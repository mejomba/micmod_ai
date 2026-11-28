"""Observe meaningful changes; collect affected documents only after commit.

Signals cover normal save/delete; bulk writes are explicitly hooked where
known and reconciled by the daily sweep. Default database only.
"""
import logging
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from extra_data.models import Item, ItemWeight
from workflow.models import WorkFlow
from .models import Order, GIO, GIOItem, Packing, PackingItem, PackingSepidarTransfer, PackingSepidarTransferItem
from .scheduling_queue import enabled, enqueue
from .scheduling_rules import normalize_label

logger = logging.getLogger(__name__)
FIELDS = {
    Order: ('item_id', 'item_trade_id', 'quantity', 'quantity_mac', 'quantity_trade',
            'production_lead_time', 'price_inquiry_result_id', 'transportation_method',
            'is_wh', 'is_bazar', 'is_deleted', 'cancel', 'sales_admin_cancel', 'is_over'),
    GIO: ('manual_weight_kg', 'gio_date', 'is_deleted'),
    GIOItem: ('gio_id', 'order_id', 'quantity', 'is_deleted'),
    Packing: ('shipment_type', 'estimated_arrive_to_wh_date', 'estimated_shipping_start_date', 'is_deleted'),
    PackingItem: ('packing_id', 'order_id', 'quantity', 'wh_receipt_quantity', 'ruined_quantity', 'is_deleted'),
    PackingSepidarTransfer: ('packing_id', 'status', 'receipt_id', 'destination_stock_ref', 'transfer_type', 'sent_at'),
    PackingSepidarTransferItem: ('packing_item_id', 'transfer_id', 'quantity'),
    ItemWeight: ('sku_id', 'weight', 'is_deleted', 'creator_user_id', 'editor_user_id'),
    Item: ('is_deleted',),
    WorkFlow: ('content_type_id', 'object_id', 'wf_status', 'state', 'current_state_name', 'is_deleted'),
}


def _values(instance):
    return {key: getattr(instance, key) for key in FIELDS[type(instance)]}


def _before(sender, instance, using, raw=False, **kwargs):
    if enabled() and not raw and using == 'default':
        instance._scheduling_old = sender._base_manager.filter(pk=instance.pk).values(*FIELDS[sender]).first() if instance.pk else None


def _after(sender, instance, using, raw=False, **kwargs):
    if not enabled() or raw or using != 'default':
        return
    # Read persisted values, not unsaved attributes omitted by update_fields.
    new = sender._base_manager.filter(pk=instance.pk).values(*FIELDS[sender]).first()
    if new is None:
        return
    old = getattr(instance, '_scheduling_old', None)
    if old == new:
        return
    if sender is WorkFlow and new['wf_status'] == 4:
        return
    _defer(sender, instance.pk, old or {}, new)


def _deleted(sender, instance, using, **kwargs):
    if enabled() and using == 'default':
        _defer(sender, instance.pk, _values(instance), {})


def _defer(sender, pk, old, new):
    def callback():
        try:
            _collect(sender, pk, old, new)
        except Exception:
            # The primary operation has already committed. Reconciliation can
            # recover an enqueue failure without undoing or replaying Sepidar.
            logger.exception('Unable to enqueue scheduling change: %s/%s', sender.__name__, pk)
    transaction.on_commit(callback, using='default')


def notify_gio_weight_changed(gio_id):
    """Explicit hook for the weight endpoint's QuerySet.update()."""
    if enabled():
        _defer(GIO, gio_id, {}, {})


def _collect(sender, pk, old, new):
    orders, packings, gios = set(), set(), set()
    reason = sender.__name__.lower() + '_changed'
    def related_ids(field):
        return {value for value in (old.get(field), new.get(field)) if value}
    if sender is WorkFlow:
        from django.contrib.contenttypes.models import ContentType
        for values in (old, new):
            if not values.get('content_type_id') or not values.get('object_id'):
                continue
            ct = ContentType.objects.get_for_id(values['content_type_id'])
            if (ct.app_label, ct.model) == ('order', 'order'):
                orders.add(values['object_id'])
            elif (ct.app_label, ct.model) == ('order', 'packing'):
                packings.add(values['object_id'])
        reason = 'workflow_transition'
        if orders and new.get('wf_status') == 3 and normalize_label(new.get('current_state_name')) == 'تایید بازرگانی':
            reason = 'trade_entry'
    elif sender is Order:
        orders.add(pk)
        gios.update(GIOItem.objects.filter(order_id=pk).values_list('gio_id', flat=True))
    elif sender is GIO:
        gios.add(pk)
    elif sender is GIOItem:
        gios.update(related_ids('gio_id'))
        orders.update(related_ids('order_id'))
    elif sender is Packing:
        packings.add(pk)
    elif sender is PackingItem:
        packings.update(related_ids('packing_id'))
        orders.update(related_ids('order_id'))
    elif sender is PackingSepidarTransfer:
        packings.update(related_ids('packing_id'))
    elif sender is PackingSepidarTransferItem:
        packings.update(PackingItem._base_manager.filter(pk__in=related_ids('packing_item_id')).values_list('packing_id', flat=True))
        orders.update(PackingItem._base_manager.filter(pk__in=related_ids('packing_item_id')).values_list('order_id', flat=True))
    elif sender in (Item, ItemWeight):
        sku_ids = {pk} if sender is Item else related_ids('sku_id')
        orders.update(Order.objects.filter(Q(item_id__in=sku_ids) | Q(item_trade_id__in=sku_ids)).values_list('pk', flat=True))
        gios.update(GIOItem.objects.filter(order_id__in=orders).values_list('gio_id', flat=True))

    orders.update(GIOItem.objects.filter(gio_id__in=gios).values_list('order_id', flat=True))
    # A changed packing row can change the candidate GIO for every row in
    # that packing. Include directly related orders even when the row was removed.
    orders.update(PackingItem.objects.filter(packing_id__in=packings).values_list('order_id', flat=True))
    # An entire GIO weight can affect other orders and their packing drafts.
    packings.update(PackingItem.objects.filter(order_id__in=orders).values_list('packing_id', flat=True))
    orders.update(PackingItem.objects.filter(packing_id__in=packings).values_list('order_id', flat=True))
    for key, ids in (('order', orders), ('packing', packings)):
        for object_id in sorted(x for x in ids if x):
            enqueue(key, object_id, reason)


def connect():
    for sender in FIELDS:
        # WorkFlow/Item signals must not alter other applications' data.
        label = sender._meta.label_lower
        pre_save.connect(_before, sender=sender, weak=False, dispatch_uid='schedule.pre.' + label)
        post_save.connect(_after, sender=sender, weak=False, dispatch_uid='schedule.post.' + label)
        post_delete.connect(_deleted, sender=sender, weak=False, dispatch_uid='schedule.delete.' + label)
