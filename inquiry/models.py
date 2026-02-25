from django.contrib.auth.models import Group
from django.db import models
from django.db.models import Count, Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from itertools import chain

from accounts.models import User
from core.models import CHOICE
from tools.utils import c_get, round_price, show_error

from django.template.loader import render_to_string

from micmod_base.base import CurrencyExchange
from micmod_base.base import BaseModel, Currency, AbsBaseModel
from micmod_base.models import QuotationItem
from translator import get_text as _
from queryable_properties.properties import queryable_property
from tools.form_tools import get_dif_percentage
from tools.utils import elapsed_time

from extra_data.models import Item, ItemWeight, PriceSettings, CalculationMethod, CustomerType
from django.utils import timezone
from django.conf import settings as dj_settings

from transportation.models import TradeTransportationMethod


class SupplierCity(AbsBaseModel):
    title = models.CharField(max_length=100, verbose_name=_('title'), unique=True)

    auto_complete = 'title'

    insert_new = True


class Supplier(BaseModel):
    BASEGROUP = (("trade", _('trade')), ('bazar', _('bazar')))
    type = models.CharField(choices=CustomerType.choices, verbose_name=_("type"), max_length=10,
                            default=CustomerType.Company)
    title = models.CharField(max_length=100, verbose_name=_('supplier'), null=True, blank=True, unique=True)
    base_group = models.CharField(verbose_name=_('base_group'), choices=BASEGROUP, max_length=10, default='trade')
    country = models.CharField(verbose_name=_('country'), max_length=255, choices=CHOICE.supplier_country, null=True, blank=True)
    city = models.ForeignKey(SupplierCity,verbose_name=_('city'), on_delete=models.DO_NOTHING, null=True, blank=True)
    # trade_transportation_method = models.ForeignKey(TradeTransportationMethod, verbose_name=_('trade_transportation_method'), on_delete=models.DO_NOTHING, null=True, blank=True)
    trade_transportation_method_json = models.JSONField(_('trade_transportation_method_json'), null=True, blank=True)
    dlref = models.IntegerField(null=True, blank=True, unique=True)
    partyid = models.IntegerField(null=True, blank=True, unique=True)
    maximumcredit = models.BigIntegerField(null=True, blank=True)
    auto_complete = 'title'

    def auto_complete_func(self):
        if request := self.extra_data.c_get('request'):
            user:User = request.user
            if 'bazar_user' in [gn[0] for gn in user.groups.values_list('name')]:
                self.base_group = 'bazar'
                self.save()
        super().auto_complete_func()

    def __str__(self):
        return f'{self.title}'


class PriceInquiryFile(BaseModel):
    TYPE_CHOICE = (('p', _('pre invoice')), ('s', _('sourcing')))
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, verbose_name=_('sku'), related_name='sku_const')
    target = models.CharField(max_length=100, verbose_name=_('target'), null=True, blank=True)
    desired_quality = models.CharField(max_length=100, verbose_name=_('desired quality'), null=True, blank=True)
    demanded_quantity = models.IntegerField(verbose_name=_('demanded quantity'), null=True, blank=True)
    type = models.CharField(max_length=1, choices=TYPE_CHOICE, verbose_name=_('type'), null=True, blank=True)
    brand = models.CharField(max_length=100, verbose_name=_('brand'), null=True, blank=True)

    def __str__(self):
        return f'[{self.id}] :  {self.item} - {self.get_type_display()}'


class PriceInquiryResult(BaseModel):
    sku = models.ForeignKey(Item, on_delete=models.DO_NOTHING, verbose_name=_('sku'), related_name='items', null=True,
                            blank=True)
    price_inquiry_file = models.ForeignKey(PriceInquiryFile, on_delete=models.DO_NOTHING,
                                           verbose_name=_('price inquiry file'), related_name='inquery_result',
                                           null=True, blank=True)
    supplier = models.ForeignKey(Supplier, verbose_name=_('supplier'), null=True, blank=True,
                                 on_delete=models.DO_NOTHING, related_name='supplier_rel')
    price = models.FloatField(verbose_name=_('price'))
    price_update_date = models.DateTimeField(verbose_name=_('price_update_date'), null=True, blank=True, auto_now_add=True)
    # local_price = models.FloatField(verbose_name=_('local_price'), null=True, blank=True)
    description = models.CharField(max_length=255, verbose_name=_('description'), null=True, blank=True)
    currency_type = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, default=2, null=True, blank=True)
    active = models.BooleanField(verbose_name=_('active'), default=False)
    inquiry_type = models.ForeignKey('InquiryResultVariant', on_delete=models.DO_NOTHING, verbose_name=_('inquiry_type'), default=1)
    item_weight = models.FloatField(verbose_name=_('item_weight'), null=True, blank=True)
    variants_json = models.JSONField(_('variants_json'), null=True, blank=True)
    price_expire_date = models.SmallIntegerField(_('price_expire_date'), null=True, blank=True)
    trade_transportation_method = models.ForeignKey(TradeTransportationMethod, verbose_name=_('trade_transportation_method'),
                                                    on_delete=models.DO_NOTHING, null=True, blank=True)
    trade_transportation_method_json = models.JSONField(_('trade_transportation_method_json'), null=True, blank=True)
    address = models.TextField(_("address"), null=True, blank=True)
    lead_time = models.CharField(max_length=32, null=True, blank=True, verbose_name=_('lead_time'))

    # trade_expire = models.SmallIntegerField(default=1000)

    @property
    def variant_show(self):
        l = []
        for k, v in self.variants_json.items() if self.variants_json else []:
            l.append(str(k) + ": " + str(v))
        y = '|'.join(l)
        return f'( {y} )' if y else ''

    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_properties = {
            'quantity_': None,
            'customer_grade_': None,
            'payment_method_': None,
            'currency_': None,
        }

    @property
    def bazar_expire_date(self):
        bazar_expire_delta = timezone.timedelta(days=self.price_expire_date or 3000)
        return self.price_update_date + bazar_expire_delta

    @property
    def is_valid_time(self):
        return True
        from django.utils import timezone
        now = timezone.now()
        try:
            return ((now - self.last_update_date).total_seconds() / 3600) < 72
        except Exception as e:
            return

    @classmethod
    def valid_bazar_inquiry(cls):
        now = timezone.now()
        last_72_hour = (now - timezone.timedelta(hours=72_000), now)  # 3000 days
        bazar_filter = Q(inquiry_type__title__icontains='داخل')
        qs = cls.objects.filter(bazar_filter, active=True, last_update_date__range=last_72_hour)
        return qs

    @property
    def item_sku(self):
        return self.sku.sku

    # price_settings_ = None
    submit_copy = True
    # rmb_final_price_before_ondemand = dict()
    # _rmb_final_price_ = dict()
    # rmb_final_price_before_ondemand_percentage = dict()
    def __str__(self):
        return f'{self.id}: {self.jalali_last_update_date} - {self.sku}'

    @classmethod
    def inquiry_list_datatable(cls, user, param={}):
        qs = cls.objects.filter(**param)
        user_group_names = user.groups.values_list('name', flat=True)
        if user.is_superuser or user.groups.filter(name='total_admin'):
            return qs
        elif user.groups.filter(name='bazar_user') or user.groups.filter(name='bazar_admin'):
            return qs.filter(inquiry_type__base_group='bazar')
        elif user.groups.filter(name='trade_user') or user.groups.filter(name='trade_admin') or user.has_perm("inquiry.add_priceinquiryresult"):
            return qs.filter(inquiry_type__base_group='trade')
        else:
            return cls.objects.none()
        # qq = InquiryResultVariant.objects.filter(Q(base_group_id__in=list(g)) | Q(base_group__isnull=True))
        # return qs.filter(Q(inquiry_type_id__in=qq) | Q(inquiry_type_id__isnull=True))

    @classmethod
    def inquiry_list(cls, user, param):
        if user.base_group == 'sales' or user.is_superuser:
            qs = cls.objects.filter(**param)
            return qs
        else:
            return cls.objects.none()

    @property
    def elapsed_from_last_price(self):
        return elapsed_time(self.price_update_date)

    @property
    def bazar_price(self):
        if self.inquiry_type.base_group == 'bazar':
            payment_method = (self.custom_properties['payment_method_'] or '').lower()
            discount = 0.05
            if payment_method == 'cash':
                discount = 0.07
                if (self.custom_properties['customer_grade_'] or '').lower() in ['a+', 'special']:
                    discount = 0.05
            elif payment_method == '1 month':
                discount = 0.10
            elif payment_method == '2 month':
                discount = 0.12
            elif payment_method == '3 month':
                discount = 0.15
            elif payment_method == '4 month':
                discount = 0.18
            return self.price * (1+discount)
        else:
            return ''


    @property
    def rial_final_price(self):
        if self.inquiry_type.base_group == 'bazar':
            return self.bazar_price
        else:
            if self.sku and self.transportations_cost:
                # self.custom_properties['currency_'] = Currency.objects.filter(title_en="Rial").first() or self.currency_
                free_rmb_rate = self.price_settings.free_rmb_rate
                final_price = self.rmb_final_price
                # final_price = dict(map(lambda x: (x[0], round_price(int(x[1].get('price') * free_rmb_rate))),
                #                        final_price.items()))
                final_price = {k: {**v, 'price': round_price(int(v.get('price', 0) * free_rmb_rate))} for k, v in final_price.items()}
                return final_price

    @property
    def rial_final_price_new_order(self):
        if self.inquiry_type.base_group == 'bazar':
            return self.bazar_price
        else:
            # self.custom_properties['currency_'] = self.currency_ or
            free_rmb_rate_new_order = self.free_rmb_rate_new_order
            # final_price = dict(map(lambda x: (x[0], round_price(int(x[1].get('price') * free_rmb_rate_new_order))),
            #                        self.rmb_final_price.items()))
            final_price = {k: {**v, 'price': round_price(v.get('price', 0) * free_rmb_rate_new_order)} for k, v in self.rmb_final_price.items()}
            return final_price

    @property
    def rmb_final_price(self):
        if self.inquiry_type.base_group == 'bazar':
            return None
        else:
            if not getattr(self.extra_data,'_rmb_final_price_',None):
                return self.rmb_final_price_()
            return self.extra_data._rmb_final_price_

    def rmb_final_price_(self):
        self.currency_ = (Currency.objects.filter(id=self.custom_properties.get('currency_')).first()
                          or Currency.objects.filter(title_en="Rial").first())
        self.transportations_cost_ = self.transportations_cost
        if self.sku and self.transportations_cost_:
            try:
                on_demand_discounts = 0
                quantity_discounts_percentage = 0
                customer_grade_discounts_percentage = 0
                payment_method_discount_percentage = 0
                settings = self.price_settings
                if self.custom_properties.get('quantity_'):
                    quantity_discounts_percentage = settings.get_discount_based_quantity(
                        self.custom_properties.get('quantity_') or 1)
                    on_demand_discounts += quantity_discounts_percentage
                if self.custom_properties.get('customer_grade_'):
                    customer_grade_discounts_percentage = settings.get_discount_based_customer(
                        self.custom_properties.get('customer_grade_'))
                    on_demand_discounts += customer_grade_discounts_percentage
                if self.custom_properties.get('payment_method_') and self.custom_properties.get('currency_'):
                    payment_method_discount_percentage = settings.get_discount_based_payment_method(
                        self.custom_properties.get('payment_method_'),
                        self.currency_)
                    on_demand_discounts += payment_method_discount_percentage
                office_cost_percentage = self.price_settings.office_cost_percentage or 0

                self.extra_data.discount_percentage = {
                    'on_demand_discounts_percentage': on_demand_discounts or 0,
                    'quantity_discounts_percentage': quantity_discounts_percentage or 0,
                    'customer_grade_discounts_percentage': customer_grade_discounts_percentage or 0,
                    'payment_method_discount_percentage': payment_method_discount_percentage or 0,
                    'office_cost_percentage': office_cost_percentage or 0,
                }
                # self.extra_data.after_office_price = (1 + 0.01 * (office_cost_percentage + (self.sku.extra_cost_percentage or 0 if not settings.delivery_in_china else 0 or 0))) * (self.effective_rmb_price or 0+ self.customs_cost or 0)
                self.extra_data.after_office_price = (1 + 0.01 * (office_cost_percentage + (self.sku.extra_cost_percentage or 0 if not settings.delivery_in_china else 0 or 0))) * ((self.effective_rmb_price or 0) + (self.customs_cost or 0))
                self.extra_data.after_price_discount_price = (self.extra_data.after_office_price *
                                                              (1 + 0.01 * (settings.get_discount_based_price(self.extra_data.after_office_price))))
                # self.extra_data.rmb_final_price_custom_office = dict( map(lambda x: (x[0], x[1] + self.extra_data.after_price_discount_price),
                #                                               self.transportations_cost_.items()))
                self.extra_data.rmb_final_price_custom_office = {k: {**v, 'price': v.get('price', 0) + self.extra_data.after_price_discount_price} for k, v in self.transportations_cost_.items()}


                # self.extra_data.rmb_final_price_before_ondemand = dict(
                #     map(lambda x: (x[0], (x[1].get('price') * (1 + 0.01 * (
                #                                         0#settings.get_discount_based_price(x[1])
                #                                         + settings.max_discount_for_final_step
                #                                         + settings.interest_percentage)))),
                #         self.extra_data.rmb_final_price_custom_office.items()))

                self.extra_data.rmb_final_price_before_ondemand = {k: {**v, 'price': (v['price'] * (1 + 0.01 * (
                                                        0#settings.get_discount_based_price(x[1])
                                                        + settings.max_discount_for_final_step
                                                        + settings.interest_percentage)))} for k, v in self.extra_data.rmb_final_price_custom_office.items()}

                # x = TradeTransportationMethod.objects.all()
                # x = TradeTransportationMethod.objects.filter(Q(pk__in=self.trade_transportation_method_json.values()) | Q(access_type__in=dj_settings.PUBLIC_TRADE_TRANSPORTATION_METHOD)) if self.trade_transportation_method_json else TradeTransportationMethod.objects.none()
                # x |= TradeTransportationMethod.objects.filter(access_type__in=dj_settings.PUBLIC_TRADE_TRANSPORTATION_METHOD)
                # if x:
                #     self.extra_data.rmb_final_price_before_ondemand = {TradeTransportationMethod.objects.filter(pk__in=x).get(title=k).method.lower(): v for k, v in self.extra_data.rmb_final_price_before_ondemand.items()}
                # self.extra_data.rmb_final_price_before_ondemand = dict(map(lambda x: (x[0], (x[1] * (1 + 0.01 *
                #                                                             (
                #                                                                 (self.sku.express_extra_cost_percentage or 0 if not settings.delivery_in_china else 0)
                #                                                                             if x[0] == "express" else
                #                                                                 (self.sku.air_extra_cost_percentage or 0 if not settings.delivery_in_china else 0)
                #                                                                             if x[0] == "air" else
                #                                                                 (self.sku.sea_extra_cost_percentage or 0
                #                                                                             if not settings.delivery_in_china else 0)
                #                                                             )
                #                                                                                      )
                #                                                                              )
                #                                                                       ),
                #                                   self.extra_data.rmb_final_price_before_ondemand.items()))
                self.extra_data.rmb_final_price_before_ondemand = {k: {**v, 'price': v.get("price", 0) * (1 + 0.01 *
                                                                            (
                                                                                (self.sku.express_extra_cost_percentage or 0 if not settings.delivery_in_china else 0)
                                                                                            if v.get('method', '').lower() == "express" else
                                                                                (self.sku.air_extra_cost_percentage or 0 if not settings.delivery_in_china else 0)
                                                                                            if v.get('method', '').lower() == "air" else
                                                                                (self.sku.sea_extra_cost_percentage or 0
                                                                                            if not settings.delivery_in_china else 0)
                                                                            )
                                                                                                     )} for k, v in self.extra_data.rmb_final_price_before_ondemand.items()}


                # self.extra_data._rmb_final_price_ = dict(map(lambda x: (x[0], (x[1] * (1 + 0.01 * on_demand_discounts))),
                #                                   self.extra_data.rmb_final_price_before_ondemand.items()))
                self.extra_data._rmb_final_price_ = {k: {**v, 'price': v.get("price", 0) * (1 + 0.01 * on_demand_discounts)} for k, v in self.extra_data.rmb_final_price_before_ondemand.items()}

                # self.extra_data.rmb_final_price_custom_office_percentage = dict(
                #     map(lambda x: (x[0], 100 * x[1] / self.rmb_price - 100),
                #         self.extra_data.rmb_final_price_custom_office.items()))
                self.extra_data.rmb_final_price_custom_office_percentage = {k: {**v, 'percentage': 100 * v.get("price", 0) / self.rmb_price - 100} for k, v in self.extra_data.rmb_final_price_custom_office.items()}

                self.extra_data.rmb_final_price_before_ondemand_percentage = get_dif_percentage(self.extra_data.rmb_final_price_before_ondemand,
                                                                                     self.extra_data.rmb_final_price_custom_office)
                self.extra_data.rmb_final_price_percentage = get_dif_percentage(self.extra_data._rmb_final_price_,
                                                                     self.extra_data.rmb_final_price_custom_office)

                # d = dict()
                # for item in x:
                #     if item.method.lower() in self.extra_data._rmb_final_price_:
                #         d[item.title.lower()] = self.extra_data._rmb_final_price_.get(item.method.lower())

                # if d:
                #     self.extra_data._rmb_final_price_ = d
                return self.extra_data._rmb_final_price_
            except Exception as e:
                show_error(e, __file__)
                return 0

    @staticmethod
    def select_title(title):
        if title.lower() == 'express':
            return "2-3 هفته"
        elif title.lower() == 'air':
            return "3-5 هفته"
        elif title.lower() == 'sea':
            return "12-14 هفته"

    def rial_final_price_rendered(self):
        return render_to_string('inquiry/partial/item_price_irr.html',
                                {"data": "rial_final_price", "obj": self, 'detail': True})

    def rmb_final_price_rendered(self):
        return render_to_string('inquiry/partial/item_price_irr.html',
                                {"data": "rmb_final_price", "obj": self, 'detail': True})

    rial_final_price_rendered.allow_tags = True
    rmb_final_price_rendered.allow_tags = True

    def set_discount_params(self, quantity=None, customer_grade=None, payment_method=None, currency=None,
                            price_setting=None):
        if price_setting:
            self.extra_data.price_settings_ = price_setting
        self.custom_properties['quantity_'] = quantity or 1
        if customer_grade:
            self.custom_properties['customer_grade_'] = customer_grade
        if payment_method:
            self.custom_properties['payment_method_'] = payment_method
        self.custom_properties['currency_'] = currency or "1"
        self.rmb_final_price_()
        # return self

    @property
    def price_settings(self):
        if getattr(self.extra_data,'price_settings_', None):
            return self.extra_data.price_settings_
        if self.sku:
            self.extra_data.price_settings_ = None
            if self.sku.price_settings:
                self.extra_data.price_reference = self.sku
                self.extra_data.price_settings_ = self.sku.price_settings
            if self.sku.purchase_group:
                if self.sku.purchase_group.price_settings:
                    self.extra_data.price_reference = self.sku.purchase_group
                    self.extra_data.price_settings_ = self.sku.purchase_group.price_settings
                # elif self.sku.purchase_group.hs and self.sku.purchase_group.hs.price_settings:
                elif self.sku.active_hs and self.sku.active_hs.price_settings:
                    # self.extra_data.price_reference = self.sku.purchase_group.hs
                    # self.extra_data.price_settings_ = self.sku.purchase_group.hs.price_settings
                    self.extra_data.price_reference = self.sku.active_hs
                    self.extra_data.price_settings_ = self.sku.active_hs.price_settings
        if not self.extra_data.price_settings_:
            self.extra_data.price_reference = None
            self.extra_data.price_settings_ = PriceSettings.setting()

        return self.extra_data.price_settings_

    @price_settings.setter
    def price_settings(self, value):
        self.extra_data.price_settings_ = value

    @queryable_property
    def weight(self):
        # if item := self.sku.item_weights.order_by('-creator_user__groups__name', '-created_date').first():
        if item := self.sku.item_weights.filter(creator_user__isnull=False).order_by('-creator_user__groups__name', '-created_date').first():
            return item.weight

    @weight.filter
    @classmethod
    def weight(cls, lookup, value):
        if lookup != 'exact':  # Only allow equality checks for the simplicity of the example
            raise NotImplementedError()
        # Don't implement any validation to keep the example simple.
        major, minor = value.split('.')
        return Q(major=major, minor=minor)

    @property
    def free_rmb_rate_new_order(self):
        return self.price_settings.free_rmb_rate_new_order  # CurrencyExchange.rmb_rate().sell_exchange

    @queryable_property
    def rmb_price(self):
        if self.currency_type.c_get("title_en","RMB") == "RMB":
            return self.price or 0
        else:
            return self.price_settings.dollar_rmb_rate * self.price

    @queryable_property
    def effective_rmb_price(self):
        if self.price_settings.calculation_method == CalculationMethod.Old:
            return self.rmb_price
        free_rmb_rate = self.price_settings.free_rmb_rate
        talar_rmb_rate = self.price_settings.talar_rmb_rate
        # customs_price = self.sku.get_customs_price
        # customs_price = self.rmb_price
        rmb_price = self.rmb_price
        customs_price = self.sku.get_customs_price or rmb_price

        if rmb_price >= customs_price:
            return (customs_price * talar_rmb_rate + (rmb_price - customs_price) * free_rmb_rate) / free_rmb_rate
        else:
            return rmb_price * talar_rmb_rate / free_rmb_rate

    @queryable_property
    def transportations_cost(self):
        trade_transportation_method_json = self.trade_transportation_method_json # or self.sku.trade_transportation_method_json or self.supplier.trade_transportation_method_json or self.sku.purchase_group.trade_transportation_method_json
        trade_transportation_method_obj = TradeTransportationMethod.objects.filter(pk__in=trade_transportation_method_json.values()) if trade_transportation_method_json else None
        if not trade_transportation_method_obj:
            if not self.sku or not self.sku.purchase_group or not self.sku.active_hs or not self.weight:
                return
            trade_transportation_method_obj = TradeTransportationMethod.objects.filter(access_type__in=dj_settings.PUBLIC_TRADE_TRANSPORTATION_METHOD)
            out = {}
            for item in trade_transportation_method_obj:
                currency_type = item.currency_type.title_en
                if currency_type.lower() == 'rmb':
                    rmb = item.variable_cost + item.fixed_cost
                elif currency_type.lower() == 'dollar':
                    rmb = (item.variable_cost + item.fixed_cost) * self.price_settings.dollar_rmb_rate
                elif currency_type.lower() == 'ero':
                    rmb = (item.variable_cost + item.fixed_cost) * self.price_settings.dollar_rmb_rate
                elif currency_type.lower() == 'rial':
                    rmb = (item.variable_cost + item.fixed_cost) / self.price_settings.customs_rmb_rate

                out.update({item.title: {'price': rmb * self.weight / 1000,
                                         'method': item.method,
                                         'duration': 'xxxx'}
                            })

            cost_multiplier = 1/self.price_settings.free_rmb_rate if self.price_settings.calculation_method == CalculationMethod.Old else 1
            weight = self.weight
            settings = self.price_settings
            effective_rmb_price = self.rmb_price
            if self.supplier and self.supplier.country == 'CHN':
                # return {
                #     "air": cost_multiplier * (self.sku.purchase_group.air_transportation or 1) * settings.air_transportation_cost * weight / 1000,
                #     "sea": cost_multiplier * (self.sku.purchase_group.sea_transportation or 1) * settings.sea_transportation_cost * weight / 1000,
                # }
                out.update({
                    "air": {'price': cost_multiplier * (self.sku.purchase_group.air_transportation or 1) * settings.air_transportation_cost * weight / 1000,
                            'method': "air",
                            'duration': '3-5 هفته'},
                    "sea": {'price': cost_multiplier * (self.sku.purchase_group.sea_transportation or 1) * settings.sea_transportation_cost * weight / 1000,
                            'method': "sea",
                            'duration': '12-14 هفته'}
                })
            elif self.supplier and self.supplier.country == 'HKG':
                # return {
                #     "express": cost_multiplier * (self.sku.purchase_group.express_transportation or 1) * settings.express_transportation_cost * weight / 1000,
                #     "sea": cost_multiplier * (self.sku.purchase_group.sea_transportation or 1) * settings.sea_transportation_cost * weight / 1000,
                # }
                out.update( {
                    "express": {'price': cost_multiplier * (self.sku.purchase_group.express_transportation or 1) * settings.express_transportation_cost * weight / 1000,
                                'method': "express",
                                'duration': '2-3 هفته'},
                    "sea": {'price': cost_multiplier * (self.sku.purchase_group.sea_transportation or 1) * settings.sea_transportation_cost * weight / 1000,
                            'method': "sea",
                            'duration': '12-14 هفته'}
                })
            elif self.currency_type.c_get("title_en", "RMB") == "RMB":
                # return {
                #     "air": cost_multiplier * (self.sku.purchase_group.air_transportation or 1) * settings.air_transportation_cost * weight / 1000,
                #     "sea": cost_multiplier * (self.sku.purchase_group.sea_transportation or 1) * settings.sea_transportation_cost * weight / 1000,
                # }
                out.update( {
                    "air": {'price': cost_multiplier * (self.sku.purchase_group.air_transportation or 1) * settings.air_transportation_cost * weight / 1000,
                                'method': "air",
                                'duration': '3-5 هفته'},
                    "sea": {'price': cost_multiplier * (self.sku.purchase_group.sea_transportation or 1) * settings.sea_transportation_cost * weight / 1000,
                            'method': "sea",
                            'duration': '12-14 هفته'}
                })
            else:
                # return {
                #     "express": cost_multiplier * (self.sku.purchase_group.express_transportation or 1) * settings.express_transportation_cost * weight / 1000,
                #     "sea": cost_multiplier * (self.sku.purchase_group.sea_transportation or 1) * settings.sea_transportation_cost * weight / 1000,
                # }
                out.update( {
                    "express": {'price': cost_multiplier * (self.sku.purchase_group.express_transportation or 1) * settings.express_transportation_cost * weight / 1000,
                                'method': "express",
                                'duration': '2-3 هفته'},
                    "sea": {'price': cost_multiplier * (self.sku.purchase_group.sea_transportation or 1) * settings.sea_transportation_cost * weight / 1000,
                            'method': "sea",
                            'duration': '12-14 هفته'}
                })

            return out
        else:
            # trade_transportation_method_obj |= TradeTransportationMethod.objects.filter(access_type__isnull=False)
            trade_transportation_method_obj |= TradeTransportationMethod.objects.filter(access_type__in=dj_settings.PUBLIC_TRADE_TRANSPORTATION_METHOD)
            out = {}
            for item in trade_transportation_method_obj:
                transportation_cost_multiplier = getattr(self.sku.purchase_group,f"{item.method.lower()}_transportation", 1) or 1
                currency_type = item.currency_type.title_en
                if currency_type.lower() == 'rmb':
                    rmb = item.variable_cost + item.fixed_cost
                elif currency_type.lower() == 'dollar':
                    rmb = (item.variable_cost + item.fixed_cost) * self.price_settings.dollar_rmb_rate
                elif currency_type.lower() == 'ero':
                    rmb = (item.variable_cost + item.fixed_cost) * self.price_settings.dollar_rmb_rate
                elif currency_type.lower() == 'rial':
                    rmb = (item.variable_cost + item.fixed_cost) / self.price_settings.customs_rmb_rate

                out.update({item.title: {'price': transportation_cost_multiplier * rmb * self.weight / 1000,
                                         'method': item.method,
                                         'duration': 'xxxx'}
                            })
            return out

    @queryable_property
    def customs_cost(self):
        settings = self.price_settings
        if settings.calculation_method == CalculationMethod.Old:
            return 0
        free_rmb_rate = settings.free_rmb_rate
        customs_rmb_rate = settings.customs_rmb_rate
        if settings.calculation_method == CalculationMethod.Old:
            customs_price = self.rmb_price
        else:
            customs_price = self.sku.get_customs_price if self.sku.get_customs_price > 0 else self.rmb_price
        # self.customs_rate = self.sku.purchase_group.hs.customs_rate
        self.customs_rate = self.sku.active_hs.customs_rate
        return 0.01 * (
                settings.duty_on_value_percentage + self.customs_rate) * customs_price * customs_rmb_rate / free_rmb_rate

    class Meta:
        ordering = 'created_date',

    def deactivate_other(self):
        condition = None
        if p := self.price_inquiry_file:
            sku = p.item
            result = [pif.inquery_result.all() for pif in sku.sku_const.all()]
            r2 = PriceInquiryResult.objects.filter(sku=sku)
            result.append(r2)
            result = list(chain(*result))
            for res in result:
                condition = self.variants_json == res.variants_json
                if (self.active and self != res and self.inquiry_type == res.inquiry_type) and condition:
                    res.active = False
                    res.save()
        else:
            sku = self.sku
            result = [pif.inquery_result.all() for pif in sku.sku_const.all()]
            r2 = PriceInquiryResult.objects.filter(sku=sku)
            result.append(r2)
            result = list(chain(*result))
            for res in result:
                condition = self.variants_json == res.variants_json
                if (self.active and self != res and self.inquiry_type == res.inquiry_type and res.active) and condition:
                    res.active = False
                    res.save()

    def save(self, *args, **kwargs):
        # deactivate other PriceInquiryFile
        if self.price_inquiry_file and self.active:
            self.deactivate_other()
        elif self.active:
            print(self.sku)
            self.deactivate_other()
        print('=== save inquiry result === ')
        if self.price_inquiry_file:
            print('=== IF: ', self.sku, self.price_inquiry_file.item)
            self.sku = self.price_inquiry_file.item
        elif not self.sku:
            print('=== else: ', self.sku)
            raise ValueError('فیلد اجباری')

        super().save(*args, **kwargs)


class SalesPriceInqueryLog(AbsBaseModel):
    sku = models.ForeignKey(Item, related_name="sales_price_inquery", verbose_name=_('sku'),
                            on_delete=models.DO_NOTHING)
    quantity = models.FloatField(verbose_name=_('quantity'), blank=True, null=True)
    grade = models.CharField(verbose_name=_('grade'), max_length=30, blank=True, null=True)
    payment_method = models.CharField(verbose_name=_('payment_method'), max_length=30, blank=True, null=True)
    currency = models.ForeignKey(Currency, verbose_name=_('currency'), on_delete=models.DO_NOTHING, blank=True,
                                 null=True)
    price_setting = models.ForeignKey(PriceSettings, verbose_name=_('price_setting'), on_delete=models.DO_NOTHING,
                                      blank=True, null=True)
    party_code = models.CharField(verbose_name=_('party_code'), blank=True, null=True, max_length=20)


class InquiryResult(AbsBaseModel):
    #  استعلام از گوگل شیت
    # goods_sheet_date = models.DateField(null=True, blank=True, verbose_name=_("goods_sheet_date"))
    # goods_price_sheet1 = models.FloatField(null=True, blank=True, verbose_name=_("goods_price_sheet"))
    # goods_price_sheet2 = models.FloatField(null=True, blank=True, verbose_name=_("goods_price_sheet"))
    # goods_price_sheet3 = models.FloatField(null=True, blank=True, verbose_name=_("goods_price_sheet"))

    price_inquiry_result = models.ForeignKey(PriceInquiryResult, on_delete=models.DO_NOTHING, null=True, blank=True)

    #  استعلام از بازار
    goods_price_market = models.FloatField(null=True, blank=True, verbose_name=_("goods_price_market"))
    goods_market_date = models.DateField(null=True, blank=True, verbose_name=_("goods_market_date"))

    #  قیمت ۶۰ روز اخیر
    goods_avg_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_avg_price"))
    goods_min_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_min_price"))
    goods_max_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_max_price"))

    #  آخرین فروش به مشتری (فاکتور)
    goods_last_sale = models.DateField(null=True, blank=True, verbose_name=_("goods_last_sale"))
    goods_total_sales = models.FloatField(null=True, blank=True, verbose_name=_("goods_total_sales"))
    goods_last_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_last_price"))

    #  آخرین فروش به مشتری (پیش فاکتور)
    goods_q_last_sale = models.DateField(null=True, blank=True, verbose_name=_("goods_last_sale_q"))
    goods_q_total_sales = models.FloatField(null=True, blank=True, verbose_name=_("goods_total_sales_q"))
    goods_q_last_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_last_price_q"))

    #  موجودی انبار
    stock_amount = models.FloatField(null=True, blank=True)
    stock_amount_res = models.FloatField(null=True, blank=True)

    #  express - air - sea (1) => 7200
    #  ۹ تا از این ها نگه دار ۳ تا برای ۷۲۰۰ و ۳ تا برای ۷۴۰۰ و سه تا برای rmb_final_price همونی که ۳ تا قیمت برمیگردونه
    express_transportation_cost_1 = models.FloatField(verbose_name=_('express_transportation_cost_1'), null=True,
                                                      blank=True)
    air_transportation_cost_1 = models.FloatField(verbose_name=_('air_transportation_cost_1'), null=True, blank=True)
    sea_transportation_cost_1 = models.FloatField(verbose_name=_('sea_transportation_cost_1'), null=True, blank=True)

    #  express - air - sea (2) => 7400
    express_transportation_cost_2 = models.FloatField(verbose_name=_('express_transportation_cost_2'), null=True,
                                                      blank=True)
    air_transportation_cost_2 = models.FloatField(verbose_name=_('air_transportation_cost_2'), null=True, blank=True,)
    sea_transportation_cost_2 = models.FloatField(verbose_name=_('sea_transportation_cost_2'), null=True, blank=True)

    #  express - air - sea (3) => transportations_cost
    express_transportation_cost_3 = models.FloatField(verbose_name=_('express_transportation_cost_3'), null=True,
                                                      blank=True)
    air_transportation_cost_3 = models.FloatField(verbose_name=_('air_transportation_cost_3'), null=True, blank=True)
    sea_transportation_cost_3 = models.FloatField(verbose_name=_('sea_transportation_cost_3'), null=True, blank=True)

    inquiry_price_json = models.JSONField(null=True, blank=True)

    quotation_item = models.ForeignKey(QuotationItem, on_delete=models.SET_NULL, related_name='quotation_item_rel',
                                       null=True, blank=True)
    sales_price_inquery_log = models.ForeignKey(SalesPriceInqueryLog, on_delete=models.DO_NOTHING,
                                                related_name='sales_price_inquery_log_rel', null=True, blank=True)
    price_settings = models.ForeignKey(PriceSettings, on_delete=models.DO_NOTHING, related_name='price_settings_rel',
                                       blank=True, null=True)
    price_update_date = models.DateField(null=True, blank=True, verbose_name=_('price update date'))

    # Todo `FK to -> bazar-price, price` -> priceInquiryResult

# @receiver(post_save, sender=PriceInquiryResult)
# def deactivate_prev_inquiry_result(sender, instance, created, **kwargs):
#     sku = instance.price_inquiry_file.item
#     result = [pif.inquery_result.all() for pif in sku.sku_const.all()]
#     result = list(chain(*result))
#     for res in result:
#         if instance.active and instance != res:
#             res.active = False
#             res.save()


class InquiryResultVariant(AbsBaseModel):
    BASEGROUP = (("trade", _('trade')), ('bazar', _('bazar')))
    title = models.CharField(max_length=100, verbose_name=_('variant_title'))
    value = models.CharField(max_length=100, verbose_name=_('value'))
    base_group = models.CharField(verbose_name=_('base_group'), choices=BASEGROUP, max_length=10, default='trade')

    def __str__(self):
        return f'{self.value}'


class AllowedInquiry(BaseModel):
    title = models.CharField(max_length=255, verbose_name=_('title'))

    def __str__(self):
        return f'{self.title}'


class CurrencyAmount(BaseModel):
    currency = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, related_name='currency_amount')
    # customs = models.DecimalField(max_digits=14, decimal_places=4, verbose_name=_('customs'))
    open_rate = models.DecimalField(max_digits=14, decimal_places=4, verbose_name=_('rate'))
    # new_order = models.DecimalField(max_digits=14, decimal_places=4, verbose_name=_('new_order'))
    # talar = models.DecimalField(max_digits=14, decimal_places=4, verbose_name=_('talar'))

    def __str__(self):
        return f'{self.currency.title}({self.currency.title_en})'
