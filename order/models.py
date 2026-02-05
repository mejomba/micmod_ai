import jdatetime
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Sum, ExpressionWrapper, F, FloatField, Count

from micmod_base.base import Currency
from core.models import BaseModel, BaseModeWF, BaseManager
from extra_data.models import Brand, Item, Customer, WH
from inquiry.models import Supplier
# from factor.models import FactorItem
from micmod_base.models import QuotationItem, CustomerRequestItem
from sepidar.api_call import SepidarApiCall
from translator import get_text as _
from workflow.models import WorkFlow
from tools import const


class SepidarOrderDocument(models.Model):
    """
    << data format >>
    data = {
        "payment": [{
            "id": 111,
            "sepidar": [
                {
                    "credit_debit": {
                        "id": 123541,
                        "number": 44521
                    },
                    "credit_debit_2": {
                        "id": 123541,
                        "number": 44521
                    },
                    "voucher": {
                        "id": 123541,
                        "number": 44521
                    }
                }
            ],
            "general": {"id": 45, "row_id": 2, "quantity": 200, "amount": 200, "currency": "usd"}
        }],
        "gio": [{
            "id": 111,
            "sepidar": [
                {
                    "purchase_invoice": {
                        "number": 13, "id": 1142, "quantity": 400,
                        "price": 0.8, "currency": 'rmb'
                    },
                    "before_central_wh_receipt": {
                        "id": 44123,
                        "number": 123,
                    },
                    "voucher": {
                        "id": 1236652,
                        "number": 12521
                    }
                }
            ],
            "general": {"id": 45, "row_id": 2, "quantity": 200}
        }],
        "packing": [{
            "id": 111,
            "sepidar": [
                {
                    "wh_delivery": {
                        "id": 1,
                        "number": 1,
                        "quantity": 200
                    },
                    "wh_receipt": {
                        "id": 1,
                        "number": 1,
                        "quantity": 200
                    }
                }
            ],
            "general": {"id": 45, "row_id": 2, "quantity": 200}
        }]
    }
    """
    data = models.JSONField(null=True, blank=True)
    order = models.OneToOneField("Order", on_delete=models.DO_NOTHING, related_name='sepidar_document', null=True, blank=True)

    @staticmethod
    def get_format():
        return {
            "payment": {
                "sepidar": [
                    {
                        "credit_debit": {
                            "id": 123541,
                            "number": 44521
                        },
                        "credit_debit_2": {
                            "id": 123541,
                            "number": 44521
                        },
                        "voucher": {
                            "id": 123541,
                            "number": 44521
                        }
                    }
                ],
                "general": {"id": 45, "row_id": 2, "quantity": 200, "amount": 200, "currency": "usd"}
            },
            "gio": {
                "sepidar": [
                    {
                        "purchase_invoice": {
                            "number": 13, "id": 1142, "quantity": 400,
                            "price": 0.8, "currency": 'rmb'
                        },
                        "before_central_wh_receipt": {
                            "id": 44123,
                            "number": 123,
                        },
                        "voucher": {
                            "id": 1236652,
                            "number": 12521
                        }
                    }
                ],
                "general": {"id": 45, "row_id": 2, "quantity": 200}
            },
            "packing": {
                "sepidar": [
                    {
                        "wh_delivery": {
                            "id": 1,
                            "number": 1,
                            "quantity": 200
                        },
                        "wh_receipt": {
                            "id": 1,
                            "number": 1,
                            "quantity": 200
                        }
                    }
                ],
                "general": {"id": 45, "row_id": 2, "quantity": 200}
            }
        }


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
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, null=True)
    sales_admin_cancel = models.BooleanField(_('sales_admin_cancel'), default=False)
    transportation_method = models.CharField(_('transportation_method'), max_length=64, choices=TRANSPORTATION_CHOICE,
                                             default='sea', null=True, blank=True)
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
    qi = models.ForeignKey(QuotationItem, on_delete=models.DO_NOTHING, null=True, blank=True)
    currency = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, related_name='currency_ref', null=True, blank=True)
    order_m2m = models.ManyToManyField('self', through='OrderOrder', related_name='order_items',
                                       null=True, blank=True, verbose_name=_('OrderOrder'))
    customer_request_item = models.ForeignKey(CustomerRequestItem, on_delete=models.DO_NOTHING, null=True, blank=True,
                                              related_name='customer_order_items')
    buy_factors = models.JSONField(verbose_name=_("buy_factor"), default=list, null=True, blank=True)
    buy_factor_quantity_in_sepidar = models.FloatField(verbose_name=_('buy_factor_quantity_in_sepidar'), null=True, blank=True)
    order_report_data = models.JSONField(null=True, blank=True)
    sepidar_wh_code = models.IntegerField(null=True, blank=True)
    receipt_in_wh = models.BooleanField(default=False)

    def __str__(self):
        if self.final_item:
            return f'{self.pk} -- {self.final_item.part_number}'
        else:
            return f'{self.pk}'
        return f'{self.pk} -- {self.last_work_flow.current_state_name} -- {self.quantity} / {self.remaining_quantity}'

    def is_other_orders_available(self):
        illegal_order_ids = [x.order_rel.pk for x in self.order_base_items.all()] if self.pk else []
        illegal_order_ids.append(self.pk)
        return True
        return self.__class__.objects.filter(item=self.item).exclude(pk__in=illegal_order_ids).exists()

    @property
    def sepidar_wh_quantity(self):
        if not hasattr(self, 'oo'):
            return None
        """ WARN__: this function has massive execution time"""
        year = jdatetime.date.today().year
        res = []
        stock_qty_api = SepidarApiCall.get_stock_quantity([self.item.sepidar_id_0], year) if self.is_wh else {}
        api_res = stock_qty_api.get('res')
        if api_res:
            for name_code, stock_qty in api_res.items():
                if stock_qty:
                    sepidar_wh_name = name_code[0]  # re.search(r'(.*)\(code.*\)', code).group(1)
                    sepidar_wh_code = name_code[1]  # re.search(r'(code: (\d+))', code).group(2)
                    # todo get wh__order from db, show reserve and stock_quantity
                    if self.oo.sepidar_wh_code == sepidar_wh_code:
                        quantity_sum = self.item.reserved_count_in_portal(sepidar_wh_code)
                        if stock_qty.is_integer():
                            qty = int(stock_qty)
                            if qty - quantity_sum < 0:
                                res.append(f'☑️ {sepidar_wh_name} (کل:{qty:,}) - (آزاد: منفی{int(abs(qty - quantity_sum)):,})')#, int(qty - quantity_sum))
                            else:
                                res.append(f'☑️ {sepidar_wh_name} (کل:{qty:,}) - (آزاد:{int(qty - quantity_sum):,})')
                        else:
                            qty = stock_qty
                            res.append((f'wh__{sepidar_wh_code}', f'☑️ {sepidar_wh_name} {stock_qty}'))

        for o in self.item.order_set.filter(cancel=False).order_by('-quantity'):
            if o.cancel:
                for oo in o.order_base_items.all():
                    if oo.sepidar_wh_code:
                        res.append(
                            ((f'wh__{oo.sepidar_wh_code}__{o.pk}'), f"رزرو انبار {o.pk} ام ({oo.quantity:0.20g})"))
                    else:
                        remaining_quantity = o.remaining_quantity
                        if remaining_quantity > 0:
                            res.append(f"🧺 {o.last_work_flow.current_state_name} ({o.quantity:0.20g} کل) - (آزاد {remaining_quantity:0.20g})")
            else:
                remaining_quantity = o.remaining_quantity
                if remaining_quantity > 0:
                    res.append(f"🧺 {o.last_work_flow.current_state_name} (کل {o.quantity:0.20g}) - (آزاد {remaining_quantity:0.20g})  🕘 {o.estimate_arrive_at}")

        if not res:
            return None

        return res[0]

    @property
    def sepidar_wh_item_pair_quantity(self):
        if not hasattr(self, 'oo'):
            return None
        """ WARN__: this function has massive execution time"""
        year = jdatetime.date.today().year
        stock_qty_api = SepidarApiCall.get_stock_item_pair_quantity([self.item.sepidar_id_0], self.oo.sepidar_wh_code, year)
        if stock_qty_api:
            if stock_qty_api.get('results'):
                return stock_qty_api.get('results')[0].get('quantity')

        return None


    @property
    def order_text_in_factor(self):
        text = f'{self.last_work_flow.current_state_name}'
        return text

    @property
    def where_is_other_payment(self):
        return [{'payment': x.payment.pk, 'total_amount': x.total_amount, 'currency': x.payment.currency.title_en if x.payment.currency else None} for x in self.order_payment_items.all()]

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        import jdatetime
        year = str(jdatetime.date.today().year - 1400).zfill(2)
        last_pk = self.__class__.objects.latest('id').pk if self.__class__.objects.exists() else 0
        if self.pk is None:
            self.order_number = f'A{year}-{last_pk + 1}'
        return super().save(force_insert=False, force_update=False, using=None, update_fields=None)

    @classmethod
    def get_qs(cls, request, lst=False, groups_list=None):
        q = request.POST.get('q')
        qs = cls.objects.get_access_object(request.user, q=q, lst=lst, groups_list=groups_list)
        return qs

    @property
    def total_price(self):
        total_price = self.final_price * self.final_quantity
        return total_price

    @property
    def final_price(self):
        # issues 295
        """ calculate effective price for order"""
        price = self.price or self.price_mac or self.price_trade or 0
        return price

    @property
    def final_discount(self):
        discount = (self.price_mac or self.price_trade or 0) - self.final_price
        if discount > 0:
            return discount
        return 0

    @property
    def final_addition(self):
        return 0

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
    def remaining_amount(self):
        return self.total_price - self.total_paid

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
        if self.is_bazar:
            return final_quantity, final_quantity, final_quantity
        total_arrived_wh = total_arrived_wh_in_percent = 0
        x = []
        if self.cancel:
            for oo in self.order_base_items.all():
                if oo.sepidar_wh_code:
                    total_arrived_wh += oo.quantity
                else:
                    arrived_wh, arrived_wh_in_percent = oo.order_rel.packing_item_order.filter().aggregate(
                    total_arrived_wh=Sum("wh_receipt_quantity"),
                    total_arrived_wh_in_precent=Sum("wh_receipt_quantity") / self.final_quantity * 100).values()

                    total_arrived_wh += (arrived_wh or 0)
                    total_arrived_wh_in_percent += (arrived_wh_in_percent or 0)
            return int(total_arrived_wh_in_percent or 0), int(total_arrived_wh or 0), final_quantity

        total_arrived_wh, total_arrived_wh_in_percent = self.packing_item_order.filter().aggregate(
            total_arrived_wh=Sum("wh_receipt_quantity"),
            total_arrived_wh_in_precent=Sum("wh_receipt_quantity")/self.final_quantity*100).values()
        return int(total_arrived_wh_in_percent or 0), int(total_arrived_wh or 0), final_quantity

    @property
    def is_all_arrival(self):
        _, in_wh, final_quantity = self.packing_info
        if in_wh == final_quantity:
            return True
        return False

    @property
    def final_po_number(self):
        return self.po_number_trade

    @property
    def final_supplier(self):
        if self.supplier_mac:
            return self.supplier_mac
        elif self.supplier_trade:
            return self.supplier_trade

    @property
    def final_item(self):
        if self.item_trade:
            return self.item_trade
        else:
            return self.item

    @property
    def computed_price(self):
        return self.price_trade

    def total_pay_percent(self):
        x = (self.total_paid / self.total_price) * 100
        return int(x)

    @property
    def needed_qty(self):
        s = self.total_supply_qty - self.quantity
        return abs(s)

    @property
    def total_supply_qty(self):
        s = self.order_base_items.aggregate(total=Sum('quantity'))['total'] or 0
        return s

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
    def create_with_rel(cls, data_base=None, o2=None, factor_item=None, sepidar_wh_code=None, is_wh=False):
        if not data_base:
            data_base = {
                "order_title": "خودکار توسط سیستم",
                # "status": "1",
                "item": factor_item.qi.goods_code_fk,
                "production_lead_time": 5,  # TODO self.qi.lead_time,
                "quantity": factor_item.quantity,
                "cancel": True if o2 else False,
                "is_over": False,
                "qi": factor_item.qi,
                "creator_user": factor_item.extra_data.request.user,
                "editor_user": factor_item.extra_data.request.user,
                'is_bazar': factor_item.is_bazar,
                'is_wh': is_wh,
                'commitment_date_to_customer': factor_item.qi.supply_date,
                'transportation_method': factor_item.qi.get_price_method_type,
                'sepidar_wh_code': sepidar_wh_code
            }
        o1 = cls.objects.create(**data_base)
        flow_data = {
            "wf_status": 5,  # first draft
            "action": 'ایجاد خودکار',
            "flow_name": 'سفارش',
            "state": const.WF__ORDER__FIRST_STATE,
            "wf_description": const.WF__ORDER__FIRST_WF_DESCRIPTION,
            "belong_to_group": 'sales_user',
            "object_id": o1.pk,
            "content_type": ContentType.objects.get_for_model(o1),
            "creator_user": data_base.get('creator_user'),
            "editor_user": data_base.get('editor_user'),
            "from_user": data_base.get('creator_user'),
            "to_user": data_base.get('creator_user'), # get_user_model().objects.filter(groups__name='order_admin').first(),
            "current_state_name": const.WF__ORDER__FIRST_CURRENT_STATE_NAME,
        }
        wf = WorkFlow.objects.create(**flow_data)

        o1.last_work_flow = wf
        oo = None
        if o2 is not None:
            factor_item.supply_locations = o1
            # o1.cancel = True
            remaining_quantity = o2.remaining_quantity
            oo = OrderOrder.objects.create(order_base=o1, order_rel=o2, quantity=min(factor_item.quantity, o1.quantity, remaining_quantity, factor_item.reserve_count),
                                           sepidar_wh_code=sepidar_wh_code, creator_user=factor_item.creator_user, editor_user=factor_item.creator_user,
                                           item=o1.item)
        o1.extra_data.request = factor_item.extra_data.request
        o1.save()
        return o1, oo

    @property
    def remaining_quantity(self):
        total_consumed_count = 0
        total_count = self.final_quantity
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
        return "-"

    @property
    def order_method(self):
        if self.is_wh:
            return 'رزرو انبار'
        if self.is_bazar:
            return 'سفارش بازار'
        if not self.is_bazar and not self.is_wh:
            return 'سفارش خارجی'

    @property
    def select2_placeholder(self):
        return f'{self.pk} - {self.final_item} - {self.final_item.part_number}'

    sepidar_wh_map = {
        2: "انبار مركزي",
        5: "انبار اوليه فروشگاه",
        15: "ويترين",
        19: "انبار فروشگاه",
        22: "انبار توليد",
        23: "انبار موقت",
        24: "انبار سايت",
        25: "shenzen",
        26: "انباري",
        27: "leadtime",
        28: "گمرك",
        29: "انبار 19",
        30: "انبار فني",
        32: "انبار سوختي گمرك",
        33: "hogkog majazi",
        34: "انبار طبقه 3",
        35: "گمرك مجازي",
        37: "انبار اماني",
        40: "انبار 5",
        42: "انبار كالاي معيوب",
        44: "انبار اماني سايت",
        45: "HONGKONG",
        50: "انبار رزرو 2",
        51: "انبار رزرو 1",
        53: "انبار رزرو 3",
        54: "انبار رزرو 4",
        55: "انبار ورامين",
        56: "انبار رزرو ماركت",
        57: "انبار رزرو رايكا",
        58: "انبار رزرو JRC",
        59: "انبار مركزي 2",
        60: "انبار رزرو آقاي چاوشي",
        61: "انبار نمونه",
        62: "انبار قرنطينه",
        63: "انبار بازار",
        64: "انبار مرجوعي مشتري خاص",
        65: "انبار بازرگاني(غير قابل فروش)",
        69: "انبار رزرو 5",
        70: "انبار اصفهان",
        73: "انبار رسالت",
        74: "انبار رسالت رزرو 1",
        75: "انبار رسالت رزرو 2",
        76: "انبار رسالت رزرو 3",
        77: "انبار رسالت رزرو 4",
        78: "انبار رسالت رزرو 5",
        79: "انبار رسالت معيوب",
        80: "انبار توليد آقاي پاكدل",
        81: "انبار مجازي مرصوص",
        82: "انبار توليد PCB",
        83: "انبار محصول  PCB",
        84: "انبار رزرو 6",
        85: "انبار رسالت رزرو 6",
        87: "انبار آذين",
        88: "انبار مواد اوليه ايروان",
        89: "انبار محصول ايروان",
        90: "انبار کالای بین راهی لوئیز"
    }

    @property
    def get_wh_name(self):
        name = self.sepidar_wh_map.get(self.sepidar_wh_code)
        if not name:
            name = 'سفارش'
        return name


class OrderOrder(BaseModel):
    sepidar_wh_map = {
        2: "انبار مركزي",
        5: "انبار اوليه فروشگاه",
        15: "ويترين",
        19: "انبار فروشگاه",
        22: "انبار توليد",
        23: "انبار موقت",
        24: "انبار سايت",
        25: "shenzen",
        26: "انباري",
        27: "leadtime",
        28: "گمرك",
        29: "انبار 19",
        30: "انبار فني",
        32: "انبار سوختي گمرك",
        33: "hogkog majazi",
        34: "انبار طبقه 3",
        35: "گمرك مجازي",
        37: "انبار اماني",
        40: "انبار 5",
        42: "انبار كالاي معيوب",
        44: "انبار اماني سايت",
        45: "HONGKONG",
        50: "انبار رزرو 2",
        51: "انبار رزرو 1",
        53: "انبار رزرو 3",
        54: "انبار رزرو 4",
        55: "انبار ورامين",
        56: "انبار رزرو ماركت",
        57: "انبار رزرو رايكا",
        58: "انبار رزرو JRC",
        59: "انبار مركزي 2",
        60: "انبار رزرو آقاي چاوشي",
        61: "انبار نمونه",
        62: "انبار قرنطينه",
        63: "انبار بازار",
        64: "انبار مرجوعي مشتري خاص",
        65: "انبار بازرگاني(غير قابل فروش)",
        69: "انبار رزرو 5",
        70: "انبار اصفهان",
        73: "انبار رسالت",
        74: "انبار رسالت رزرو 1",
        75: "انبار رسالت رزرو 2",
        76: "انبار رسالت رزرو 3",
        77: "انبار رسالت رزرو 4",
        78: "انبار رسالت رزرو 5",
        79: "انبار رسالت معيوب",
        80: "انبار توليد آقاي پاكدل",
        81: "انبار مجازي مرصوص",
        82: "انبار توليد PCB",
        83: "انبار محصول  PCB",
        84: "انبار رزرو 6",
        85: "انبار رسالت رزرو 6",
        87: "انبار آذين",
        88: "انبار مواد اوليه ايروان",
        89: "انبار محصول ايروان",
        90: "انبار کالای بین راهی لوئیز"
    }

    STATUS_CHOICES = [("-1", _("wh__central__1")), ("-2", _("wh__resalat__1")),
                      ("-3", _("wh__res_chavoshi__1")), ("-4", _("wh__res_chavoshi__2")),
                      ("-5", _("wh__res_moradi__1",)), ]
    order_base = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='order_base_items', null=True, blank=True)
    order_rel = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='order_rel_items', null=True, blank=True)
    quantity = models.FloatField(_('quantity'), null=True, blank=True)
    # local_sepidar_wh = models.ForeignKey(WH, on_delete=models.DO_NOTHING, null=True, blank=True)
    fi = models.ForeignKey("factor.FactorItem", on_delete=models.DO_NOTHING, null=True, blank=True)
    sepidar_wh_code = models.IntegerField(_('sepidar_wh_code'), null=True, blank=True)
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='oo_items', null=True, blank=True)

    @property
    def get_wh_name(self):
        name = self.sepidar_wh_map.get(self.sepidar_wh_code)
        if not name:
            name = 'سفارش'
        return name
        # if self.sepidar_wh_code == 1:
        #     return 'مرکزی'
        # else:
        #     return 'رسالت'


class Packing(BaseModeWF):
    SHIPMENT_TYPE = [("express", _("express")), ("air", _("air")), ("sea", _("sea")), ]
    WH_DESTINATION_CHOICE = [(2, _("central")), (3, _("resalat")), ]
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
    wh_destination = models.CharField('wh_destination', choices=WH_DESTINATION_CHOICE, null=True, blank=True)
    sepidar_wh_to_wh = models.JSONField(null=True, blank=True)

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
    wh_receipt_quantity = models.FloatField(null=True, blank=True, verbose_name='تعداد در انبار')

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
    sepidar_buy_factor_response_json = models.JSONField(null=True, blank=True)
    sepidar_inventory_receipt_response_json = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f'ID: {self.pk} ({self.gio_date}) '


class GIOItem(BaseModeWF):
    quantity = models.FloatField(_('quantity'), default=0)
    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='gio_items', verbose_name=_('order'), null=True, blank=True)
    gio = models.ForeignKey(GIO, on_delete=models.DO_NOTHING, related_name='gioitems')
    description = models.TextField(_('description'), null=True, blank=True)

    def is_valid_for_sepidar(self):
        supplier_trade = self.order.supplier_trade
        if supplier_trade and supplier_trade.partyid and supplier_trade.dlref:
            return True

        return self.order.order_payment_items.exists()


class OrderPayment(BaseModeWF):
    from_date = models.DateField(verbose_name=_('form_date'), null=True, blank=True)
    to_date = models.DateField(verbose_name=_('to_date'), null=True, blank=True)
    total_amount = models.FloatField(_('total_amount'))
    description = models.TextField(_('description'), null=True, blank=True)
    currency = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, null=True, blank=True,
                                 related_name='payments')
    exchange_rate = models.FloatField(default=1.0, verbose_name=_('rate'), null=True, blank=True)
    karmozd = models.FloatField(default=0, verbose_name=_('karmozd'))
    karmozd_currency = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, null=True, blank=True,related_name='payments_karmozd')
    bank = models.ForeignKey('ACNT', on_delete=models.DO_NOTHING, verbose_name=_('info_Bank'), null=True, blank=True)
    vendor_party = models.ForeignKey(Supplier, on_delete=models.DO_NOTHING, related_name='vendor_party_payment')
    sepidar_response = models.JSONField(null=True, blank=True)

    @property
    def total_payment(self):
        if self.pk:
            return sum(p.total_amount for p in self.payment_item.all())
        else:
            return 0

    @property
    def total_amount_percent(self):
        return self.total_payment / self.total_amount

    @property
    def total_payment_and_percent(self):
        if self.pk:
            total_payment = self.total_payment
            return total_payment, round((total_payment / self.total_amount) * 100, 2)
        else:
            return 0


class OrderPaymentItemManager(BaseManager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False).order_by('id')


class OrderPaymentItem(BaseModeWF):
    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='order_payment_items', verbose_name=_('order'), null=True, blank=True)
    payment = models.ForeignKey(OrderPayment, on_delete=models.DO_NOTHING, related_name='payment_item', null=True, blank=True)
    from_date = models.DateField(verbose_name=_('form_date'), null=True, blank=True)
    to_date = models.DateField(verbose_name=_('to_date'), null=True, blank=True)
    description = models.TextField(_('description'), null=True, blank=True)
    quantity = models.FloatField(verbose_name='payment_quantity', null=True, blank=True)

    bank = models.ForeignKey('ACNT', on_delete=models.DO_NOTHING, verbose_name=_('info_Bank'), null=True, blank=True)
    destination_currency = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, related_name='destination_currency', null=True, blank=True)
    currency = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, null=True, blank=True, related_name='base_currency')
    exchange_rate = models.FloatField(default=1.0, verbose_name=_('rate'), null=True, blank=True)
    total_amount = models.FloatField(_('total_amount'))

    objects = OrderPaymentItemManager()

    class Meta:
        ordering = ['created_date']


class ACNT(BaseModeWF):
    info_bank = models.CharField(_('info_Bank'), max_length=120)
    currency = models.ForeignKey(Currency, on_delete=models.DO_NOTHING)
    first_amount = models.FloatField(default=0.0)
    is_blocked = models.BooleanField(default=False)
    block_date = models.DateField(null=True, blank=True)
    description = models.TextField(_('description'), null=True, blank=True)
    sepidar_code = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f'{self.info_bank} {self.currency.title_en}'
