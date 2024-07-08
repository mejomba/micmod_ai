from django.db import models
from core.models import AbsBaseModel
from translator import get_text as _


class PaymentOrder(AbsBaseModel):
    request_date = models.DateField(verbose_name=_('request_date'))
    payment_date = models.DateField(verbose_name=_('payment_date'), null=True, blank=True)
    amount = models.PositiveBigIntegerField(verbose_name=_('amount'), default=1)
    behalf = models.CharField(verbose_name=_('for_'), max_length=255)
    pay_to = models.CharField(verbose_name=_('pay_to'), max_length=255)
    from_source = models.CharField(verbose_name=_('from_source'), max_length=255)
    to_account = models.CharField(verbose_name=_('to_account'), max_length=40)
    applicant = models.CharField(verbose_name=_('applicant'), max_length=255)
    accounting = models.CharField(verbose_name=_('applicant'), max_length=255, null=True, blank=True)
    manager_confirmation = models.BooleanField(verbose_name=_('manager_confirm'), default=False)
