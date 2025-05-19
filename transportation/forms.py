from core.forms import CustomBaseModelForm
from transportation.models import TradeTransportationMethod
from django import forms


class TradeTransportationMethodModelForm(CustomBaseModelForm):

    class Meta:
        model = TradeTransportationMethod
        exclude = ['group', 'is_deleted', 'code']

    def __init__(self, *args, **kwargs):
        super(TradeTransportationMethodModelForm, self).__init__(*args, **kwargs)
        # self.fields['fixed_cost'] = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control comma-seperator'}))
        # self.fields['variable_cost'] = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control comma-seperator'}))

