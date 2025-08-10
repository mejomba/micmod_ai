from django.db.models import Q
from django.forms import inlineformset_factory

from django import forms
from django_select2.forms import ModelSelect2MultipleWidget
from jalali_date.fields import JalaliDateField, JalaliDateTimeField, SplitJalaliDateTimeField
from jalali_date.widgets import AdminJalaliDateWidget, AdminSplitJalaliDateTime

from accounts.models import User
from core.forms import CustomBaseModelForm
from factor.models import Factor, FactorItem
from order.models import Order
from translator import get_text as _
from django.utils.html import format_html


class x (AdminSplitJalaliDateTime):
    template_name = 'core/partial/jalali_split_datetime.html'


class UserSelectWidget(ModelSelect2MultipleWidget):
    search_fields = [
        "username__icontains",
        "first_name__icontains",
        "last_name__icontains",
        "email__icontains",
    ]

class FactorModelForm(CustomBaseModelForm):
    class Meta:
        model = Factor
        exclude = ['factor_self', 'guid', 'status', 'group', ]

    def __init__(self, *args, **kwargs):
        request = access = form_constraint = formset_constraint = form_constraint_read = form_constraint_hide = formset_constraint_read = formset_constraint_hide = None
        if self.form_state is None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                self.form_state = c.get('form_state')
            elif kwargs.get('constraint'):
                self.form_state = kwargs.get('constraint').get('form_state')

        if self.form_state is not None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                access = c.pop('wf_access')
                form_constraint = c.pop('form_constraint')  # remove unnecessary kwargs
                formset_constraint = c.pop('formset_constraint')  # remove unnecessary kwargs
                request = c.pop('request')  # remove unnecessary kwargs
            elif kwargs.get('constraint'):
                access = kwargs.get('constraint').get('wf_access')
                form_constraint = kwargs.get('constraint').get('form_constraint')
                formset_constraint = kwargs.get('constraint').get('formset_constraint')
                request = kwargs.get('constraint').get('request')  # remove unnecessary kwargs
                kwargs.pop('constraint')  # remove unnecessary kwargs

            if form_constraint:
                for item in form_constraint[self.form_state]:
                    if item.get('group') in request.user.groups.values_list('name', flat=True):
                        form_constraint_read = item.get('read')  # form_constraint[self.form_state].get('read')
                        form_constraint_hide = item.get('hide')  # orm_constraint[self.form_state].get('hide')
            if formset_constraint:
                for item in formset_constraint[self.form_state]:
                    if item.get('group') in request.user.groups.values_list('name', flat=True):
                        formset_constraint_read = item.get('read')  # formset_constraint[self.form_state][0].get('read')
                        formset_constraint_hide = item.get('hide')  # formset_constraint[self.form_state][0].get('hide')
        super(FactorModelForm, self).__init__(*args, **kwargs)
        self.make_hidden(['packing_json'])
        self.fields['is_official'].widget.attrs['onchange'] = 'factor_calculate_price_all_rows()'
        self.fields['official_value'].widget = forms.TextInput(attrs={'onchange': 'factor_calculate_price_all_rows()', 'class': 'LTR-RTL rounded font-size-11 text-center w-75'})
        self.fields['self_discount'].widget = forms.TextInput(attrs={'onchange': 'factor_calculate_price_all_rows()', 'class': 'LTR-RTL rounded font-size-11 text-center w-75'})

        self.make_hidden(['q'])
        # self.fields['collecting_start_time'] = SplitJalaliDateTimeField(label=_('date time'),
        #     widget=AdminSplitJalaliDateTime # required, for decompress DatetimeField to JalaliDateField and JalaliTimeField
        # )
        self.fields['collecting_start_time'] = SplitJalaliDateTimeField(label=_('collecting_start_time'),
                                                      widget=x(
                                                          attrs={'class': 'jalali_date-date form-control',
                                                                 'size': '10'}), required=False
                                                      )
        self.fields['wh_user'] = forms.ModelMultipleChoiceField(queryset=User.objects.filter(Q(groups__name='wh_user') |
                                                                              Q(groups__name='wh_admin')).distinct(), required=False)

        if request and request.user.base_group == 'accounting':
            self.fields['checker'] = forms.ModelMultipleChoiceField(queryset=User.objects.filter(Q(groups__name='accounting_user') |
                                                                                                 Q(groups__name='accounting_admin')).distinct(), required=False)
        else:
            self.fields['checker'] = forms.ModelMultipleChoiceField(
                queryset=User.objects.filter(Q(groups__name='accounting_user') |
                                             Q(groups__name='accounting_admin')).distinct(), required=False, disabled=True)

        self.make_hidden(form_constraint_hide or [])
        self.make_hidden(formset_constraint_hide or [])
        self.make_disable(form_constraint_read or [])
        self.make_disable(formset_constraint_read or [])
        # if not access:
        #     self.make_disable(self.fields)


class FactorItemModelForm(CustomBaseModelForm):
    class Meta:
        model = FactorItem
        exclude = ['group']
    supply_location = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        request = access = form_constraint = formset_constraint = form_constraint_read = form_constraint_hide = formset_constraint_read = formset_constraint_hide = None
        if self.form_state is None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                self.form_state = c.get('form_state')
            elif kwargs.get('constraint'):
                self.form_state = kwargs.get('constraint').get('form_state')

        if self.form_state is not None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                access = c.pop('wf_access')
                form_constraint = c.pop('form_constraint')  # remove unnecessary kwargs
                formset_constraint = c.pop('formset_constraint')  # remove unnecessary kwargs
                request = c.pop('request')  # remove unnecessary kwargs
            elif kwargs.get('constraint'):
                access = kwargs.get('constraint').get('wf_access')
                form_constraint = kwargs.get('constraint').get('form_constraint')
                formset_constraint = kwargs.get('constraint').get('formset_constraint')
                request = kwargs.get('constraint').get('request')  # remove unnecessary kwargs
                kwargs.pop('constraint')  # remove unnecessary kwargs

            if form_constraint:
                for item in form_constraint[self.form_state]:
                    if item.get('group') in request.user.groups.values_list('name', flat=True):
                        form_constraint_read = item.get('read')  # form_constraint[self.form_state].get('read')
                        form_constraint_hide = item.get('hide')  # orm_constraint[self.form_state].get('hide')
            if formset_constraint:
                for item in formset_constraint[self.form_state]:
                    if item.get('group') in request.user.groups.values_list('name', flat=True):
                        formset_constraint_read = item.get('read')  # formset_constraint[self.form_state][0].get('read')
                        formset_constraint_hide = item.get('hide')  # formset_constraint[self.form_state][0].get('hide')

        super(FactorItemModelForm, self).__init__(*args, **kwargs)

        self.fields['quantity'].widget.attrs['onkeyup'] = 'check_quantity(event)'
        self.fields['price'].widget.attrs['onkeyup'] = 'check_price(event)'
        self.fields['is_bazar'].widget.attrs['class'] = 'checkbox_is_bazar'
        if self.fields['is_bazar']:
            self.make_disable(['supply_locations'])
        if self.instance:
            self.fields['supply_locations'].queryset = Order.objects.filter(item_id=self.instance.goods_code)

        self.make_hidden(form_constraint_hide or [])
        self.make_hidden(formset_constraint_hide or [])
        self.make_disable(form_constraint_read or [])
        self.make_disable(formset_constraint_read or [])
        if not access:
            self.make_disable(self.fields)


factor_item_fields = ['factor', 'qi', 'index', 'quantity', 'delivery_time', 'custom_price', 'goods_code',
                      'part_number_show', 'price', 'supply_location', 'supply_locations', 'is_bazar', 'reserve_count'
                      ]

FactorItemFormset = inlineformset_factory(
    Factor,
    FactorItem,
    form=FactorItemModelForm,
    extra=0,
    fields=factor_item_fields,
)
