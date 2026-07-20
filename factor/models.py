from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q, Value
from django.contrib import messages
from django.db.models import F, Sum, FloatField
from django.db.models.functions import Coalesce

from accounts.models import User
from core.models import BaseModel, BaseManager, BaseModeWF, BaseModel2
from extra_data.models import Item, CustomerAddress, Customer
from core.models import BaseModel, BaseManager, BaseModeWF
from extra_data.models import Item, CustomerAddress
from inquiry.models import CurrencyAmount
from micmod_base.base import SLSDoc, DeliveryTime, PaymentMethod
from micmod_base.models import Quotation, SaleType, QuotationItem, CustomerRequestItem, CustomerRequest
from order.models import Order, OrderOrder, OrderBazar, WhReserve
from tools import const
from tools.utils import show_error, round_rial
from django.utils.dateparse import parse_datetime
from translator import get_text as _
from datetime import datetime
from simple_history.models import HistoricalRecords


class FactorItemManager(BaseManager):
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.order_by('index', 'qi__is_over', 'qi__id')

    def base_qs(self):
        return self.get_queryset().order_by('-index', 'id')


class Factor(SLSDoc):
    is_reserve = models.BooleanField(default=False, verbose_name=_(''))
    customer_party_id = models.ForeignKey(Customer, verbose_name=_('party_id'), null=True, blank=True,
                                          to_field='sepidar_party_id', on_delete=models.DO_NOTHING,
                                          db_column='customer_party_id')
    address = models.ForeignKey(CustomerAddress, on_delete=models.DO_NOTHING, null=True, blank=True, verbose_name=_('address'))
    history = HistoricalRecords()
    DELIVER_TYPE_CHOICES = (('in_person', _('in_person')), ('delivery', _('delivery')))
    q = models.ForeignKey(Quotation, verbose_name=_('پیش فاکتور'), related_name='q', on_delete=models.DO_NOTHING, null=True, blank=True)

    delivery_time = models.CharField(choices=DeliveryTime, max_length=10, null=True, blank=True,
                                     verbose_name=_('delivery_time'), default="2-3 week")
    description = models.TextField(max_length=2000, null=True, blank=True, verbose_name=_('description'))
    guid = models.UUIDField(_('guid'), default=None, editable=False, null=True, blank=True)

    ### sepidar data
    sepidar_number = models.BigIntegerField(_('sepidar_number'), null=True, blank=True)
    sepidar_id = models.BigIntegerField(_('sepidar_id'), null=True, blank=True)
    sepidar_inventory_delivery_number = models.CharField(_('sepidar_inventory_delivery_number'), null=True, blank=True, max_length=64)
    sepidar_inventory_delivery_id = models.CharField(_('sepidar_inventory_delivery_id'), null=True, blank=True, max_length=64)
    sepidar_voucher_number = models.BigIntegerField(_('sepidar_voucher_number'), null=True, blank=True)
    sepidar_voucher_id = models.BigIntegerField(_('sepidar_voucher_id'), null=True, blank=True)
    fiscalyearref = models.SmallIntegerField(_('sepidar_fiscalyearref'), null=True, blank=True)

    workflows = GenericRelation('workflow.Workflow', related_query_name="model")
    factor_self = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='factor_rel', null=True, blank=True)
    self_discount = models.PositiveSmallIntegerField(verbose_name=_('self_discount'), default=0, validators=[MaxValueValidator(100)])
    is_official = models.BooleanField(default=False, verbose_name=_('is_official'))
    official_value = models.FloatField(default=0, verbose_name=_('official_value'), null=True, blank=True)
    cancel = models.BooleanField(default=False, verbose_name=_('cancel'))

    payment_method = models.CharField(choices=PaymentMethod, max_length=10, null=True, blank=True,
                                      verbose_name=_('payment_method'), default="6,2 Month")
    sale_type = models.ForeignKey(SaleType, on_delete=models.DO_NOTHING, related_name='factors')

    need_financial_approval = models.BooleanField(default=True, verbose_name=_('نیاز به تایید مالی'))
    wh_user = models.ManyToManyField(User, related_name='wh_factors', null=True, blank=True, verbose_name=_('کارشناس انبار'))
    to_be_collected = models.BooleanField(default=False, verbose_name=_('جمع‌آوری شود'))
    collecting_start_time = models.DateTimeField(verbose_name=_('زمان شروع جمع‌آوری'), null=True, blank=True)
    collecting_end_time = models.DateTimeField(verbose_name=_('زمان پایان جمع‌آوری'), null=True, blank=True)
    final_check = models.BooleanField(default=False, verbose_name=_('چک نهایی'))
    require_official_factor_with_delivery = models.BooleanField(default=False, verbose_name=_('الزام ارسال فاکتور رسمی همراه بار'))
    official_factor_send_with_this_factor = models.CharField(verbose_name=_('فاکتورهای رسمی ارسال شده(با ویرگول جدا شود)'), max_length=255, null=True, blank=True)
    official_factor_for_this_factor = models.CharField(verbose_name=_('فاکتور رسمی(متعلق به این فاکتور)'), max_length=255, null=True, blank=True)
    deliver_type = models.CharField(max_length=10, null=True, blank=True, choices=DELIVER_TYPE_CHOICES, verbose_name=_('deliver_type'))
    deliver_to_customer = models.BooleanField(default=False, verbose_name=_('تحویل به مشتری'))
    need_factor_document = models.BooleanField(default=False, verbose_name=_('نیاز به اسناد فاکتور'))
    checker = models.ManyToManyField(User, related_name='factor_checker', verbose_name=_('چک کننده'))
    packing_json = models.JSONField(verbose_name=_('packing_json'), default=list, null=True, blank=True)
    customer_request = models.ForeignKey(CustomerRequest, on_delete=models.DO_NOTHING, related_name='customer_factor_items', null=True, blank=True)
    deliver_method = models.ForeignKey('Delivery', related_name='deliver_method', null=True, blank=True, on_delete=models.DO_NOTHING, verbose_name=_('deliver_method'))
    accounting_confirm = models.BooleanField(_('accounting_confirm'), default=False)
    force_factor = models.BooleanField(_('force_factor'), default=False)
    sales_admin_confirm = models.BooleanField(_('sales_admin_confirm'), default=False)
    currency_amount = models.DecimalField(max_digits=14, decimal_places=4, verbose_name=_('rate'), null=True, blank=True)
    request_cancel = models.BooleanField(default=False)
    notify_number = models.CharField(verbose_name=_('notify_number'), max_length=255, null=True, blank=True)

    def is_need_sales_admin_confirmation(self):
        if not self.q:
            return False
        if not self.q.sales_admin_confirm:
            return True

        for fis in self.factoritem_set.select_related('qi'):
            try:
                if fis.qi.fee != fis.price:
                    return True
            except Exception as e:
                pass
        return False

    @classmethod
    def get_qs_count(cls, user):
        return len(cls.objects.get_access_object(user, q='active', quotation=False))

    @classmethod
    def get_qs(cls, request, lst=False, groups_list=None):
        q = request.POST.get('q')
        qs = cls.objects.none()
        base_group = request.user.base_group
        comm_filter = Q(is_deleted=False)
        wh_filter = Q(last_work_flow__current_state_name__in=const.WH_FACTOR_STATES) | Q(wh_user__id__in=[request.user.pk])
        office_filter = Q()
        sales_filter = Q()
        trade_filter = ''
        bazar_filter = ''
        accounting_filter = Q(last_work_flow__current_state_name__in=const.ACCOUNTING_FACTOR_STATES) | Q(checker__id__in=[request.user.pk])

        if base_group == 'wh':
            total_filter = comm_filter & wh_filter
            qs = cls.objects.filter(total_filter).distinct()
        if base_group == 'sales':
            # total_filter = comm_filter & wh_filter
            qs = cls.objects.get_access_object(request.user, q=q, lst=False)
        if base_group == 'trade':
            qs |= Factor.objects.filter()
        if base_group == 'bazar':
            qs |= Factor.objects.filter()
        if base_group == 'accounting':
            qs |= Factor.objects.filter(accounting_filter, need_financial_approval=True)
        if request.user.is_superuser:
            qs |= Factor.objects.filter()
        if base_group == 'office':
            qs |= Factor.objects.filter(office_filter)
        # qs = cls.objects.get_access_object(request.user, q=q, lst=False)
        return qs

    @property
    def payment(self):
        fis = self.factoritem_set.all()
        sum_price = sum((fi.row_price for fi in fis))
        tax = sum([fi.tax for fi in fis])
        discount = sum([fi.discount_value for fi in fis])

        additions = self.q.addition or 0
        total = sum_price + additions - discount + tax


        if self.q.currency_ref.title_en == 'Rial':
            return int(sum_price), int(additions), int(discount), int(tax), int(total)
        return sum_price, additions, discount, tax, total

        # return sum_price

    @property
    def get_price(self):
        obj = Factor.objects.filter(pk=self.pk, factoritem__is_deleted=False).annotate(
            total=Sum(F('factoritem__price') * F('factoritem__quantity'), output_field=FloatField())).first()
        if obj:
            return obj.total
        else:
            return 0

    @property
    def sum_tax(self):
        s = sum([x.tax for x in self.factoritem_set.filter(is_deleted=False)])
        return s

    @property
    def sum_discount(self):
        s = sum([x.discount_value for x in self.factoritem_set.filter(is_deleted=False)])
        return s

    @property
    def is_all_supplied(self):
        try:
            factoritems = (
                self.factoritem_set
                .select_related('supply_locations')
                .all()
            )
            return all(x.supply_locations.is_all_arrival for x in factoritems)
        except Exception as e:
            return False

    @property
    def is_all_supplied2(self):
        wh_supplied = Coalesce(
            Sum(
                'factoritemsupplylocation__quantity',
                filter=Q(
                    factoritemsupplylocation__wh_reserve__isnull=False,
                    factoritemsupplylocation__is_deleted=False,
                ),
            ),
            Value(0.0),
            output_field=FloatField(),
        )

        x = not (
            self.factoritem_set
            .annotate(shortage=F('quantity') - wh_supplied)
            .filter(shortage__gt=0.0001)
            .exists()
        )
        return x


class FactorItem(BaseModel):
    sepidar_id = models.BigIntegerField(null=True, blank=True)
    history = HistoricalRecords()
    supply_locations_choice = ((1, 'انبار'), (2, 'سفارش داخل'), (3, 'س'), (4, ''), (5, ''))
    factor = models.ForeignKey(Factor, on_delete=models.DO_NOTHING, verbose_name=_('factor'))
    qi = models.ForeignKey(QuotationItem, verbose_name=_('qi'), related_name='qi', on_delete=models.DO_NOTHING, null=True, blank=True)
    goods_code = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='factor_goods_code', verbose_name=_('goods_code'), null=True, blank=True)
    part_number_show = models.CharField(max_length=255, verbose_name=_('part_number_show'), null=True, blank=True)
    price = models.FloatField(verbose_name=_('price'), null=True, blank=True)
    index = models.IntegerField(null=True, blank=True, verbose_name=_("index"))
    quantity = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0)], verbose_name=_("quantity"))
    delivery_time = models.CharField(choices=DeliveryTime, max_length=20, null=True, blank=True,
                                     verbose_name=_('delivery_time'))
    custom_price = models.FloatField(_('custom_price'), null=True, blank=True)
    supply_locations = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='factor_items', null=True, blank=True, verbose_name=_('supply_locations'))
    supply_location = models.CharField(null=True, blank=True, verbose_name=_('supply_location'))
    reserve_count = models.FloatField(_('reserve_count'), null=True, blank=True)
    # supply_locations = models.ManyToManyField(Order, through='FactorOrder',
    #                                             related_name='factor_items', null=True, blank=True,
    #                                             verbose_name=_('supply_locations'))
    discount_per_item = models.FloatField(_('discount_per_item'), null=True, blank=True)
    is_bazar = models.BooleanField(_('is_bazar'), default=False)
    customer_request_item = models.ForeignKey(CustomerRequestItem, on_delete=models.DO_NOTHING, null=True, blank=True,
                                              related_name='customer_factor_items')
    description = models.TextField(max_length=2000, null=True, blank=True, verbose_name=_('description'))

    final_amount = models.FloatField(_('final_amount'), null=True, blank=True)
    objects = FactorItemManager()

    def customerdiscountrate(self, row_price, discount):
        """calculate discount rate in % for customer"""
        out = (discount / row_price) * 100
        return round(out, 2)

    @property
    def row_price(self):
        price = self.price or 0
        quantity = self.quantity or 0
        row_price = price * quantity
        return row_price

    def fee_(self):
        return self.price
        iqr = self.qi.quotation_item_rel.all().last()
        if iqr is None:
            return self.price or 0
        if iqr.quotation_item.quotation.currency_ref.title == 'ریال':
            currency_ref = 'RIAL'
        else:
            currency_ref = 'RMB'
        match self.qi.price_method:
            case 'last_sale':
                return iqr.goods_last_price
            case 'last_sale_q':
                return iqr.goods_q_last_price
            case 'price_avg':
                return iqr.goods_avg_price
            case 'sales_admin':
                return self.price
            case 'price_sheet1':
                x = iqr.express_transportation_cost_1 if self.factor.q.currency_ref_id == 1 else iqr.express_transportation_cost_3
                return round_rial(x, currency_ref) if isinstance(x, (int, float)) else 1
            case 'price_sheet2':
                x = iqr.air_transportation_cost_1 if self.factor.q.currency_ref_id == 1 else iqr.air_transportation_cost_3
                return round_rial(x, currency_ref) if isinstance(x, (int, float)) else 1
            case 'price_sheet3':
                x = iqr.sea_transportation_cost_1 if self.factor.q.currency_ref_id == 1 else iqr.sea_transportation_cost_3
                return round_rial(x, currency_ref) if isinstance(x, (int, float)) else 1
            case 'price_market':
                x = iqr.goods_price_market
                return round_rial(x, currency_ref='RIAL') if isinstance(x, (int, float)) else 1

    @property
    def net_price(self):
        try:
            return (self.fee_()) * self.quantity if self.pk and self.fee_() else 0
        except Exception as e:
            return 0
            raise ValueError('قیمت یا تعداد در یکی از ردیف ها اشتباه است')

    @property
    def tax(self):
        try:
            if self.factor.is_official:
                x = (self.net_price - sum(self.discount_tuple)) * (settings.TAX_VALUE / 100)
                currency_title = getattr(self.factor, 'q.currency_ref.title_en', None) or self.factor.currency_ref.title_en
                if currency_title == 'Rial':
                    return int(x)
                return x
            else:
                return 0
        except Exception as e:
            show_error(e, __file__)
            return None

    @property
    def discount_tuple(self):
        try:
            net_price = self.net_price
            row_discount = self.quantity * (self.discount_per_item or 0)
            row_discount_base_percentage = net_price * (self.factor.self_discount / 100) if self.pk else 0
            tax_discount = (net_price - row_discount - row_discount_base_percentage) * (
                    1 - ((100 + settings.TAX_VALUE - self.factor.official_value) / (100 + settings.TAX_VALUE)))
        except Exception as e:
            row_discount = tax_discount = row_discount_base_percentage = 0
        return tax_discount, row_discount_base_percentage, row_discount

    @property
    def discount_value(self):
        x = sum(self.discount_tuple)
        try:
            return int(x)
        except Exception as e:
            print(e)
            return 0



    @property
    def is_wh(self):
        try:
            return True if self.supply_locations.local_sepidar_wh_code else False
        except Exception as e:
            return False

    @property
    def is_order(self):
        try:
            return True if not self.supply_locations.local_sepidar_wh_code else False
        except Exception as e:
            return False

    @property
    def select_wh_reserve(self):
        return self.supply_location and str(self.supply_location).startswith('wh__') and len(str(self.supply_location).split('__')) == 3

    @property
    def select_wh_sepidar(self):
        return self.supply_location and str(self.supply_location).startswith('wh__') and len(str(self.supply_location).split('__')) == 2

    @property
    def select_order(self):
        return self.supply_location and not str(self.supply_location).startswith('wh__')

    def get_sepidar_stock_code_from_selected_supply_location(self):
        # TODO: بعد از تمام شدن فاکتور های قدیمی فقط تابع امن را فراخوانی کن
        try:
            wh_code = self.supply_locations.sepidar_wh_code
            if not wh_code:
                sp = self.supply_location.split('__')
                wh_code = sp[1] if len(sp) >= 2 else 0
        except Exception as e:
            if self.supply_location:
                sp = self.supply_location.split('__')
                wh_code = sp[1] if len(sp) >= 2 else 0
            else:
                return self.get_sepidar_stock_code_from_selected_supply_location_safe
        return wh_code

    @property
    def get_sepidar_stock_code_from_selected_supply_location_safe(self):
        s = set()
        for sl in self.factoritemsupplylocation_set.all():
            if sl.wh_reserve:
                s.add(sl.wh_reserve.sepidar_wh_code)
            else:
                raise ValueError('ارسال به سپیدار انجام نشد. برخی از ردیف ها در انبار رسید نشده اند')

        if None in s:
            raise ValueError('ارسال به سپیدار انجام نشد. برخی از ردیف ها در انبار رسید نشده اند')

        if len(s) > 1:
            raise ValueError('ارسال به سپیدار انجام نشد. برخی از ردیف ها بیش از یک محل تامین دارند.')

        if len(s) == 0:
            raise ValueError('ارسال به سپیدار انجام نشد. برای برخی از ردیف ها محل تامین مشخص نشده است')

        if len(s) == 1:
            x = s.pop()
            return x

        raise ValueError('ارسال به سپیدار انجام نشد. خطا در شناسایی انبار')





    def quantity_for_wh_order(self):
        """calculate quantity base on min(fi.quantity, sepidar_wh_quantity, reserve_quantity)"""
        from sepidar.api_call import SepidarApiCall
        import re
        res = SepidarApiCall.get_stock_quantity([self.goods_code.sepidar_id_0])
        res = res.get('res')
        if res:
            wh_code = self.get_sepidar_stock_code_from_selected_supply_location()
            for name_code, quantity in res.items():
                code = name_code[1]  # re.search(r'(code: (\d+))', code).group(2)
                if int(code) == int(wh_code):
                    x = quantity - self.goods_code.reserved_count_in_portal(wh_code)
                    return min([float(x) if x > 0 else 0, float(self.quantity), (self.reserve_count or 0)])
        else:
            res2 = SepidarApiCall.get_stock_quantity([self.goods_code.sepidar_id_0])
            res2 = res2.get('res')
            if res2:
                wh_code = self.get_sepidar_stock_code_from_selected_supply_location()
                for name_code, quantity in res2.items():
                    code = name_code[1]  # re.search(r'(code: (\d+))', code).group(2)
                    if int(code) == int(wh_code):
                        x = quantity - self.goods_code.reserved_count_in_portal(wh_code)
                        return min([float(x) if x > 0 else 0, float(self.quantity), (self.reserve_count or 0)])
        return 0

    def selected_order(self):
        """
        کدام محل تامینن انتخاب شده است
        """
        unselect = select_order = select_wh = select_bazar = deselect_bazar = None
        if self.is_bazar:
            select_bazar = True
            select_order = select_wh = unselect = False
        elif not self.supply_location:
            unselect = True
            select_order = select_wh = select_bazar = False
        else:
            try:
                if not self.supply_locations and self.supply_location.isdigit():
                    select_order = True
                    unselect = select_wh = select_bazar = False
                elif self.supply_locations and int(self.supply_location) != self.supply_locations.pk:
                    select_order = True
                    unselect = select_wh = select_bazar= False
                elif '__' in self.supply_location:
                    select_wh = True
                    unselect = select_order = select_bazar = False
                else:
                    deselect_bazar = True
            except Exception as e:
                select_wh = True
                unselect = select_order = no_change = False

        return unselect, select_order, select_wh, select_bazar, deselect_bazar

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if False and not self.pk or (self.created_date and self.created_date > parse_datetime("2026-06-16 09:13:00.390205+00")):
            super().save(force_insert, force_update, using, update_fields)
        else:
            with transaction.atomic():
                oo = None
                if not self.reserve_count:
                    self.reserve_count = 0
                unselect, select_order, select_wh, select_bazar, deselect_bazar = self.selected_order()
                if self.pk is None:
                    if not self.quantity:
                        return
                    if unselect or select_bazar:
                        """ایجاد سفارش کامل"""
                        o1 = Order.create_with_rel(factor_item=self)[0]
                        self.supply_locations = o1
                        self.supply_location = o1.pk
                    elif select_order:
                        """ایجاد سفارش کامل"""
                        """ایجاد سفارش میانی به اندازه ظرفیت سفارش انتخاب شده"""
                        o2 = Order.objects.filter(pk=self.supply_location).first()
                        o1 = Order.create_with_rel(o2=o2, factor_item=self)[0]
                        self.supply_locations = o1
                    elif select_wh:

                        quantity = self.quantity_for_wh_order()
                        sepidar_free_quantity = quantity
                        if quantity < self.reserve_count:
                            '''محاسبه تعداد قرض گرفتن از رزرو دیگران'''
                            oo_id = self.extra_data.request.POST.get(f'factoritem_set-{self.extra_data.idx}-reserve_selection') or 0
                            oo = OrderOrder.objects.filter(pk=oo_id).first()
                            available_for_barrow = oo.quantity if oo else 0

                            quantity = min(self.reserve_count, quantity + available_for_barrow)

                            '''تغییر تعداد در سفارش میانی دیگران که رزرو انبار بوده بعد از قرض گرفتن'''
                            if oo:
                                total_barrow = min(abs(self.reserve_count - sepidar_free_quantity), available_for_barrow)
                                oo.quantity -= total_barrow
                                oo.editor_user = self.editor_user
                                oo.save()

                                '''تغییر تعداد در سفارش اصلی دیگران که رزرو انبار بوده بعد از قرض گرفتن'''
                                order_rel = oo.order_rel
                                order_rel.quantity -= total_barrow
                                order_rel.editor_user = self.extra_data.request.user
                                order_rel.save()

                        """ایجاد سفارش کامل"""
                        """ایجاد سفارش میانی به اندازه ظرفیت سفارش انتخاب شده به همراه اطلاعات کد انبار"""

                        """generate order with quantity min(sepidar_wh_quantity, fi.quantity)"""
                        data_base = {
                            "order_title": "رزرو انبار (خودکار توسط سیستم)",
                            # "status": "1",
                            "item": self.qi.goods_code_fk,
                            "production_lead_time": 10,  # self.qi.lead_time,
                            "quantity": quantity,  # self.quantity,
                            "cancel": False,
                            "is_over": False,
                            "qi": self.qi,
                            'commitment_date_to_customer': self.qi.supply_date,
                            "creator_user": self.extra_data.request.user,
                            "editor_user": self.extra_data.request.user,
                            'is_bazar': False,
                            'is_wh': True,
                            'sepidar_wh_code': int(self.supply_location[4:])
                        }
                        o1_as_o2 = Order.create_with_rel(data_base=data_base, factor_item=self)[0]
                        o1, oo = Order.create_with_rel(o2=o1_as_o2, factor_item=self, sepidar_wh_code=int(self.supply_location[4:]), is_wh=True)
                        self.supply_locations = o1
                elif self.pk:
                    if not self.quantity:
                        self.is_deleted = True
                        object_to_delete = dict()
                        object_to_delete['oo'] = []
                        for oo in self.supply_locations.order_base_items.all():
                            object_to_delete['oo'].append(oo)

                        object_to_delete['supply_locations'] = self.supply_locations
                        self.supply_locations = None
                        super().save(force_insert, force_update, using, update_fields)

                        for oo_to_delete in object_to_delete['oo']:
                            oo_to_delete.delete()
                        object_to_delete['supply_locations'].delete()

                        total_quantity, total_quantity_wh = self.qi.total_quantity_in_factor
                        if total_quantity >= self.qi.quantity:
                            self.qi.is_over = True
                        else:
                            self.qi.is_over = False
                        self.qi.save()
                        return

                    if select_bazar:
                        """حذف سفارش هایی میانی و تبدیل سفارش به نوع بازار"""
                        for oo in self.supply_locations.order_base_items.all():
                            oo.delete()
                        self.supply_locations.cancel = False
                        self.supply_locations.is_bazar = True
                        self.supply_locations.item = self.goods_code
                        self.supply_locations.quantity = self.quantity
                        self.supply_locations.extra_data.request = self.extra_data.request
                        self.supply_locations.save()

                    elif unselect:
                        pass
                    elif self.supply_locations.is_bazar and deselect_bazar:
                        self.supply_locations.is_bazar = False
                        self.supply_locations.save()

                    elif select_order:
                        """بروز سفارش کامل"""
                        """ایجاد سفارش میانی به اندازه ظرفیت سفارش انتخاب شده"""
                        o2 = Order.objects.filter(pk=self.supply_location).first()
                        if o2.trade_lock_order:
                            raise ValueError(f'سفارش {o2} توسط بازرگانی شروع شده است و ردیف فاکتور {self.index + 1} قابل تغییر نمیباشد.')
                        o2.item = self.goods_code
                        o2.save()
                        # o1 = Order.create_with_rel(o2=o2, factor_item=self)[0]
                        # self.supply_locations = o1
                    elif select_wh:
                        self.reserve_count = self.quantity
                        oo = self.supply_locations.order_base_items.first()
                        if oo:
                            try:
                                oo.delete()
                            except Exception as e:
                                oo.is_deleted = True
                                oo.save()

                        quantity = self.quantity_for_wh_order()
                        sepidar_free_quantity = quantity
                        if quantity < self.reserve_count:
                            '''محاسبه تعداد قرض گرفتن از رزرو دیگران'''
                            oo_id = self.extra_data.request.POST.get(
                                f'factoritem_set-{self.extra_data.idx}-reserve_selection') or 0
                            oo = OrderOrder.objects.filter(pk=oo_id).first()
                            available_for_barrow = oo.quantity if oo else 0

                            quantity = min(self.reserve_count, quantity + available_for_barrow)

                            '''تغییر تعداد در سفارش میانی دیگران که رزرو انبار بوده بعد از قرض گرفتن'''
                            if oo:
                                total_barrow = min(abs(self.reserve_count - sepidar_free_quantity), available_for_barrow)
                                oo.quantity -= total_barrow
                                oo.editor_user = self.editor_user
                                oo.save()

                                '''تغییر تعداد در سفارش اصلی دیگران که رزرو انبار بوده بعد از قرض گرفتن'''
                                order_rel = oo.order_rel
                                order_rel.quantity -= total_barrow
                                order_rel.editor_user = self.extra_data.request.user
                                order_rel.save()

                        """ایجاد سفارش کامل"""
                        """ایجاد سفارش میانی به اندازه ظرفیت سفارش انتخاب شده به همراه اطلاعات کد انبار"""

                        """generate order with quantity min(sepidar_wh_quantity, fi.quantity)"""
                        data_base = {
                            "order_title": "رزرو انبار (خودکار توسط سیستم)",
                            # "status": "1",
                            "item": self.goods_code,
                            "production_lead_time": 10,  # self.qi.lead_time,
                            "quantity": quantity,  # self.quantity,
                            "cancel": False,
                            "is_over": False,
                            "qi": self.qi,
                            'commitment_date_to_customer': self.qi.supply_date,
                            "creator_user": self.extra_data.request.user,
                            "editor_user": self.extra_data.request.user,
                            'is_bazar': False,
                            'is_wh': True,
                            'sepidar_wh_code': int(self.supply_location[4:])
                        }
                        o1_as_o2 = Order.create_with_rel(data_base=data_base, factor_item=self)[0]
                        o1, oo = Order.create_with_rel(o2=o1_as_o2, factor_item=self,
                                                       sepidar_wh_code=int(self.supply_location[4:]), is_wh=True)
                        self.supply_locations = o1

                        """
                        x = fi.reserve_count - order_rel.quantity
                        order_rel.quantity += x
                        
                        oo = oo.order_base == fi.supply_location
                        oo.quantity = fi.reserve_count
                        """
                        # order_rel = oo.order_rel if oo else None
                        # order_rel.quantity += (self.quantity_for_wh_order() or 0) - (oo.quantity or 0)
                        # oo.quantity += (self.quantity_for_wh_order() or 0) - (oo.quantity or 0)
                        # oo.sepidar_wh_code = self.supply_location.split('__')[1]
                        # order_rel.save()
                        # oo.save()

                super().save(force_insert, force_update, using, update_fields)
                if oo:
                    oo.fi = self
                    oo.save()

                total_quantity, total_quantity_wh = self.qi.total_quantity_in_factor
                if not self.qi.is_over:
                    if total_quantity >= self.qi.quantity:
                        self.qi.is_over = True
                    if self.quantity >= self.qi.quantity:
                        self.qi.is_over = True
                    else:
                        self.qi.is_over = False
                self.qi.save()

    def total_supply(self):
        s = sum([x.quantity for x in self.supply_locations.order_base_items.all()])
        quantity = self.quantity
        div = quantity - s
        status = True if s == quantity else False
        return s, quantity, status, div

    class Meta:
        ordering = ['id']


class FactorOrder(BaseModeWF):
    fi = models.ForeignKey(FactorItem, on_delete=models.DO_NOTHING, null=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, null=True, blank=True)
    quantity = models.FloatField(_('quantity'), default=0)


class FactorItemSupplyLocation(BaseModel2):
    original_source_type = models.CharField(max_length=16, blank=True, null=True)  # warehouse|order|bazar_order
    original_source_id = models.IntegerField(null=True, blank=True)
    fi = models.ForeignKey(FactorItem, on_delete=models.SET_NULL, null=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, null=True, blank=True, related_name='order_fis')
    order_bazar = models.ForeignKey(OrderBazar, on_delete=models.DO_NOTHING, null=True, blank=True, related_name='order_bazar_fis')
    wh_reserve = models.ForeignKey(WhReserve, on_delete=models.DO_NOTHING, null=True, blank=True, related_name='wh_reserve_fis')
    quantity = models.FloatField(_('quantity'))
    wh_receipt_quantity = models.FloatField(null=True, blank=True)  # اگر یک سفارش به چند فاکتور آیتم وصل باشد ممکن است چون بخشی از سفارش در انبار رسید شده همه ردیف فاکتور ها تامین نشوند. ما بر اساس این فیلد متوجه میشویم که چه تعدادی تامین شده
    wh_code = models.PositiveIntegerField(null=True, blank=True)  # همه محل تامین هایی یک ردیف فاکتور در هنگام ارسال به سپیدار باید کد انبار داشته باشند و همه یک کد باشن
    taken_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='taken_by')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['fi', 'order'],
                name='unique_fi_order'
            ),

            models.UniqueConstraint(
                fields=['fi', 'order_bazar'],
                name='unique_fi_order_bazar'
            ),

            models.UniqueConstraint(
                fields=['fi', 'wh_reserve'],
                name='unique_fi_wh_reserve'
            ),
        ]

    @property
    def source_type(self):
        if self.wh_reserve_id:   return 'warehouse'
        if self.order_id:        return 'foreign'
        if self.order_bazar_id:  return 'market'
        return None

    @property
    def source(self):
        return self.wh_reserve or self.order or self.order_bazar


class Delivery(BaseModeWF):
    POST = 'POST'
    TIPAX = 'TIPAX'
    PICKUP = 'PICKUP'
    CUSTOM = 'CUSTOM'
    PAKE = 'PAKE'
    CHAPAR = 'CHAPAR'
    BARBARI = 'BARBARI'
    CUSTOMER_PAKE = 'CUSTOMER_PAKE'
    DELIVERY_TYPE_CHOICES = ((POST, _('Post')), (TIPAX, _('TIPAX')), (PICKUP, _('PICKUP_IN_PERSON')), (CUSTOM, _('CUSTOM')), (PAKE, _('PAKE')), (CHAPAR, 'چاپار'), (BARBARI, 'باربری'), (CUSTOMER_PAKE, 'پیک مشتری'))

    # factor = models.ForeignKey(Factor, on_delete=models.DO_NOTHING, related_name='factor_delivery')
    type = models.CharField(max_length=250, verbose_name=_('delivery_type'), choices=DELIVERY_TYPE_CHOICES)
    base_cost = models.PositiveBigIntegerField(_('base_cost'), default=0)
    extra_cost = models.PositiveBigIntegerField(_('extra_cost'), default=0)
    tracking_number = models.CharField(max_length=250, verbose_name=_('tracking_number'), null=True, blank=True )
    delivery_date = models.DateField(verbose_name=_('delivery_date'), null=True, blank=True)

    def __str__(self):
        return f'{self.get_type_display()}'


