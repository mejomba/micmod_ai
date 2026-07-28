from django import forms
from django.forms import inlineformset_factory
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget
from django_select2 import forms as s2forms
from files.models import File, Image
from translator import get_text as _

from core.forms import CustomBaseModelForm, CustomBaseForm
from .models import Contract, CustomerItemReceipt, ProjectItemList, ProductionDayActivities, ItemsInCustomerReceipt


class CustomerItemReceiptFormContractWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "id__iexact",
    ]


class ProjectItemListFormContractWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "id__iexact",
    ]


class ProjectItemListFormGoodsCodeWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "sku__icontains",
        "id__iexact",
    ]


class ProductionDayActivitiesFormCustomerWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "customer_party_id__title__icontains",
        "id__iexact",
    ]


class ContractForm(CustomBaseModelForm):
    image_model = Image
    image_groups = 1
    has_image = True

    class Meta:
        model = Contract
        fields = ['customer_party_id', 'goods_code_fk', 'project_name_en', 'customer_board_count',
                  'customer_sheet_count', 'customer_total_board_count', 'first_setup_time', 'second_setup_time',
                  'pad_count', 'ic_pad_count', 'first_setup_cost', 'second_setup_cost', 'pad_cost', 'ic_pad_cost',
                  'total_cost', 'not_assembly_pad_count', 'finish'
                  ]

    def __init__(self, *args, **kwargs):
        request = access = form_constraint = formset_constraint = form_constraint_read = form_constraint_hide = formset_constraint_read = formset_constraint_hide = None
        if self.form_state is None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                self.form_state = c.get('form_state')
            elif kwargs.get('constraint'):
                self.form_state = kwargs.get('constraint').get('form_state')

        if self.form_state is not None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                form_constraint = c.pop('form_constraint')  # remove unnecessary kwargs
                formset_constraint = c.pop('formset_constraint')  # remove unnecessary kwargs
                request = c.pop('request')  # remove unnecessary kwargs
                access = c.get('wf_access')
            elif kwargs.get('constraint'):
                form_constraint = kwargs.get('constraint').get('form_constraint')
                formset_constraint = kwargs.get('constraint').get('formset_constraint')
                request = kwargs.get('constraint').get('request')
                access = kwargs.get('constraint').get('wf_access')
                kwargs.pop('constraint')  # remove unnecessary kwargs
            if form_constraint:
                form_constraint_read = form_constraint[self.form_state].get('read')
                form_constraint_hide = form_constraint[self.form_state].get('hide')
            if formset_constraint:
                formset_constraint_read = formset_constraint[self.form_state][0].get('read')
                formset_constraint_hide = formset_constraint[self.form_state][0].get('hide')
        super(ContractForm, self).__init__(*args, **kwargs)
        self.make_hidden(['customer_party_id', 'goods_code_fk',])

        # request = kwargs.get('initial').get('constraint').get('request')
        user_groups = request.user.groups.values_list('name', flat=True)
        if request and not request.user.is_superuser and 'pcba_admin' not in user_groups:
            # if 'pcba_user' in user_groups:
            self.make_hidden(
                ['first_setup_cost', 'second_setup_cost', 'pad_cost', 'ic_pad_cost', 'total_cost', 'finish'])
            self.make_disable(
                ['first_setup_cost', 'second_setup_cost', 'pad_cost', 'ic_pad_cost', 'total_cost', 'finish'])


class ItemReceiptForm(CustomBaseModelForm):
    file_groups = 1
    file_model = File
    has_file = True
    # part_number = forms.ChoiceField(choices=[], widget=forms.Select())

    class Meta:
        model = ItemsInCustomerReceipt
        exclude = ['group']

        widgets = {
            'customer_item_receipt': CustomerItemReceiptFormContractWidget,
        }

    def __init__(self, *args, **kwargs):
        contract = kwargs.pop('contract', None)
        super(ItemReceiptForm, self).__init__(*args, **kwargs)
        self.fields['receipt_date'] = JalaliDateField(label=_('receipt_date'), widget=AdminJalaliDateWidget, required=False)
        self.fields['receipt_date'].widget.attrs.update(
            {'class': 'jalali_date-date form-control', 'placeholder': _('receipt_date'), 'required': False})
        # self.make_hidden(['parent', 'contract'])
        self.make_hidden(['goods_code_fk'])
        self.fields['goods_code_fk'].widget.attrs['id'] = 'id_goods_code_fk3'
        self.fields['part_number'].widget.attrs['id'] = 'id_part_number2'
        self.fields['part_number'].widget.attrs['list'] = "lst_part_number"
        self.fields['part_number'].widget.attrs['autocomplete'] = "off"
        # self.fields['customer_item_receipt'].queryset = CustomerItemReceipt.objects.filter()

        # if self.instance.pk is not None:
        #     self.fields['part_number'].widge.attrs['data-url'] = f'core/xxx/yyy/{self.instance.customer_item_receipt.pk}'
        #
        # if contract:
        #     part_number = ProjectItemList.objects.filter(contract_id=contract)
        #     self.fields['part_number'].choices = ([('', '----------')] +
        #                                           [(item.part_number, item.part_number) for item in part_number])
        # else:
        #     try:
        #         cir = kwargs.get('initial').get('constraint').get('request').POST.get('customer_item_receipt')
        #         contract = CustomerItemReceipt.objects.filter(pk=cir).first().contract.pk
        #         part_number = ProjectItemList.objects.filter(contract_id=contract)
        #         self.fields['part_number'].choices = ([('', '----------')] +
        #                                               [(item.part_number, item.part_number) for item in part_number])
        #     except:
        #         pass


class CustomerItemReceiptForm(CustomBaseModelForm):

    def __init__(self, *args, **kwargs):
        contract = kwargs.pop('contract', None)
        super(CustomerItemReceiptForm, self).__init__(*args, **kwargs)
        if contract:
            self.fields['parent'].queryset = CustomerItemReceipt.objects.filter(contract_id=contract,
                                                                                status=CustomerItemReceipt.INCOMPLETE)
        self.fields['receipt_date'] = JalaliDateField(label=_('receipt_date'), widget=AdminJalaliDateWidget, required=False)
        self.fields['receipt_date'].widget.attrs.update(
            {'class': 'jalali_date-date form-control', 'placeholder': _('receipt_date'), 'required': False})

    class Meta:
        model = CustomerItemReceipt
        exclude = ['group']

        widgets = {
            'contract': CustomerItemReceiptFormContractWidget,
        }


class ProjectItemListForm(CustomBaseModelForm):

    class Meta:
        model = ProjectItemList
        exclude = ['group']

        widgets = {
            'contract': ProjectItemListFormContractWidget,
        }

    def __init__(self, *args, **kwargs):
        super(ProjectItemListForm, self).__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['rows'] = 1
        self.make_hidden(['goods_code_fk'])
        self.fields['goods_code_fk'].widget.attrs['id'] = 'id_goods_code_fk2'


class ProductionDayActivitiesForm(CustomBaseModelForm):
    class Meta:
        model = ProductionDayActivities
        exclude = ['group', 'last_work_flow']

        widgets = {
            'contract': ProjectItemListFormContractWidget,
            'goods_code_fk': ProjectItemListFormGoodsCodeWidget,
            'customer_party_id': ProductionDayActivitiesFormCustomerWidget,
            'start_time': forms.TimeInput(
                attrs={'type': 'time'},
                format='%H:%M'
            ),
            'end_time': forms.TimeInput(
                attrs={'type': 'time'},
                format='%H:%M'
            )
        }

    def __init__(self, *args, **kwargs):
        contract = kwargs.pop('contract', None)
        super(ProductionDayActivitiesForm, self).__init__(*args, **kwargs)
        self.fields['production_date'] = JalaliDateField(label=_('production_date'), widget=AdminJalaliDateWidget,
                                                      required=False)
        self.fields['production_date'].widget.attrs.update(
            {'class': 'jalali_date-date form-control', 'placeholder': _('production_date'), 'required': False})
        if contract:
            self.fields['customer_item_receipt'].queryset = CustomerItemReceipt.objects.filter(contract_id=contract)

        request = kwargs.get('initial').get('constraint').get('request')
        user_groups = request.user.groups.values_list('name', flat=True)
        if request and not request.user.is_superuser and 'pcba_admin' not in user_groups:
            self.make_hidden(['factor_number'])
            self.make_disable(['factor_number'])


class TimeForm(CustomBaseForm):
    from_time = forms.DateField(required=False)
    to_time = forms.DateField(required=False)

    def __init__(self, *args, **kwargs):
        super(TimeForm, self).__init__(*args, **kwargs)
        self.fields['from_time'] = JalaliDateField(label=_('from_time'), widget=AdminJalaliDateWidget, required=False)
        self.fields['to_time'] = JalaliDateField(label=_('to_time'), widget=AdminJalaliDateWidget, required=False)
        self.fields['from_time'].widget.attrs.update(
            {'class': 'jalali_date-date form-control', 'placeholder': _('from_time'), 'required': False})
        self.fields['to_time'].widget.attrs.update(
            {'class': 'jalali_date-date form-control', 'placeholder': _('to_time'), 'required': False})
