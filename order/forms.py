from django import forms


class OrderForm(forms.ModelForm):
    class Meta:
        fields = '__all__'


class OrderItemForm(forms.ModelForm):
    class Meta:
        fields = '__all__'
