from core.forms import CustomBaseModelForm
from transportation.models import TradeTransportationMethod, TransportationCalender
from django import forms


class TradeTransportationMethodModelForm(CustomBaseModelForm):
    has_comment = True

    class Meta:
        model = TradeTransportationMethod
        exclude = ['group', 'is_deleted', 'code']

    def __init__(self, *args, **kwargs):
        super(TradeTransportationMethodModelForm, self).__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['rows'] = 1
        # self.fields['fixed_cost'] = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control comma-seperator'}))
        # self.fields['variable_cost'] = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control comma-seperator'}))


class TransportationCalenderModelForm(CustomBaseModelForm):
    has_comment = True

    class Meta:
        model = TransportationCalender
        exclude = ['group', 'is_deleted', 'code']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['rows'] = 1


