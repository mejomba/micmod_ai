from django.db import models

from translator import get_text as _

from core.models import BaseModel, AbsBaseModel, BaseModeWF


def is_valid(value):
    if not value:
        return False
    if value != value:
        return False
    return True


QTYDis = [-4,-5,-7,-10,-10,-10,-10,-11,-11]
PMDisY = [0,3,6,9,12]
PMDisR = [0,4,8,12,16]
GradeDis = [-3,-2,-1,0,0]
Status = (
    ("New", _('new')),
    ("Pending", _("pending")),
    ("Failed", _("failed")),
    ("Success", _("success")),
)
CustomerGrade = (
    ("-3,Special", _("special")),
    ("-2,A+", _("A+")),
    ("-1,A", _("A")),
    ("0,B", _("B")),
    ("0,C", _("C")),
)
DeliveryTime = (
    ("2-3 week", _("2-3 week")),
    ("3-5 week", _("3-5 week")),
    ("12-14 week", _("12-14 week")),
)
PaymentMethod = (
    ("0,Cash", _("Cash")),
    ("3,1 Month", _("1 Month")),
    ("6,2 Month", _("2 Month")),
    ("9,3 Month", _("3 Month")),
    ("12,4 Month", _("4 Month")),
)
PriceMethod = (
    ("last_sale", _("last_sale")),
    ("last_sale_q", _("last_sale_q")),
    ("price_avg", _("price_avg")),
    ("sales_admin", _("sales_admin")),
    ("price_sheet1", _("price_sheet1")),
    ("price_sheet2", _("price_sheet2")),
    ("price_sheet3", _("price_sheet3")),
    ("price_market", _("price_market")),
)
MarketGrade = (
    ("5,A", "A"),
    ("7,B", "B"),
    ("9,C", "C"),
    ("12,D", "D"),
    ("15,E", "E"),
)




class Currency(models.Model):
    title = models.CharField(_('m-title'), max_length=20)
    title_en = models.CharField(_('m-title_en'), max_length=20)
    sepidar_id = models.IntegerField(_('sepidar_id'),blank=True,null=True)

    def __str__(self):
        return f'{self.title} ({self.title_en})'

    def current_rate(self):
        if exchange_rate := self.exchange_rates.order_by("-date").first():
            return exchange_rate.sell_exchange
        return None


class SLSDoc(BaseModeWF):
    # translations = TranslatedFields(
    currency_ref = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, null=True, blank=True,
                                     verbose_name=_('currency_ref'), default="1")
    rate = models.FloatField(_('rate'), blank=True, null=True)
    total_price = models.FloatField(_('total_price'), null=True, blank=True)
    total_price_in_base_currency = models.BigIntegerField(_('total_price_in_base_currency'), null=True,
                                                          blank=True)
    addition = models.FloatField(_('addition'), null=True, blank=True)
    addition_in_base_currency = models.BigIntegerField(_('addition_in_base_currency'), null=True, blank=True)
    duty = models.FloatField(_('duty'), null=True, blank=True)
    duty_in_base_currency = models.BigIntegerField(_('duty_in_base_currency'), null=True, blank=True)
    tax = models.FloatField(_('tax'), null=True, blank=True)
    tax_in_base_currency = models.BigIntegerField(_('tax_in_base_currency'), null=True, blank=True)
    final_price = models.FloatField(_('final_price'), null=True, blank=True)
    status = models.CharField(_('status'), max_length=10, choices=Status, default="New")
    # )

    class Meta:
        abstract = True


class CurrencyExchange(AbsBaseModel):
    currency = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, verbose_name=_('currency_ref'),related_name="exchange_rates")
    buy_exchange = models.FloatField(verbose_name=_('buy_exchange'))
    sell_exchange = models.FloatField(verbose_name=_('sell_exchange'))
    date = models.DateField(verbose_name='date',auto_now=True)

    @staticmethod
    def rmb_rate():
        return CurrencyExchange.objects.filter(currency__title_en="RMB").order_by("-date")[0]
