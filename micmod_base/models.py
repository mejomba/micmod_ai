import uuid

from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MaxValueValidator
# from django.contrib.auth.models import User
from accounts.models import User
from django.db import models
from django.conf import settings
from accounts.templatetags.accounts_tag import has_groups,has_permission
from tools.utils import show_error

from translator import get_text as _
# Create your models here.
from .base import SLSDoc, CustomerGrade, DeliveryTime, PaymentMethod, MarketGrade, BaseModel, PriceMethod


class QuotationManager(models.Manager):
    def own_quotations(self, request):
        has_permission(request.user,"")
        if has_groups(request.user, "total_admin,sales_admin"):
            return self.all()
        else:
            return self.filter(creator_user=request.user)


class Quotation(SLSDoc):
    # translations = TranslatedFields(
    customer_party_id = models.IntegerField(verbose_name=_('party_id'), null=True, blank=True)
    request_date = models.DateField(null=False, blank=False, verbose_name=_('request_date'))
    expiration_date = models.DateField(null=True, blank=True, verbose_name=_('expiration_date'))
    customer_code = models.CharField(max_length=20, null=True, blank=True, verbose_name=_('customer_code'))
    customer_grade = models.CharField(choices=CustomerGrade, max_length=10, null=True, blank=True,
                                      verbose_name=_('customer_grade'), default="-1,A")
    delivery_time = models.CharField(choices=DeliveryTime, max_length=10, null=True, blank=True,
                                     verbose_name=_('delivery_time'), default="2-3 week")
    payment_method = models.CharField(choices=PaymentMethod, max_length=10, null=True, blank=True,
                                      verbose_name=_('payment_method'), default="6,2 Month")
    market_grade = models.CharField(choices=MarketGrade, max_length=10, null=True, blank=True,
                                    verbose_name=_('market_grade'), default="5,A")
    description = models.CharField(max_length=200, null=True, blank=True, verbose_name=_('description'))
    guid = models.UUIDField(_('guid'), default=None, editable=False, null=True, blank=True)
    sepidar_quotation_id = models.BigIntegerField(_('sepidar_quotation_id'), null=True, blank=True)
    sepidar_number = models.BigIntegerField(_('sepidar_number'), null=True, blank=True)

    workflows = GenericRelation('workflow.Workflow', related_query_name="model")
    quotation_self = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='quotation_rel', null=True, blank=True)
    self_discount = models.PositiveSmallIntegerField(verbose_name=_('self_discount'), default=0, validators=[MaxValueValidator(100)])
    is_official = models.BooleanField(default=False, verbose_name=_('is_official'))
    official_value = models.PositiveSmallIntegerField(default=0, verbose_name=_('official_value'), null=True, blank=True)
    cancel = models.BooleanField(default=False, verbose_name=_('cancel'))


    custom_objects = QuotationManager()

    @property
    def price(self):
        try:
            return sum(x.price for x in self.quotation.all())
        except Exception as e:
            show_error(e, __file__)
            return None

    def __str__(self):
        return str(self.id)

    class Meta:
        verbose_name = _("t-quotation")

    @property
    def get_inquiry_result_count(self):
        if self.pk:
            all_q = self.quotation.all()
            all_count = all_q.count()
            local_inquiry_count = all_q.filter(need_local_price_inquiry=True).count()
            local_inquiry_done_count = all_q.filter(local_price_inquiry_done=True).count()
            foreign_inquiry_count = all_q.filter(need_foreign_price_inquiry=True).count()
            foreign_inquiry_done_count = all_q.filter(foreign_price_inquiry_done=True).count()
            return all_count, local_inquiry_count, local_inquiry_done_count, foreign_inquiry_count, foreign_inquiry_done_count
        else:
            return


class QuotationItem(BaseModel):
    quotation = models.ForeignKey(Quotation, on_delete=models.DO_NOTHING, related_name='quotation',
                                  verbose_name=_('quotation'))
    created_date = models.DateTimeField(_('create_date'), auto_now_add=True)
    last_update_date = models.DateTimeField(_('last_update_date'), auto_now=True)
    editor_user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True, blank=True, related_name='editor',
                                    verbose_name=_('editor'))
    index = models.IntegerField(null=True, blank=True, verbose_name=_("index"))
    customer_goods_name = models.CharField(null=True, blank=True, verbose_name=_("customer_goods_name"),
                                           max_length=200)
    customer_goods_code = models.CharField(null=True, blank=True, verbose_name=_("customer_goods_code"), max_length=100)
    quantity = models.BigIntegerField(null=True, blank=True, verbose_name=_("quantity"))
    delivery_time = models.CharField(choices=DeliveryTime, max_length=20, null=True, blank=True,
                                     verbose_name=_('delivery_time'))
    goods_code = models.CharField(null=True, blank=True, verbose_name=_("goods_code"), max_length=20)
    itemid = models.BigIntegerField(null=True, blank=True, verbose_name=_("itemid"))
    goods_name = models.CharField(null=True, blank=True, verbose_name=_("goods_name"), max_length=200)
    stock_amount = models.BigIntegerField(null=True, blank=True, verbose_name=_("stock_amount"))
    stock_amount_res = models.BigIntegerField(null=True, blank=True, verbose_name=_("stock_amount_res"))
    stock_json = models.JSONField(null=True, blank=True, verbose_name=_("stock_json"))
    goods_sheet_date = models.DateField(null=True, blank=True, verbose_name=_("goods_sheet_date"))
    goods_price_sheet1 = models.FloatField(null=True, blank=True, verbose_name=_("goods_price_sheet"))
    goods_price_sheet2 = models.FloatField(null=True, blank=True, verbose_name=_("goods_price_sheet"))
    goods_price_sheet3 = models.FloatField(null=True, blank=True, verbose_name=_("goods_price_sheet"))
    goods_price_market = models.FloatField(null=True, blank=True, verbose_name=_("goods_price_market"))
    goods_market_date = models.DateField(null=True, blank=True, verbose_name=_("goods_market_date"))
    goods_avg_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_avg_price"))
    goods_min_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_min_price"))
    goods_max_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_max_price"))
    goods_avg_count = models.FloatField(null=True, blank=True, verbose_name=_("goods_avg_count"))

    goods_code_alt = models.CharField(null=True, blank=True, verbose_name=_("goods_code_alt"), max_length=20)
    goods_name_alt = models.CharField(null=True, blank=True, verbose_name=_("goods_name"), max_length=200)
    goods_last_sale = models.DateField(null=True, blank=True, verbose_name=_("goods_last_sale"))
    goods_last_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_last_price"))
    goods_total_sales = models.FloatField(null=True, blank=True, verbose_name=_("goods_total_sales"))

    goods_q_last_sale = models.DateField(null=True, blank=True, verbose_name=_("goods_last_sale_q"))
    goods_q_last_price = models.FloatField(null=True, blank=True, verbose_name=_("goods_last_price_q"))
    goods_q_total_sales = models.FloatField(null=True, blank=True, verbose_name=_("goods_total_sales_q"))

    price_method = models.CharField(choices=PriceMethod, max_length=20, default="last_sale",
                                    verbose_name=_('price_method'))
    final_price = models.FloatField(null=True, blank=True, verbose_name=_("final_price"))

    need_foreign_price_inquiry = models.BooleanField(verbose_name=_('need_foreign_price_inquiry'), default=False)
    foreign_price_inquiry_done = models.BooleanField(verbose_name=_('foreign_price_inquiry_done'), default=False)
    need_local_price_inquiry = models.BooleanField(verbose_name=_('need_local_price_inquiry'), default=False)
    local_price_inquiry_done = models.BooleanField(verbose_name=_('local_price_inquiry_done'), default=False)

    description = models.CharField(max_length=200, null=True, blank=True, verbose_name=_('description'))

    @property
    def local_pending(self):
        return self.need_local_price_inquiry != self.local_price_inquiry_done

    @property
    def foreign_pending(self):
        return self.need_foreign_price_inquiry != self.foreign_price_inquiry_done

    def fee_(self):
        iqr = self.quotation_item_rel.all().last()
        match self.price_method:
            case 'last_sale':
                return iqr.goods_last_price
            case 'last_sale_q':
                return iqr.goods_q_last_price
            case 'price_avg':
                return iqr.goods_avg_price
            case 'sales_admin':
                return self.final_price
            case 'price_sheet1':
                return iqr.express_transportation_cost_1 if self.quotation.currency_ref_id == 1 else iqr.express_transportation_cost_3
            case 'price_sheet2':
                return iqr.air_transportation_cost_1 if self.quotation.currency_ref_id == 1 else iqr.air_transportation_cost_3
            case 'price_sheet3':
                return iqr.sea_transportation_cost_1 if self.quotation.currency_ref_id == 1 else iqr.sea_transportation_cost_3
            case 'price_market':
                return iqr.goods_price_market

    @property
    def fee(self):
        if self.quotation.is_official:
            total_ = (100 - (self.quotation.official_value + self.quotation.self_discount)) / 100
        else:
            total_ = (100 - self.quotation.self_discount) / 100
        return self.fee_() * total_

    @property
    def price(self):
        try:
            if self.quotation.is_official:
                return self.fee * self.quantity * 1.09
            else:
                return self.fee * self.quantity
        except Exception as e:
            show_error(e, __file__)
            return None

    class Meta:
        ordering = ['id']
