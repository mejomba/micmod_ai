from django.db import models
from core.models import AbsBaseModel, BaseModeWF
from translator import get_text as _


class PaymentOrder(BaseModeWF):
    SOURCE_CHOICES = (('1','تنخواه مالی'), ('2', 'پرداخت مستقیم'))
    request_date = models.DateField(verbose_name=_('request_date'))
    payment_date = models.DateField(verbose_name=_('payment_date'), null=True, blank=True)
    amount = models.PositiveBigIntegerField(verbose_name=_('amount'), default=1)
    behalf = models.CharField(verbose_name=_('for_'), max_length=255)
    pay_to = models.CharField(verbose_name=_('pay_to'), max_length=255)
    from_source = models.ForeignKey('PaymentSource', verbose_name=_('from_source'), on_delete=models.DO_NOTHING, null=True, blank=True)
    to_account = models.CharField(verbose_name=_('to_account'), max_length=40)
    applicant = models.CharField(verbose_name=_('applicant'), max_length=255)
    accounting = models.CharField(verbose_name=_('applicant'), max_length=255, null=True, blank=True)
    manager_confirmation = models.BooleanField(verbose_name=_('manager_confirm'), default=False)
    group = models.IntegerField(null=True, blank=True)


class PaymentSource(AbsBaseModel):
    title = models.CharField(verbose_name=_('title'), max_length=255)

    auto_complete = 'title'
    insert_new = False
