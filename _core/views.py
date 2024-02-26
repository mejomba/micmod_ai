import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.views.generic import ListView
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ProcessFormView, ModelFormMixin
from accounts.extra_models import Profile
from accounts.mixins import FormFieldAccessMixin
from .forms import CustomBaseModelForm
from .models import ExtraData
from django.apps import apps
from tools.utils import map_model_to_python_type,is_ajax


class BaseView(UserPassesTestMixin,
               SingleObjectTemplateResponseMixin,
               SuccessMessageMixin,
               ModelFormMixin,
               ProcessFormView,
               FormFieldAccessMixin
               ):
    extra_data = ExtraData()
    # has_flow = None
    priority_strategy = 'or'
    permission_strategy = 'or'
    allow_groups = []
    allow_perms = []
    custom_queries = []
    permission_priority_order = ['allow_perms', 'allow_groups']
    base_form = CustomBaseModelForm
    main_form = None
    formset_model = None
    formset = None
    formset_form = None
    formset_fk_field = None
    related_name_fk = ''
    detail_list = []
    create = None
    has_formset = None
    template_name = 'base_view.html'
    finish = None
    extra_formset = 1
    wf_access = None
    form_partial = []
    formset_partial = []
    _form_partial = []
    _formset_partial = []
    form_struct = None
    formset_l2 = None
    form = None
    form_class = None

    def get_object(self, queryset=None):
        try:
            return super().get_object(queryset)
        except AttributeError as e:
            print('error ', __file__, e.__traceback__.tb_lineno, e)
            return None

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        ...

    def get(self, request, *args, **kwargs):
        ...
        return super().get(request, *args, **kwargs)


    def post(self, request, *args, **kwargs):
        self.form_class = self.get_form_class()

        self.request.POST._mutable = True
        for key, value in list(self.request.POST.items()):
            if key.__contains__("__auto__"):
                key = key.replace("__auto__", "")
                value = value.strip()
                if value:
                    model = self.form_class.base_fields[key].queryset.model
                    obj, _ = model.objects.get_or_create(**{model.auto_complete: value})
                    value = getattr(obj, self.form_class.base_fields[key].to_field_name, None)
                self.request.POST[key] = value
        self.request.POST._mutable = False

        self.form = self.form_class(self.request.POST, self.request.FILES, instance=self.object, initial={
                                                  "constraint": {
                                                      "wf_access": True,
                                                      'form_state': self.state_index,
                                                      'request': self.request,
                                                      'form_constraint': self.flow_config.get('flow_form_constraint'),
                                                      'formset_constraint': self.flow_config.get('flow_formset_constraint')
                                                      }
                                              })

    def __permission_priority_check(self, priority):
        permissions = getattr(self, priority)
        return self.__permission_check(permissions, priority)

    def __permission_check(self, permissions, priority):
        if 'perms' in priority and self.permission_strategy == 'or':
            return any(self.request.user.has_perm(perm) for perm in permissions)
        elif 'perms' in priority and self.permission_strategy == 'and':
            return all(self.request.user.has_perm(perm) for perm in permissions)

        if 'groups' in priority and self.permission_strategy == 'or':
            user_groups = self.request.user.groups.values_list('name', flat=True)
            for g in user_groups:
                if g in permissions:
                    return True

        elif 'groups' in priority and self.permission_strategy == 'and':
            user_groups = self.request.user.groups.values_list('name', flat=True)
            for g in user_groups:
                if g not in permissions:
                    return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.profile = Profile.get_or_create(self.request.user)

        print(__file__, 'super class context', context.get('current_user_groups'))
        return context

    def test_func(self):
        if not self.model:
            raise ImproperlyConfigured(f'''BaseView need model attribute''')
        if not self.allow_perms:
            self.allow_perms = [f'{self.model._meta.app_label}.view_{self.model._meta.model_name}',
                                f'{self.model._meta.app_label}.add_{self.model._meta.model_name}',
                                f'{self.model._meta.app_label}.change_{self.model._meta.model_name}',
                                f'{self.model._meta.app_label}.delete_{self.model._meta.model_name}',
                                ]

        if self.priority_strategy == 'or':
            return any(self.__permission_priority_check(priority) for priority in self.permission_priority_order)
        if self.priority_strategy == 'and':
            return all(self.__permission_priority_check(priority) for priority in self.permission_priority_order)


class BaseCustomView():
    def get_queryset_from_request(self):
        """
if request params is name__icontains=test&age=30 for example
this function  generate qry for load data from model db
qry = model.objects.filter(name__icontains=test, age=30 )
        """
        qry = dict()
        request_data = dict()
        for key, value in self.request_data.items():
            split_ = key.split('__')
            request_data[split_[0]] = (split_[1:], value)
        for field in self.model._meta.fields:
            value_ = request_data.get(field.name)
            if value_:
                value = value_[1]
                datatype = map_model_to_python_type(field)
                if datatype == 'int':
                    value = int(value)
                elif datatype == 'float':
                    value = float(value)
                qry[f'{"__".join([field.name]+ value_[0])}'] = value
        return qry

    def get_model(self, **kwargs):
        app_label = kwargs.get('app_label')
        model_name = kwargs.get('model_name')
        if app_label and model_name:
            del kwargs['app_label']
            del kwargs['model_name']
            self.model = apps.get_model(app_label=app_label.lower(), model_name=model_name.lower())
        return kwargs

class BaseCustomCreateView(BaseCustomView, ProcessFormView):
    template_name = ''

    def __init__(self):
        super().__init__()

    def get_forms(self):
        self.forms = self.model.extra_process_on_get_method(data=self.request_data)

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        kwargs = self.get_model(**kwargs)
        instance = self.model.objects.first()
        self.form = instance.get_view_forms(request,*args, **kwargs)

    def get(self, request, *args, **kwargs):
        context = dict()
        context['form'] = self.form
        return render(request, '_core/create/base.html', context)
    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            self.form.save()
            if getattr(self.form,'forms', None) and self.form.forms[0].is_valid():
                self.form.forms[0].save()
        context = dict()
        self.form.instance.pk = None
        context['form'] = self.form
        return render(request, '_core/create/base.html', context)

class BaseCustomListView(BaseCustomView,ListView):

    def __init__(self):
        super().__init__()
    def get_queryset(self):
        return super().get_queryset().filter(self.get_queryset_from_request())

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.get_model(**kwargs)
        self.request_data = self.request.GET or self.request.POST
        if not self.template_name:
            self.template_name = self.model.template_name_list or ''

    def get(self, request, *args, **kwargs):
        return super().get(self, request, *args, **kwargs)


def download_excel(request,app_label, model_name):
    ...
