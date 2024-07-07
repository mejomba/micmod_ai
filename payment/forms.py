from django.utils import timezone
from jalali_date.fields import JalaliDateTimeField
from jalali_date.widgets import AdminJalaliDateWidget

from core.forms import CustomBaseModelForm
from payment.models import PaymentOrder

from translator import get_text as _


class PaymentOrderModelForm(CustomBaseModelForm):
    image_groups = 1
    file_groups = 1

    class Meta:
        model = PaymentOrder
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['request_date'] = JalaliDateTimeField(widget=AdminJalaliDateWidget(
                                      attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True)
        self.fields['payment_date'] = JalaliDateTimeField(widget=AdminJalaliDateWidget(
            attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True)

        self.fields['request_date'].initial = timezone.now()