from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Sum, ExpressionWrapper, F, FloatField, Count

from micmod_base.base import Currency
from core.models import BaseModel, BaseModeWF
from extra_data.models import Brand, Item, Customer, WH
from inquiry.models import Supplier
# from factor.models import FactorItem
from micmod_base.models import QuotationItem
from translator import get_text as _
from workflow.models import WorkFlow
from tools import const


class Order(BaseModeWF):
    # SALES #######################################
    ORDER_STATUS = [('1', _("draft")), ('2', _("started")), ('3', _("co-conf")), ('4', _("supp-sent")), ('5', _("sup-conf")),
                    ('6', _("pre-paid")), ('7', _("gio")), ('8', _("has-packing")), ('9', _("partial-arrived")),
                    ('10', _("total-arrived")), ('11', _("has-error")), ('12', _("completed")), ('13', _("canceled")), ]
    TRANSPORTATION_CHOICE = [("express", _("express")), ("air", _("air")), ("sea", _("sea")), ]
    is_bazar = models.BooleanField(_('is_bazar'), default=False)
    is_wh = models.BooleanField(_('is_wh'), default=False)
    ORDER_TYPE_CHOICE = [("china", _("china")), ("hong-kong", _("hong-kong")), ]
    order_title = models.CharField(max_length=255, blank=True, null=True)
    order_number = models.CharField(max_length=255, blank=True, null=True)
    # status = models.CharField(max_length=2, verbose_name=_('status'), default=1, choices=ORDER_STATUS)
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, null=True)
    sales_admin_cancel = models.BooleanField(_('sales_admin_cancel'), default=False)
    # customer = models.ForeignKey(Customer, verbose_name=_('customer'), on_delete=models.DO_NOTHING,
    #                              to_field='sepidar_party_id', db_column='customer_party_id')
    # fi = models.ForeignKey(_('fi'), FactorItem, on_delete=models.DO_NOTHING)
    transportation_method = models.CharField(_('transportation_method'), max_length=64, choices=TRANSPORTATION_CHOICE,
                                             default='sea')
    commitment_date_to_customer = models.DateField(_('commitment_date_to_customer'), null=True, blank=True)

    quantity = models.FloatField(_('quantity'), default=0)


    description_sale = models.TextField(_('description_sale'), null=True, blank=True)
    order_type = models.CharField(_('order_type'), max_length=64, choices=ORDER_TYPE_CHOICE, default='china',
                                  null=True, blank=True)
    price = models.FloatField(_("order_final_price"), null=True, blank=True, help_text='قیمت نهایی (در صورت وجود تضاد در قیمت)')

    # TRADE #######################################
    item_trade = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='item_trade', null=True,
                                   blank=True)  # Todo autocomplete with select2 search
    quantity_trade = models.FloatField(_('quantity_trade'), null=True, blank=True)
    po_number_trade = models.CharField(_("po_number_trade"), max_length=255, null=True, blank=True)
    supplier_trade = models.ForeignKey(Supplier, verbose_name=_('supplier'), null=True, blank=True,
                                       on_delete=models.DO_NOTHING, related_name='supplier_trade_set')
    price_trade = models.FloatField(_("price_trade"), null=True, blank=True)
    description_trade = models.TextField(_('description_trade'), null=True, blank=True)
    apply_mac = models.BooleanField(_('apply_mac'), default=False)
    mohandes_confirmation = models.BooleanField(_("mohandes_confirmation"), default=False)
    trade_commitment_date = models.DateField(_('trade_commitment_date'), null=True, blank=True)
    production_lead_time = models.PositiveSmallIntegerField(_('production_lead_time'), null=True, blank=True)

    # MAC #######################################
    supplier_mac = models.ForeignKey(Supplier, verbose_name=_('supplier'), null=True, blank=True,
                                     on_delete=models.DO_NOTHING, related_name='supplier_mac_set')
    price_mac = models.FloatField(_("price_mac"), null=True, blank=True)
    part_number_mac = models.CharField(_("part_number_mac"), null=True, blank=True)
    po_number_mac = models.CharField(_("po_number_mac"), max_length=255, null=True, blank=True)
    quantity_mac = models.FloatField(_('quantity_mac'), default=0, null=True, blank=True)
    description_mac = models.TextField(_('description_trade'), null=True, blank=True)

    sales_admin_confirmation = models.BooleanField(_("sales_admin_confirmation"), default=False)
    cancel = models.BooleanField(_("cancel"), default=False)
    is_over = models.BooleanField(_('is_over'), default=False)
    # qi = models.ForeignKey(Quotation, on_delete=models.DO_NOTHING, null=True)
    qi = models.ForeignKey(QuotationItem, on_delete=models.DO_NOTHING, null=True, blank=True)
    # local_sepidar_wh = models.ForeignKey(WH, on_delete=models.DO_NOTHING, null=True, blank=True)
    # local_sepidar_wh_code = models.IntegerField(_("local_sepidar_wh_code"), null=True, blank=True)
    currency = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, related_name='currency_ref', null=True, blank=True)
    order_m2m = models.ManyToManyField('self', through='OrderOrder', related_name='order_items',
                                       null=True, blank=True, verbose_name=_('OrderOrder'))

    def __str__(self):
        if self.final_item:
            return f'{self.pk} -- {self.final_item.part_number}'
        else:
            return f'{self.pk}'
        return f'{self.pk} -- {self.last_work_flow.current_state_name} -- {self.quantity} / {self.remaining_quantity}'

    @property
    def order_text_in_factor(self):
        text = f'{self.last_work_flow.current_state_name}'
        return text

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        import jdatetime
        year = str(jdatetime.date.today().year - 1400).zfill(2)
        last_order = self.__class__.objects.latest('id')
        last_pk = last_order.pk
        if self.pk is None:
            self.order_number = f'A{year}-{last_pk + 1}'
        return super().save(force_insert=False, force_update=False, using=None, update_fields=None)

    @classmethod
    def get_qs(cls, request, lst=False):
        q = request.POST.get('q')
        qs = cls.objects.get_access_object(request.user, q=q, quotation=True, lst=lst)
        return qs

    @property
    def total_price(self):
        total_price = self.final_price * self.final_quantity
        return total_price

    @property
    def final_price(self):
        # issues 295
        """ calculate effective price for order"""
        price = self.price_mac or self.price or self.price_trade or 0
        return price

    @property
    def final_quantity(self):
        quantity = self.quantity_mac or self.quantity_trade or self.quantity or 0
        return quantity

    @property
    def total_paid(self):
        s = 0
        for payment in self.order_payment_items.all():
            s += payment.total_amount
        return s

    @property
    def payment_info(self):
        total_price = self.total_price
        pay_in_percent = total_pay = is_complete = None
        total_pay, pay_in_percent = self.order_payment_items.aggregate(total_pay=Sum("total_amount"), pay_in_percent=Sum("total_amount")/total_price*100).values()
        return int(pay_in_percent or 0), total_pay, total_price, is_complete

    @property
    def gio_info(self):
        final_quantity = self.final_quantity
        total_arrived = total_arrived_in_percent = is_complete = None  # Define is_complete
        total_arrived, total_arrived_in_percent = self.gio_items.aggregate(
            total_arrived=Sum("quantity"),
            total_arrived_in_precent=Sum("quantity") / final_quantity * 100
        ).values()

        return int(total_arrived_in_percent or 0), int(total_arrived or 0), final_quantity, is_complete

    @property
    def packing_info(self):
        final_quantity = self.final_quantity
        total_arrived_wh = total_arrived_wh_in_percent = None
        total_arrived_wh, total_arrived_wh_in_percent = self.packing_item_order.aggregate(
            total_arrived_wh=Sum("arrived_quantity"),
            total_arrived_wh_in_precent=Sum("arrived_quantity")/self.final_quantity*100).values()
        return int(total_arrived_wh_in_percent or 0), int(total_arrived_wh or 0), final_quantity

    @property
    def final_po_number(self):
        return self.po_number_trade

    @property
    def final_item(self):
        return self.item_trade

    @property
    def computed_price(self):
        return self.price_trade

    def total_pay_percent(self):
        x = (self.total_paid / self.total_price) * 100
        return int(x)

    def description(self):
        sepidar_wh = None
        order = None
        if self.cancel:
            s = 0
            # supplied_quantity = self.order_base_items.all().annotate(
            #     s=Sum('quantity'), calculated_difference=ExpressionWrapper(F('s') - self.quantity, output_field=FloatField()))
            for oo in self.order_base_items.all():
                s += oo.quantity
                if oo.sepidar_wh_code:
                    sepidar_wh = True
                else:
                    order = True
            x = s - self.quantity
            if x < 0:
                return f'نیاز به {abs(x)} عدد  برای تامین کامل'
            else:
                return ''

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
    def create_with_rel(cls, data_base=None, o2=None, factor_item=None, sepidar_wh_code=None):
        if not data_base:
            data_base = {
                "order_title": "خودکار توسط سیستم",
                # "status": "1",
                "item": factor_item.qi.goods_code_fk,
                "production_lead_time": 5,  # self.qi.lead_time,
                "quantity": factor_item.quantity,
                "cancel": True if o2 else False,
                "is_over": False,
                "qi": factor_item.qi,
                "creator_user": factor_item.extra_data.request.user,
                "editor_user": factor_item.extra_data.request.user,
                'is_bazar': factor_item.is_bazar,
                'is_wh': False,
            }
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
            factor_item.supply_locations = o1
            # o1.cancel = True
            remaining_quantity = o2.remaining_quantity
            oo = OrderOrder.objects.create(order_base=o1, order_rel=o2, quantity=min(o1.quantity, remaining_quantity),
                                           sepidar_wh_code=sepidar_wh_code)
            # if remaining_quantity >= o1.quantity:
            #     oo = OrderOrder.objects.create(order_base=o1, order_rel=o2, quantity=o1.quantity, sepidar_wh_code=sepidar_wh_code)
            # else:
            #     oo = OrderOrder.objects.create(order_base=o1, order_rel=o2, quantity=remaining_quantity, sepidar_wh_code=sepidar_wh_code)
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

    @property
    def estimate_arrive_at(self):
        from django.utils import safestring
        return "1404/02/10"


class OrderOrder(BaseModel):
    STATUS_CHOICES = [("-1", _("wh__central__1")), ("-2", _("wh__resalat__1")),
                      ("-3", _("wh__res_chavoshi__1")), ("-4", _("wh__res_chavoshi__2")),
                      ("-5", _("wh__res_moradi__1",)), ]
    order_base = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='order_base_items', null=True, blank=True)
    order_rel = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='order_rel_items', null=True, blank=True)
    quantity = models.FloatField(_('quantity'), null=True, blank=True)
    # local_sepidar_wh = models.ForeignKey(WH, on_delete=models.DO_NOTHING, null=True, blank=True)
    fi = models.ForeignKey("factor.FactorItem", on_delete=models.DO_NOTHING, null=True, blank=True)
    sepidar_wh_code = models.IntegerField(_('sepidar_wh_code'), null=True, blank=True)

    @property
    def get_wh_name(self):
        if self.sepidar_wh_code == 1:
            return 'مرکزی'
        else:
            return 'رسالت'


class Packing(BaseModeWF):
    SHIPMENT_TYPE = [("express", _("express")), ("air", _("air")), ("sea", _("sea")), ]
    packing_number = models.CharField(_('packing_number'), max_length=255, null=True, blank=True)
    shipment_type = models.CharField(_('shipment_type'), max_length=255, choices=SHIPMENT_TYPE, null=True, blank=True)
    bl_number = models.CharField(_('bl_number'), max_length=255, null=True, blank=True)
    departure_date = models.DateField(_('departure_date'), null=True, blank=True)
    arrival_date = models.DateField(_('arrival_date'), null=True, blank=True)
    sales_manager_needed = models.BooleanField(_('sales_manager_needed'), default=False)
    sales_manager_check_date = models.DateField(_('sales_manager_date'), null=True, blank=True)
    delivery_to_salehi_date = models.DateField(_('delivery_to_salehi_date'), null=True, blank=True)
    cl_90_date = models.DateField(_('cl_90_date'), null=True, blank=True)
    cl_10_date = models.DateField(_('cl_10_date'), null=True, blank=True)
    cl_100_date = models.DateField(_('cl_100_date'), null=True, blank=True)
    arrive_to_wh_date = models.DateField(_('arrive_to_wh_date'), null=True, blank=True)
    estimated_delivery_date = models.DateField(_('estimated_arrive_date'), null=True, blank=True)
    sum_qty = models.FloatField(_('sum_qty'))
    sum_arrived_qty = models.FloatField(_('sum_arrived_qty'))
    description = models.TextField(_('description'), null=True, blank=True)

    def __str__(self):
        return f'{self.bl_number} -- {self.created_date}'

    @property
    def computed_estimated_delivery_date(self):
        # Todo: check this
        return self.estimated_delivery_date

    @property
    def computed_carton_qty(self):
        # Todo: check this
        return self.packing_item_rel.all().count()

    @property
    def computed_weight_kg(self):
        # Todo: check this
        return self.packing_item_rel.all().aggregate(Sum('net_weight_kg'))['net_weight_kg__sum']


class PackingItem(BaseModeWF):
    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='packing_item_order', null=True, blank=True)
    part_number = models.CharField(_('part_number'), max_length=255, null=True, blank=True)
    quantity = models.FloatField(_('quantity'), null=True, blank=True)
    arrived_quantity = models.FloatField(_('arrived_quantity'), null=True, blank=True)
    # arrive_date = models.DateField(_('arrive_date'), null=True, blank=True) Todo: check this
    price = models.FloatField(_('price'), null=True, blank=True)
    packing = models.ForeignKey(Packing, on_delete=models.DO_NOTHING, related_name='packing_item_rel')
    carton_number = models.CharField(_('carton_number'), max_length=100, null=True, blank=True)
    net_weight_kg = models.FloatField(_('weight_kg'), null=True, blank=True)
    gross_weight_kg = models.FloatField(_('grows_weight_kg'), null=True, blank=True)
    size = models.CharField(_('size'), max_length=128, null=True, blank=True)
    brand = models.CharField(_('brand'), null=True, blank=True)
    description = models.TextField(_('description'), null=True, blank=True)
    sales_conf = models.BooleanField(_('sales_conf'), default=False)
    sales_conf_date = models.DateField(_('sales_conf_date'), null=True, blank=True)
    invoice_conf = models.BooleanField(_('invoice_conf'), default=False)
    invoice_conf_date = models.DateField(_('invoice_conf_date'), null=True, blank=True)

    @property
    def computed_price(self):
        # Todo: check this
        return 0

    @property
    def computed_amount(self):
        # Todo check this
        x = self.quantity * self.price
        return x

    @property
    def computed_net_weight_kg(self):
        # Todo check this
        return 0

    @property
    def computed_gross_weight_kg(self):
        # Todo check this
        return 0

    @property
    def computed_volume_cbm(self):
        # Todo check this
        return 0

    @property
    def computed_status(self):
        # Todo check this
        return 'wh'


class GIO(BaseModeWF):
    quantity = models.FloatField(_('quantity'), default=0)
    gio_date = models.DateField(_('gio_date'))
    description = models.TextField(_('description'), null=True, blank=True)


class GIOItem(BaseModeWF):
    quantity = models.FloatField(_('quantity'), default=0)
    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='gio_items', verbose_name=_('order'), null=True, blank=True)
    gio = models.ForeignKey(GIO, on_delete=models.DO_NOTHING, related_name='gioitems')
    description = models.TextField(_('description'), null=True, blank=True)


class OrderPayment(BaseModeWF):
    from_date = models.DateField(verbose_name=_('form_date'), null=True, blank=True)
    to_date = models.DateField(verbose_name=_('to_date'), null=True, blank=True)
    total_amount = models.FloatField(_('total_amount'))
    description = models.TextField(_('description'), null=True, blank=True)


class OrderPaymentItem(BaseModeWF):
    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='order_payment_items', verbose_name=_('order'), null=True, blank=True)
    payment = models.ForeignKey(OrderPayment, on_delete=models.DO_NOTHING, related_name='payment_item', null=True, blank=True)
    from_date = models.DateField(verbose_name=_('form_date'), null=True, blank=True)
    to_date = models.DateField(verbose_name=_('to_date'), null=True, blank=True)
    description = models.TextField(_('description'), null=True, blank=True)
    quantity = models.FloatField(verbose_name='payment_quantity', null=True, blank=True)

    bank = models.ForeignKey('ACNT', on_delete=models.DO_NOTHING, verbose_name=_('info_Bank'), null=True, blank=True)
    destination_currency = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, related_name='destination_currency')
    currency = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, null=True, blank=True, related_name='base_currency')
    exchange_rate = models.FloatField(default=1.0, verbose_name=_('rate'))
    total_amount = models.FloatField(_('total_amount'))


class ACNT(BaseModeWF):
    info_bank = models.CharField(_('info_Bank'), max_length=120)
    currency = models.ForeignKey(Currency, on_delete=models.DO_NOTHING)
    first_amount = models.FloatField(default=0.0)
    is_blocked = models.BooleanField(default=False)
    block_date = models.DateField(null=True, blank=True)
    description = models.TextField(_('description'), null=True, blank=True)

    def __str__(self):
        return f'{self.info_bank} {self.currency.title_en}'
