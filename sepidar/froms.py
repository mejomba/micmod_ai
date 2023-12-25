from django import forms

from core.forms import CustomBaseModelForm
from files.models import Image
from .models import Device
from translator import get_text as _


class DeviceForm(CustomBaseModelForm):
    class Meta:
        model = Device
        fields = '__all__'

    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)