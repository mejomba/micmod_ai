import os

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.http import JsonResponse

from core.models import AbsBaseModel, BaseModeWF, BaseContentType
from translator import get_text as _


def uploaded_file_path(instance, filename: str):
    """generate file path for file"""
    name = '_'.join(filename.split(' '))
    name = f"_{name}"
    return os.path.join('uploads/file/payment/', name)


class CreditCard(BaseModeWF):
    title = models.CharField(_('title'), max_length=255, unique=True, error_messages="این عنوان از قبل موجود است")
    credit_card_number = models.CharField(_('credit-card-number'), max_length=255, help_text='بدون خط فاصله، بدون اسپیس')
    auto_complete = 'title'


class PaymentOrder(BaseModeWF):
    SOURCE_CHOICES = (('1','تنخواه مالی'), ('2', 'پرداخت مستقیم'))
    FORMAL_CHOICE = (('1', 'غیر رسمی'), ('2', 'رسمی رسول رفیع'), ('3', 'رسمی رهاورد'))
    request_date = models.DateField(verbose_name=_('request_date'))
    payment_date = models.DateField(verbose_name=_('payment_date'), null=True, blank=True)
    # amount = models.PositiveBigIntegerField(verbose_name=_('amount'), default=1)
    amount = models.CharField(max_length=16, verbose_name=_('amount'), default=1)
    behalf = models.CharField(verbose_name=_('for_'), max_length=255)
    pay_to = models.CharField(verbose_name=_('pay_to'), max_length=255, null=True, blank=True)
    from_source = models.ForeignKey('PaymentSource', verbose_name=_('from_source'), on_delete=models.DO_NOTHING, null=True, blank=True)
    to_account = models.CharField(verbose_name=_('to_account'), max_length=40)
    applicant = models.CharField(verbose_name=_('applicant'), max_length=255)
    accounting = models.CharField(verbose_name=_('applicant'), max_length=255, null=True, blank=True)
    manager_confirmation = models.BooleanField(verbose_name=_('manager_confirm'), default=False)
    group = models.IntegerField(null=True, blank=True)
    is_formal = models.BooleanField(verbose_name=_('is_formal'), default=False)
    is_formal2 = models.CharField(verbose_name=_('payment_type'), choices=FORMAL_CHOICE, default='1')
    pay_doc = models.FileField(verbose_name=_('file'), upload_to=uploaded_file_path, null=True, blank=True)
    need_pay_doc = models.BooleanField(verbose_name=_('need_pay_doc'), default=False)
    is_paid = models.BooleanField(verbose_name=_('is_paid'), default=False)
    force = models.BooleanField(_('force'), default=False)
    description = models.TextField(_('description'), null=True, blank=True)
    credit_card = models.ForeignKey(CreditCard, on_delete=models.DO_NOTHING, related_name='payments', null=True, blank=True)

    def __str__(self):
        return f'دستور پرداخت ({self.id})'


class PaymentSource(AbsBaseModel):
    title = models.CharField(verbose_name=_('title'), max_length=255)

    auto_complete = 'title'
    insert_new = True


class PaymentDocument(AbsBaseModel):
    DOC_CHOICES = (
        ("A", _("pay_doc")),
        ("B", _("receive_doc")),
    )
    from_date = models.DateField(verbose_name=_('form_date'), null=True, blank=True)
    to_date = models.DateField(verbose_name=_('to_date'), null=True, blank=True)
    total_amount = models.FloatField(_('total_amount'), null=True, blank=True)
    path = models.FileField(verbose_name=_('file'), upload_to=uploaded_file_path, null=True, blank=True)
    doc_type = models.CharField(_('doc_type'), max_length=1, choices=DOC_CHOICES)
    description = models.TextField(_('description'), null=True, blank=True)
    payment_order = models.ForeignKey(PaymentOrder, verbose_name=_('payment'), on_delete=models.DO_NOTHING)


class Payment(BaseModeWF):
    from_date = models.DateField(verbose_name=_('form_date'), null=True, blank=True)
    to_date = models.DateField(verbose_name=_('to_date'), null=True, blank=True)
    total_amount = models.FloatField(_('total_amount'))
    description = models.TextField(_('description'), null=True, blank=True)


class GenericPaymentItem(BaseModeWF):
    # payment = models.ForeignKey(Payment, on_delete=models.DO_NOTHING, related_name='payment_item', null=True, blank=True)
    g_from_date = models.DateField(verbose_name=_('form_date'), null=True, blank=True)
    g_to_date = models.DateField(verbose_name=_('to_date'), null=True, blank=True)
    total_amount = models.FloatField(_('total_amount'))
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING, related_name='payment_content_type',
                                     null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    description = models.TextField(_('description'), null=True, blank=True)

    def get_related_model(self):
        try:
            if self.content_type:
                related_model_name = self.content_type.model
                related_object = self.content_object  # خود آبجکت مرتبط
                return related_model_name, related_object
            else:
                return 'not found'
        except GenericPaymentItem.DoesNotExist:
            return 'not found'

