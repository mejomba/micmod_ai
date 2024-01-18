from django import forms
from core.forms import CustomBaseModelForm
from files.models import File, Image
from tools.utils import show_error
from .models import PriceInquiryFile, PriceInquiryResult, SalesPriceInqueryLog, InquiryResult, Supplier
from extra_data.models import Item

from translator import get_text as _

from django_select2 import forms as s2forms


class SkuCreateForm(CustomBaseModelForm):
    image_groups = 2
    file_groups = 1
    image_model = Image
    file_model = File
    has_file = True
    has_image = True
    crispy = True

    class Meta:
        model = Item
        exclude = ['group']

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

            form_constraint_read = form_constraint[self.form_state].get('read')
            form_constraint_hide = form_constraint[self.form_state].get('hide')
            formset_constraint_read = formset_constraint[self.form_state][0].get('read')
            formset_constraint_hide = formset_constraint[self.form_state][0].get('hide')

        kwargs.pop('constraint', None)
        super().__init__(*args, **kwargs)

        if request and not request.user.is_superuser:
            if form_constraint_hide:
                self.make_hidden(form_constraint_hide)
            if form_constraint_read:
                self.make_disable(form_constraint_read)
            if formset_constraint_hide:
                self.make_hidden(formset_constraint_hide)
            if formset_constraint_read:
                self.make_disable(formset_constraint_read)

        # if not access:
        #     self.make_disable(self.fields)
        #     self.enable = False

        self.make_optional(['brand', 'quality', 'sale_group',
                            'customs_group',
                            'package', 'batch_type', 'batch_count',
                            'image_1', 'image_2', 'file_1'])

        # try:
        #     initial = kwargs.get('initial')
        #     if initial:
        #         permission_access = initial.get('permission_access')
        #         # self.set_field_level_permission(permission_access.get('fields'), permission_access.get('action'))
        #         self.set_field_level_permission(permission_access)
        # except Exception as e:
        #     print(e)
        #
        # if not self.initial.get('create') and not self.initial.get('wf_access'):
        #     self.make_disable(self.fields)
        #     self.enable = False

    def save(self, commit=True):
        return super().save(commit=True)


class PriceInquiryFileSKUWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "sku__icontains",
        "part_number__icontains",
    ]


class PriceInquiryFileCreateForm(CustomBaseModelForm):
    crispy = True
    image_groups = 1
    image_model = Image
    # sku_c = forms.CharField(max_length=100, label=_('sku'))

    class Meta:
        model = PriceInquiryFile
        exclude = ['group']

        widgets = {
            'item': PriceInquiryFileSKUWidget,
        }

    def __init__(self, *args, **kwargs):
        try:
            kwargs.pop('constraint')
        except:
            print('err cons')
        super(PriceInquiryFileCreateForm, self).__init__(*args, **kwargs)
        self.make_optional(['image_1'])
        # self.make_hidden(['item'])


class PriceInquiryResultCreateForm(CustomBaseModelForm):
    image_groups = 1
    file_groups = 1
    image_model = Image
    file_model = File
    update_price = forms.BooleanField(widget=forms.CheckboxInput(), label=_('update_price'), required=False)

    class Meta:
        model = PriceInquiryResult
        exclude = ['group','price_update_date']

        widgets = {
            'sku': PriceInquiryFileSKUWidget,
        }
        
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

            form_constraint_read = form_constraint[self.form_state].get('read') if form_constraint else None
            form_constraint_hide = form_constraint[self.form_state].get('hide') if form_constraint else None
            formset_constraint_read = formset_constraint[self.form_state][0].get('read') if formset_constraint else None
            formset_constraint_hide = formset_constraint[self.form_state][0].get('hide') if formset_constraint else None

        super(PriceInquiryResultCreateForm, self).__init__(*args, **kwargs)
        self.make_optional(['image_1', 'file_1'])
        self.make_hidden(['price_inquiry_file'])
        self.fields['active'].initial = True

        kwargs.pop('constraint', None)
        super().__init__(*args, **kwargs)

        if request and not request.user.is_superuser:
            if form_constraint_hide:
                self.make_hidden(form_constraint_hide)
            if form_constraint_read:
                self.make_disable(form_constraint_read)
            if formset_constraint_hide:
                self.make_hidden(formset_constraint_hide)
            if formset_constraint_read:
                self.make_disable(formset_constraint_read)

        # if not access:
        #     self.make_disable(self.fields)
        #     self.enable = False

        # try:
        #     initial = kwargs.get('initial')
        #     print(__file__, 'initial in formset ===== ', initial)
        #     if initial:
        #         permission_access = initial.get('permission_access')
        #         # self.set_field_level_permission(permission_access.get('fields'), permission_access.get('action'))
        #         self.set_field_level_permission(initial)
        # except Exception as e:
        #     show_error(e, __file__)


class PriceInquiryResult2CreateForm(CustomBaseModelForm):
    image_groups = 1
    file_groups = 1
    image_model = Image
    file_model = File
    update_price = forms.BooleanField(widget=forms.CheckboxInput(), label=_('update_price'), required=False)

    class Meta:
        model = PriceInquiryResult
        exclude = ['group', 'price_update_date']

        # widgets = {
        #     'sku': PriceInquiryFileSKUWidget,
        # }

    def __init__(self, *args, **kwargs):
        # request = access = form_constraint = formset_constraint = form_constraint_read = form_constraint_hide = formset_constraint_read = formset_constraint_hide = None
        # if self.form_state is None:
        #     if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
        #         self.form_state = c.get('form_state')
        #     elif kwargs.get('constraint'):
        #         self.form_state = kwargs.get('constraint').get('form_state')
        #
        # if self.form_state is not None:
        #     if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
        #         form_constraint = c.pop('form_constraint')  # remove unnecessary kwargs
        #         formset_constraint = c.pop('formset_constraint')  # remove unnecessary kwargs
        #         request = c.pop('request')  # remove unnecessary kwargs
        #         access = c.get('wf_access')
        #     elif kwargs.get('constraint'):
        #         form_constraint = kwargs.get('constraint').get('form_constraint')
        #         formset_constraint = kwargs.get('constraint').get('formset_constraint')
        #         request = kwargs.get('constraint').get('request')
        #         access = kwargs.get('constraint').get('wf_access')
        #         kwargs.pop('constraint')  # remove unnecessary kwargs
        #
        #     form_constraint_read = form_constraint[self.form_state].get('read') if form_constraint else None
        #     form_constraint_hide = form_constraint[self.form_state].get('hide') if form_constraint else None
        #     formset_constraint_read = formset_constraint[self.form_state][0].get('read') if formset_constraint else None
        #     formset_constraint_hide = formset_constraint[self.form_state][0].get('hide') if formset_constraint else None
        #
        super(PriceInquiryResult2CreateForm, self).__init__(*args, **kwargs)
        self.fields['sku_c'] = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
        # self.fields['payment_method'] = forms.ChoiceField(widget=forms.Select(attrs={'class': 'form-control'}))
        self.make_optional(['image_1', 'file_1'])
        self.make_hidden(['price_inquiry_file', 'sku'])
        self.fields['active'].initial = True
        #
        # kwargs.pop('constraint', None)
        # super().__init__(*args, **kwargs)
        #
        # if request and not request.user.is_superuser:
        #     if form_constraint_hide:
        #         self.make_hidden(form_constraint_hide)
        #     if form_constraint_read:
        #         self.make_disable(form_constraint_read)
        #     if formset_constraint_hide:
        #         self.make_hidden(formset_constraint_hide)
        #     if formset_constraint_read:
        #         self.make_disable(formset_constraint_read)
        #
        # if not access:
        #     self.make_disable(self.fields)
        #     self.enable = False

        try:
            initial = kwargs.get('initial')
            print(__file__, 'initial in formset ===== ', initial)
            if initial:
                permission_access = initial.get('permission_access')
                # self.set_field_level_permission(permission_access.get('fields'), permission_access.get('action'))
                self.set_field_level_permission(initial)
        except Exception as e:
            show_error(e, __file__)



class SalesPriceInqueryLogForm(CustomBaseModelForm):
    sku_c = forms.CharField(max_length=100, label=_('sku'))

    class Meta:
        model = SalesPriceInqueryLog
        fields = ['sku_c', 'sku', 'party_code', 'quantity', 'grade', 'payment_method', 'currency', 'price_setting']
        # widgets = {
        #     'sku': PriceInquiryFileSKUWidget,
        # }

    def __init__(self, *args, **kwargs):
        super(SalesPriceInqueryLogForm, self).__init__(*args, **kwargs)
        self.fields['sku'].widget = forms.HiddenInput()
        self.fields['payment_method'] = forms.ChoiceField(widget=forms.Select(attrs={'class': 'form-control'}))
        self.fields['grade'] = forms.ChoiceField(widget=forms.Select(attrs={'class': 'form-control'}))
        for field_name, field in self.fields.items():
            if 1 == 2:#field_name in ['sku_c','quantity','sku','party_code']:
                field.widget.attrs['onkeydown'] = "refresh_data(event)"
            else:
                field.widget.attrs['onchange'] = "refresh_data(event)"



class InquiryResultForm(CustomBaseModelForm):

    class Meta:
        model = InquiryResult
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        kwargs.pop('constraint', None)
        super(InquiryResultForm, self).__init__(*args, **kwargs)

        self.make_hidden(self.fields)


class SupplierModelForm(CustomBaseModelForm):

    class Meta:
        model = Supplier
        fields = ['name']

    def __init__(self, *args, **kwargs):
        kwargs.pop('constraint', None)
        super(SupplierModelForm, self).__init__(*args, **kwargs)
