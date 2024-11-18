from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from core.models import BaseModel, BaseModeWF
from extra_data.models import Brand, Item, Customer, WH
# from factor.models import FactorItem
from micmod_base.models import QuotationItem
from translator import get_text as _
from workflow.models import WorkFlow
from tools import const


class Order(BaseModeWF):
    ORDER_STATUS = [('1', _("draft")), ('2', _("started")), ('3', _("co-conf")), ('4', _("supp-sent")), ('5', _("sup-conf")),
                    ('6', _("pre-paid")), ('7', _("gio")), ('8', _("has-packing")), ('9', _("partial-arrived")),
                    ('10', _("total-arrived")), ('11', _("has-error")), ('12', _("completed")), ('13', _("canceled")), ]
    TRANSPORTATION_CHOICE = [("express", _("express")), ("air", _("air")), ("sea", _("sea")), ]
    ORDER_TYPE_CHOICE = [("china", _("china")), ("hong-kong", _("hong-kong")), ]
    order_title = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=2, verbose_name=_('status'), default=1, choices=ORDER_STATUS)
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, null=True)
    # customer = models.ForeignKey(Customer, verbose_name=_('customer'), on_delete=models.DO_NOTHING,
    #                              to_field='sepidar_party_id', db_column='customer_party_id')
    # fi = models.ForeignKey(_('fi'), FactorItem, on_delete=models.DO_NOTHING)
    transportation_method = models.CharField(_('transportation_method'), max_length=64, choices=TRANSPORTATION_CHOICE,
                                             default='sea')
    production_lead_time = models.PositiveSmallIntegerField(_('production_lead_time'), null=True, blank=True)
    trade_commitment_date = models.DateField(_('trade_commitment_date'), null=True, blank=True)
    commitment_date_to_customer = models.DateField(_('commitment_date_to_customer'), null=True, blank=True)
    quantity = models.FloatField(_('quantity'), default=0)
    description_sale = models.TextField(_('description_sale'), null=True, blank=True)
    order_type = models.CharField(_('order_type'), max_length=64, choices=ORDER_TYPE_CHOICE, default='china',
                                  null=True, blank=True)
    sales_admin_confirmation = models.BooleanField(_("sales_admin_confirmation"), default=False)
    cancel = models.BooleanField(_("cancel"), default=False)
    is_over = models.BooleanField(_('is_over'), default=False)
    # qi = models.ForeignKey(Quotation, on_delete=models.DO_NOTHING, null=True)
    qi = models.ForeignKey(QuotationItem, on_delete=models.DO_NOTHING, null=True, blank=True)
    # local_sepidar_wh = models.ForeignKey(WH, on_delete=models.DO_NOTHING, null=True, blank=True)
    local_sepidar_wh_code = models.IntegerField(_("local_sepidar_wh_code"), null=True, blank=True)

    order_m2m = models.ManyToManyField('self', through='OrderOrder', related_name='order_items',
                                       null=True, blank=True, verbose_name=_('OrderOrder'))

    def __str__(self):
        return f'{self.pk} -- {self.order_title} -- {self.quantity} / {self.remaining_quantity}'

    def description(self):
        if self.cancel:
            s = 0
            for oo in self.order_base_items.all():
                s += oo.quantity
            x = s - self.quantity
            if x < 0:
                return f'نیاز به {abs(x)} عدد  برای تامین کامل'
        return ''
        return 'تامین کامل'

        # remaining_quantity = self.remaining_quantity
        # if remaining_quantity < 0:
        #     return f'نیاز به {abs(remaining_quantity)} عدد برای تامین کامل'
        # f'ظرفیت سفارش {self.quantity}'
        # return f'{self.pk} -- {self.order_title} -- {self.quantity} / {self.remaining_quantity}'
    
    @classmethod
    def get_qs_count(cls, user):
        return 0

    @classmethod
    def create_with_rel(cls, data_base, o2=None):
        o1 = cls.objects.create(**data_base)
        flow_data = {
            "wf_status": 5,
            "action": 'ایجاد خودکار',
            "flow_name": 'سفارش',
            "state": const.WF__ORDER__FIRST_STATE,
            "wf_description": const.WF__ORDER__FIRST_WF_DESCRIPTION,
            "belong_to_group": 'order_admin',
            "object_id": o1.pk,
            "content_type": ContentType.objects.get_for_model(o1),
            "creator_user": data_base.get('creator_user'),
            "editor_user": data_base.get('editor_user'),
            "from_user": data_base.get('creator_user'),
            "to_user": data_base.get('creator_user'), # get_user_model().objects.filter(groups__name='order_admin').first(),
            "current_state_name": const.WF__ORDER__FIRST_CURRENT_STATE_NAME,
        }
        wf = WorkFlow.objects.create(**flow_data)
        flow_data = {
            "wf_status": 3,
            "action": 'ایجاد خودکار',
            "flow_name": 'سفارش',
            "state": const.WF__ORDER__FIRST_STATE,
            "wf_description": const.WF__ORDER__FIRST_WF_DESCRIPTION,
            "belong_to_group": 'order_admin',
            "object_id": o1.pk,
            "content_type": ContentType.objects.get_for_model(o1),
            "creator_user": data_base.get('creator_user'),
            "editor_user": data_base.get('editor_user'),
            "from_user": data_base.get('editor_user'),
            "to_user": get_user_model().objects.filter(groups__name='order_admin').first(),
            "current_state_name": const.WF__ORDER__FIRST_CURRENT_STATE_NAME,
        }

        wf = WorkFlow.objects.create(**flow_data)
        o1.last_work_flow = wf
        if o2 is not None:
            o1.cancel = True
            remaining_quantity = o2.remaining_quantity
            if remaining_quantity >= o1.quantity:
                oo = OrderOrder.objects.create(order_base=o1, order_rel=o2, quantity=o1.quantity)
            else:
                oo = OrderOrder.objects.create(order_base=o1, order_rel=o2, quantity=remaining_quantity)
        o1.save()
        return o1

    @property
    def remaining_quantity(self):
        total_consumed_count = 0
        total_count = self.quantity
        # if self.cancel:
        #     total_count = 0
        #     for oo in self.order_m2m.all():
        #         total_count += oo.quantity

        for fi in self.factor_items.all():
            total_consumed_count += fi.quantity
        for oo in self.order_rel_items.all():
            total_consumed_count += oo.quantity
        return total_count - total_consumed_count


class OrderOrder(BaseModel):
    STATUS_CHOICES = [("-1", _("wh__central__1")), ("-2", _("wh__resalat__1")),
                      ("-3", _("wh__res_chavoshi__1")), ("-4", _("wh__res_chavoshi__2")),
                      ("-5", _("wh__res_moradi__1",)), ]
    order_base = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='order_base_items', null=True, blank=True)
    order_rel = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='order_rel_items', null=True, blank=True)
    quantity = models.FloatField(_('quantity'), null=True, blank=True)
    # local_sepidar_wh = models.ForeignKey(WH, on_delete=models.DO_NOTHING, null=True, blank=True)
    fi = models.ForeignKey("factor.FactorItem", on_delete=models.DO_NOTHING, null=True, blank=True)


from django.db.models.signals import m2m_changed

def toppings_changed(sender, **kwargs):
    # sender.objects.create(order_base=kwargs.get('instance'), order_rel_id=list(kwargs.get('pk_set'))[0], quantity=min(rel.remaining_quantity, div_quantity))
    pass

m2m_changed.connect(toppings_changed, sender=Order.order_m2m.through)


class Packing(BaseModeWF):
    # PACKING_STATUS = [("1", _("ثبت اولیه")), ("2", _("dep")), ("3", _("arrive")), ("4", _("10%")),
    #                   ("5", _("تحویل اسناد")), ("6", _("اضهار گمرک")), ("7", _("ترخیص گمرک")), ("8", _("تحویل انبار"))]
    # status = models.CharField(choices=PACKING_STATUS)
    TP_METHOD = [('1', 'air'), ('2', 'sea'), ('3', 'exp')]
    sum_qty = models.FloatField(_('sum_qty'))
    sum_arrived_qty = models.FloatField(_('sum_arrived_qty'))
    tp_method = models.CharField(choices=TP_METHOD)
    pack_date = models.DateField(_('pack_date'))
    bl_number = models.CharField(_('bl_number'), max_length=255, null=True, blank=True)
    sales_manager_needed = models.BooleanField(_('sales_manager_needed'), default=False)
    description = models.TextField(_('description'), null=True, blank=True)

    def __str__(self):
        return f'{self.bl_number} -- {self.pack_date}'


class PackingItem(BaseModeWF):
    packing = models.ForeignKey(Packing, on_delete=models.DO_NOTHING, related_name='packing_item_rel')
    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='packing_item_order', null=True, blank=True)
    part_number = models.CharField(_('part_number'), max_length=255, null=True, blank=True)
    brand = models.CharField(_('brand'), null=True, blank=True)
    carton_number = models.CharField(_('carton_number'), max_length=100, null=True, blank=True)
    quantity = models.FloatField(_('quantity'), null=True, blank=True)
    size = models.CharField(_('size'), max_length=128, null=True, blank=True)
    volume = models.FloatField(_('volume'), null=True, blank=True)
    price = models.FloatField(_('price'), null=True, blank=True)
    amount = models.FloatField(_('amount'), null=True, blank=True)
    sales_conf = models.BooleanField(_('sales_conf'), default=False)
    duty_date = models.DateField(_('duty_date'), null=True, blank=True)
    item_weight = models.FloatField(_('item_weight'), null=True, blank=True)

    carton_qty = models.PositiveIntegerField(_('carton_qty'), null=True, blank=True)
    net_weight_kg = models.FloatField(_('weight_kg'), null=True, blank=True)
    grows_weight_kg = models.FloatField(_('grows_weight_kg'), null=True, blank=True)


class GIO(BaseModeWF):
    gio_date = models.DateField(_('gio_date'))
    total_quantity = models.FloatField(_('total_quantity'))


class GIOItem(BaseModeWF):
    quantity = models.FloatField(_('quantity'))
    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='gio_items', verbose_name=_('order'))
