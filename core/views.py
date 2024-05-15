import datetime
import json

from django.apps import apps
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ProcessFormView, ModelFormMixin
from _keenthemes import KTLayout
from accounts.extra_models import Profile
from accounts.mixins import FormFieldAccessMixin
from changelog.models import ChangeLog
from comments.forms import CommentsForm
from tools.import_data import import_customers_from_sepidar
from tools.utils import map_model_to_python_type, show_error
from workflow.forms import WorkFlowModelForm
from workflow.models import FlowAdminGroup
from workflow.views import FlowBaseView
from .forms import CustomBaseModelForm
from comments.models import Comments
from tools.form_tools import get_function

import openpyxl

from .models import ExtraData


class BaseView(UserPassesTestMixin,
               SingleObjectTemplateResponseMixin,
               SuccessMessageMixin,
               ModelFormMixin,
               ProcessFormView,
               FlowBaseView,
               FormFieldAccessMixin
               ):
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
    workflow_form = WorkFlowModelForm
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
    submit_copy = None

    def __init__(self):
        super().__init__()
        self.extra_data = ExtraData()

    def get_object(self, queryset=None):
        try:
            return super().get_object(queryset)
        except AttributeError as e:
            print('error ', __file__, e.__traceback__.tb_lineno, e)
            return None

    def get_formset_from_struct(self):
        try:
            return self.form_struct.get('childes')[0].get('form')
        except Exception as e:
            return None

    def get_form_from_struct(self):
        return self.form_struct.get('form')

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)

        if self.has_flow and not self.flow_config.get("append_last_step"):
            self.flow_config['flow_state_list'].append('مرحله نهایی')
            self.flow_config['flow_users_groups'].append(self.flow_config['flow_users_groups'][-1])
            self.flow_config['flow_form_constraint'].append({"hide": [], "read": []})
            self.flow_config['flow_formset_constraint'].append([{"hide": [], "read": []}])
            self.flow_config['flow_deadline'].append(0)
            self.flow_config['append_last_step'] = True

        self.object = self.get_object()
        self.formset_form = self.get_formset_from_struct()
        self.state_index = self.get_flow_index(self.object)

        # if request.method == 'GET':
        self.formset = self.get_formset_from_struct()

    def get(self, request, *args, **kwargs):
        if self.has_formset and not all([self.model, self.formset_model, self.formset_form]):
            raise ImproperlyConfigured(f'formset use but not configure [model, formset_model, formset_form] is required')
        if self.has_flow and not all([item for item in self.flow_config.keys()]):
            raise ImproperlyConfigured(f'''has_flow use but not configure [{super().flow_config.keys()}] is required''')
        if self.has_flow and not self.flow_config.get('flow_action'):
            raise ImproperlyConfigured(f'''has_flow use but not configure [flow_action] can't be None''')
        if self.has_flow and self.has_simple_flow:
            raise ImproperlyConfigured(f'''has_flow and has_simple_flow can't use together''')

        if self.has_flow and not self.flow_config.get("append_last_step"):
            self.flow_config['flow_state_list'].append('مرحله نهایی')
            self.flow_config['flow_users_groups'].append(self.flow_config['flow_users_groups'][-1])
            self.flow_config['flow_form_constraint'].append({"hide": [], "read": []})
            self.flow_config['flow_formset_constraint'].append([{"hide": [], "read": []}])
            self.flow_config['flow_deadline'].append(0)
            self.flow_config['append_last_step'] = True

        self.object = self.get_object()
        if self.has_flow:
            self.state_index = self.get_flow_index(self.object)

        if hasattr(self.form_class, 'form_state'):
            self.form_class.form_state = self.state_index

        if self.has_formset:
            self.formset_form.form_state = self.state_index
        return super().get(request, *args, **kwargs)

    def get_form_class(self):
        if self.form_struct:
            self.form_class = self.form_struct.get('form')
        return self.form_class

    def post(self, request, *args, **kwargs):
        self.form_class = self.get_form_class()

        self.request.POST._mutable = True
        for key, value in list(self.request.POST.items()):
            if key.__contains__("__auto__"):
                model_str, key = key.split("__auto__")
                value = value.strip()
                if value:
                    model = get_function(model_str) #self.form_class.base_fields[key].queryset.model
                    obj = model.objects.filter(**{f'{model.auto_complete}__iexact': value}).first()
                    if not obj:
                        obj = model.objects.create(**{model.auto_complete: value})
                        obj.extra_data.request = self.request
                        obj.auto_complete_func()
                    value = getattr(obj, 'pk', None)
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

        self.object = self.get_object()
        """ run import customer from sepidar before object create"""
        if self.object is None:
            import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})

        if self.has_flow:
            self.state_index = self.get_flow_index(self.object)

        self.get_form_kwargs()
        if self.has_flow:
            try:
                flow_obj = self.get_flow(self.object).order_by('id').last()
                if 'draft' in self.request.POST and flow_obj.wf_status == 1:
                    wfform = self.workflow_form(data=self.request.POST, initial=self.wf_initial,
                                                content_type_model=self.model, current_user=self.request.user,
                                                instance=flow_obj)
                else:
                    wfform = self.workflow_form(data=self.request.POST, initial=self.wf_initial,
                                                content_type_model=self.model, current_user=self.request.user)
            except Exception as e:
                print('error ', __file__, e.__traceback__.tb_lineno, e)
                wfform = self.workflow_form(data=self.request.POST, initial=self.wf_initial,
                                            content_type_model=self.model, current_user=self.request.user)
        elif self.has_simple_flow:
            wfform = self.workflow_form(data=self.request.POST, initial=self.wf_initial,
                                        content_type_model=self.model, current_user=self.request.user)
        else:
            wfform = None
            self.form.wfform = wfform
            if self.form.is_valid():
                x = self.form_valid(self.form)
                if 'submit/copy' in self.request.POST:
                    self.form.instance.pk = None
                    s = super().get_context_data(form=self.form)
                    return self.render_to_response(s)
                else:
                    return x
            if not self.form.is_valid():
                print(self.form.errors.as_data())
                return self.form_invalid(self.form)

        self.form.wfform = wfform
        self.formset = self.get_formset_from_struct()(self.request.POST, self.request.FILES,
                                                      instance=self.form.instance,
                                                      form_kwargs={
                                                          "constraint": {
                                                              "wf_access": True,
                                                              'form_state': self.state_index,
                                                              'request': self.request,
                                                              'form_constraint': self.flow_config.get(
                                                                  'flow_form_constraint'),
                                                              'formset_constraint': self.flow_config.get(
                                                                  'flow_formset_constraint')
                                                          }
                                                      }) if self.has_formset else None
        wf_form_valid = wfform.is_valid()
        if self.formset:
            if self.form.is_valid() and wf_form_valid and self.formset.is_valid():
                x = self.form_valid(self.form)
                if 'submit/copy' in self.request.POST:
                    self.form.instance.pk = None
                    return self.render_to_response(super().get_context_data(form=self.form))
                else:
                    return x
            else:
                return self.render_to_response(
                    self.get_context_data(form=self.form, workflow_form=wfform, formset=self.formset))
        elif self.form.is_valid() and wf_form_valid:
            x = self.form_valid(self.form)
            if 'submit/copy' in self.request.POST:
                self.form.instance.pk = None
                return self.render_to_response(super().get_context_data(form=self.form))
            else:
                return x
        else:
            self.formset = self.get_formset_from_struct()(self.request.POST, self.request.FILES, instance=self.form.instance,
                                                          form_kwargs={
                                                              "constraint": {
                                                                  "wf_access": True,
                                                                  'form_state': self.state_index,
                                                                  'request': self.request,
                                                                  'form_constraint': self.flow_config.get(
                                                                      'flow_form_constraint'),
                                                                  'formset_constraint': self.flow_config.get(
                                                                      'flow_formset_constraint')
                                                              }
                                                          }) if self.has_formset else None
            # return self.form_invalid(self.form)
            self.formset.is_valid()
            return self.render_to_response(self.get_context_data(form=self.form, workflow_form= wfform, formset=self.formset))
            # self.form_invalid(self.form)
        # if not self.form.is_valid():
        #     print(self.form.errors.as_data())
        #     return self.form_invalid(self.form)
        # if not wfform.is_valid():
        #     print(wfform.errors.as_data())
        #     return self.form_invalid(self.form)

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
        workflow_form = kwargs.get('workflow_form')
        self.profile = Profile.get_or_create(self.request.user)
        context = KTLayout.init(context)
        context['has_flow'] = self.has_flow
        if self.has_flow:
            context['workflow_form'] = workflow_form or self.workflow_form(
                                                          content_type_model=self.model,
                                                          initial=self.wf_initial,
                                                          current_user=self.request.user,
                                                          )

            context['flow_state_index'] = self.state_index
            context['active_state'] = self.active_state
            context['flow_state_list'] = self.flow_config.get('flow_state_list')
            context['belong_to_group'] = self.wf_initial.get('belong_to_group')
            context['current_user_groups'] = self.request.user.groups.values_list('name', flat=True)
            context['wf_last_step_is_open'] = self.wf_last_step_is_open
            context['flow_admin'] = FlowAdminGroup.is_admin_of_group(self.request.user, self.flow_config.get('flow_users_groups')[self.state_index])
            if flow := self.get_flow(self.object):
                context['flow'] = flow.order_by('-id')

            try:
                context['finish'] = self.finish
            except Exception as e:
                context['finish'] = False
                print('firm error ', __file__, e.__traceback__.tb_lineno, e)

        if self.has_simple_flow:
            context['workflow_form'] = self.workflow_form(
                content_type_model=self.model,
                initial=self.wf_initial,
                current_user=self.request.user,
            )

        context['object_logs'] = ChangeLog.get_log(self.object)
        try:
            context['formset'] = self.formset(instance=self.object, form_kwargs={
                                                      "constraint": {
                                                          "wf_access": self.wf_access,
                                                          'form_state': self.state_index,
                                                          'request': self.request,
                                                          'form_constraint': self.flow_config.get('flow_form_constraint'),
                                                          'formset_constraint': self.flow_config.get('flow_formset_constraint')
                                                          }
                                                  }) if self.formset else self.formset
        except:
            context['formset'] = self.formset

        context['allow_next'] = True
        print(__file__, 'super class context', context.get('current_user_groups'))
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        fields_access = self.field_access_by_user_permission()

        try:
            flow_user_groups = self.flow_config.get('flow_users_groups', [])
            try:
                belong_to_group = self.flow_config.get('flow_users_groups')[self.state_index] if self.has_flow else None
            except Exception as e:
                belong_to_group = None
                print('firm error ', __file__, e.__traceback__.tb_lineno, e)

            """initial work flow form kwargs"""
            last_flow_objs = self.get_flow(self.object)

            from_user_ = None
            if self.state_index == 0 and not last_flow_objs:
                from_user_ = None
                print(__file__,'user none')

            elif self.state_index is not None and last_flow_objs.last().wf_status == 2:  # previous step is `back`
                from_user_ = last_flow_objs.last().to_user

            elif self.state_index is not None and last_flow_objs.last().wf_status == 3:  # previous step is `next`
                from_user_ = last_flow_objs.last().to_user

            elif self.state_index is not None and last_flow_objs.last().wf_status == 4:  # previous step is `change user`
                from_user_ = get_user_model().objects.filter(
                        id=last_flow_objs.last().to_user_id).first() if last_flow_objs else None

            elif self.state_index is not None and last_flow_objs.last().wf_status == 5:  # previous step is `first draft`
                from_user_ = last_flow_objs.last().from_user

            try:
                """work flow last step to_user should be to current user"""
                if flow_user_groups:
                    if self.state_index == 0 and flow_user_groups[0] == flow_user_groups[1]:
                        to_user = self.request.user
                    elif self.state_index is not None and self.state_index + 1 == len(self.flow_config.get('flow_state_list')):
                        to_user = self.get_flow_user(flow_user_groups[self.state_index]) if self.has_flow else None
                    elif self.state_index is not None:
                        to_user = self.get_flow_user(flow_user_groups[self.state_index + 1]) if self.has_flow else None

            except Exception as e:
                print('error: ', __file__, e.__traceback__.tb_lineno, e)
                to_user = None

            if self.has_flow:
                self.wf_access = wf_access = from_user_ == self.request.user or self.request.user.is_superuser or \
                    FlowAdminGroup.is_admin_of_group(self.request.user, flow_user_groups[self.state_index]) or \
                    (belong_to_group in self.request.user.groups.values_list('name', flat=True) and
                    (from_user_ == self.request.user or self.state_index == 0) and not last_flow_objs)
                # if self.object.cancel:
                #     self.wf_access = False

            if self.has_flow:
                if flow := self.get_flow(self.object):
                    print(__file__, flow.order_by('id').last())
                    last_flow = flow.order_by('id').last()
                    self.finish = True if last_flow.wf_status == 3 and last_flow.state == self.flow_config.get('flow_state_list')[-2] else None
                if self.finish and not self.wf_last_step_is_open:
                    wf_access = False
                self.wf_initial = {
                    'wf_access': wf_access,
                    'from_user': from_user_,
                    'to_user': to_user,
                    'state': self.flow_config.get('flow_state_list')[self.state_index] if self.has_flow else None,
                    'state_index': self.state_index,
                    'belong_to_group': belong_to_group,
                    'action': self.flow_config.get('flow_action'),
                    'deadline': datetime.datetime.now() + datetime.timedelta(days=self.flow_config.get('flow_deadline')[self.state_index]) if self.has_flow else None,
                    'flow_config': self.flow_config,
                    'create': False if self.object else True
                }
            elif self.has_simple_flow:
                self.wf_access = True
                self.wf_initial = {
                    'wf_access': self.wf_access,
                    'from_user': None,
                    'to_user': None,
                    'state': None,
                    'state_index': 0,
                    'belong_to_group': None,
                    'action': None,
                    'deadline': None,
                    'flow_config': {},
                    'create': False if self.object else True
                }

            """initial main form kwargs"""
            kwargs['initial'] = {
                "constraint": {
                    'form_state': self.state_index,
                    'request': self.request,
                    "wf_access": self.wf_access,
                    'form_constraint': self.flow_config.get('flow_form_constraint'),
                    'formset_constraint': self.flow_config.get('flow_formset_constraint'),
                    },
                'permission_access': fields_access,
                                 'wf_access': wf_access if self.has_flow else True,
                                 }
        except Exception as e:
            print('error: ', __name__, 'line',  e.__traceback__.tb_lineno, e)

            # self.wf_initial = {'create': self.create, 'flow_config': self.flow_config, }
            self.wf_initial = {
                    'wf_access': wf_access,
                    'from_user': from_user_,
                    'to_user': to_user,
                    'state': self.flow_config.get('flow_state_list')[self.state_index] if self.has_flow else None,
                    'state_index': self.state_index,
                    'belong_to_group': belong_to_group,
                    'action': self.flow_config.get('flow_action'),
                    'deadline': datetime.datetime.now() + datetime.timedelta(days=self.flow_config.get('flow_deadline')[self.state_index]) if self.has_flow else None,
                    'flow_config': self.flow_config,
                    'create': False if self.object else True
                }
            kwargs['initial'] = {
                            "constraint": {
                                'form_state': self.state_index,
                                'request': self.request,
                                "wf_access": self.wf_access,
                                'form_constraint': self.flow_config.get('flow_form_constraint'),
                                'formset_constraint': self.flow_config.get('flow_formset_constraint'),
                                },
                                 'create': self.create
                                 }
        return kwargs

    def form_valid(self, form):
        if form.is_valid():
            """save main form"""
            old_obj = self.model.objects.filter(Q(id=self.kwargs.get('pk')) | Q(id=self.kwargs.get('id'))).first()

            if old_obj:
                old_obj.attach_image_file(old_obj)
                last_flow_obj = self.get_flow(old_obj)

                if self.has_flow and 'back' in self.request.POST:
                    wf_obj = form.wfform.save(commit=False)
                    wf_obj.from_user = self.request.user
                    wf_obj.object_id = old_obj.id
                    wf_obj.content_type = ContentType.objects.filter(app_label=old_obj._meta.app_label,
                                                                     model=old_obj._meta.model_name).first()

                    flow_items = self.get_flow(self.object).filter(wf_status=3).order_by('-id')
                    pad = 2 if self.state_index >= 2 else 1
                    for item in flow_items:
                        if item.state == self.flow_config.get('flow_state_list')[self.state_index - pad]:
                            # wf_obj.to_user = item.from_user
                            wf_obj.to_user = item.to_user if pad >= 2 else item.from_user
                            wf_obj.deadline = item.deadline
                            # wf_obj.wf_status = 2  # back
                            print(__file__, '========= save as back')
                            break
                    # wf_obj.save_user(self.request)
                    wf_obj.wf_status = 2  # back
                    wf_obj.extra_data.request = self.request
                    wf_obj.current_state_name = self.flow_config.get('flow_state_list')[self.state_index - 1]
                    wf_obj.save()
                    self.object.last_work_flow = wf_obj
                    self.object.extra_data.request = self.request
                    self.object.save()
                    return HttpResponseRedirect(self.get_success_url())
                    # return super().form_valid(form)

            if 'back' in self.request.POST:
                return super().form_valid(form)
            elif 'canceled' in self.request.POST:
                old_obj.cancel = True
                old_obj.save()
                old_obj.save_comment(request=self.request)
                self.object.cancel = True
                self.object.save()
                return HttpResponseRedirect(self.get_success_url())
                # return super().form_valid(form)
            elif 'uncanceled' in self.request.POST:
                old_obj.cancel = False
                old_obj.save()
                old_obj.save_comment(request=self.request)
                self.object.cancel = False
                self.object.save()
                return HttpResponseRedirect(self.get_success_url())
                # return super().form_valid(form)
            else:
                form.instance.extra_data.request = self.request
                new_obj = form.save(commit=True)

            # new_obj = form.save(commit=True) if 'back' in self.request.POST else None

            if new_obj:
                last_flow_obj = self.get_last_flow(new_obj)
                """save wf if user change"""
                if self.has_flow and 'change_user' in self.request.POST:
                    wf_obj = form.wfform.save(commit=False)
                    wf_obj.from_user = self.request.user
                    wf_obj.to_user = form.wfform.cleaned_data.get('to_current_group_user')
                    wf_obj.object_id = new_obj.id
                    wf_obj.content_type = ContentType.objects.filter(app_label=new_obj._meta.app_label,
                                                                     model=new_obj._meta.model_name).first()
                    wf_obj.wf_status = 4  # change user
                    wf_obj.extra_data.request = self.request
                    wf_obj.current_state_name = self.flow_config.get('flow_state_list')[self.state_index]
                    # wf_obj.save_user(self.request)
                    wf_obj.save()
                    new_obj.last_work_flow = wf_obj
                    new_obj.save()

                    print(__file__, '========= wf save as change user')
                    return HttpResponseRedirect(self.get_success_url())
                elif self.has_flow and ('next' in self.request.POST or 'submit' in self.request.POST or 'submit/copy' in self.request.POST or 'submit/copy_q' in self.request.POST):
                    """save workflow form (main)"""
                    if form.wfform.is_valid():
                        wf_obj = form.wfform.save(commit=False)
                        wf_obj.from_user = self.request.user
                        wf_obj.object_id = new_obj.id
                        wf_obj.content_type = ContentType.objects.filter(app_label=new_obj._meta.app_label,
                                                                         model=new_obj._meta.model_name).first()

                        wf_obj.wf_status = 3  # next
                        # if 'next' in self.request.POST:
                        #     """to_user submit as default to next user"""
                        #     wf_obj.wf_status = 3  # next
                        #
                        # if 'submit' in self.request.POST:
                        #     """to_user submit as default to next user"""
                        #     wf_obj.wf_status = 3  # next

                        # wf_obj.save_user(self.request)
                        wf_obj.extra_data.request = self.request
                        wf_obj.current_state_name = self.flow_config.get('flow_state_list')[self.state_index + 1]  # Todo test for last step [index error]
                        wf_obj.save()
                        wf_obj.final_save()
                    else:
                        print(form.wfform.errors.as_data())
                elif self.has_flow and 'draft' in self.request.POST:
                    if 'to_user' in form.wfform.changed_data:
                        """ if to_user change save new flow object `save as change_user` """
                        wf_obj = form.wfform.save(commit=False)
                        wf_obj.from_user = self.request.user
                        wf_obj.object_id = new_obj.id
                        wf_obj.content_type = ContentType.objects.filter(app_label=new_obj._meta.app_label,
                                                                         model=new_obj._meta.model_name).first()
                        wf_obj.wf_status = 4  # change user
                        print('========= workflow save as next')
                        wf_obj.extra_data.request = self.request
                        wf_obj.current_state_name = self.flow_config.get('flow_state_list')[self.state_index]
                        wf_obj.save()
                        # wf_obj.save_user(self.request)
                    elif not form.wfform.cleaned_data.get('from_user'):
                        """ if state 0 and from_user is None `save as first_draft` """
                        wf_obj = form.wfform.save(commit=False)
                        wf_obj.from_user = self.request.user
                        wf_obj.to_user = self.request.user
                        wf_obj.object_id = new_obj.id
                        wf_obj.content_type = ContentType.objects.filter(app_label=new_obj._meta.app_label,
                                                                         model=new_obj._meta.model_name).first()
                        wf_obj.wf_status = 5  # first draft
                        print('========= workflow save as next')
                        wf_obj.extra_data.request = self.request
                        wf_obj.current_state_name = self.flow_config.get('flow_state_list')[0]
                        wf_obj.save()
                        # wf_obj.save_user(self.request)
                try:
                    """save main form image and file"""
                    if form.image_model and form.image_groups:
                        new_obj.save_image(request=self.request,
                                           image_groups=form.image_groups,
                                           image_model=form.image_model,
                                           obj=new_obj,
                                           input_prefix='image',
                                           )
                    if form.file_model and form.file_groups:
                        new_obj.save_file(request=self.request,
                                          file_groups=form.file_groups,
                                          file_model=form.file_model,
                                          obj=new_obj,
                                          input_prefix='file'
                                          )

                    """***NEW***"""
                    if form.has_comment:
                        new_obj.save_comment(request=self.request)
                    """***NEW***"""

                    """***NEW***"""
                    if form.has_addition:
                        new_obj.save_additions(request=self.request)

                    """***NEW***"""

                except Exception as e:
                    print('error: ', e.__traceback__.tb_lineno, e)

                """save formset"""
                if self.has_formset:

                    old_details_ = getattr(new_obj, self.related_name_fk, None)
                    old_details = []
                    if old_details_:
                        old_details = list(old_details_.all())
                        old_details = [old_detail.attach_image_file(old_detail) for old_detail in old_details]

                    self.formset = self.get_formset_from_struct()(self.request.POST, self.request.FILES, instance=new_obj, form_kwargs={
                        "constraint": {
                            "wf_access": True,
                            'form_state': self.state_index,
                            'request': self.request,
                            'form_constraint': self.flow_config.get('flow_form_constraint'),
                            'formset_constraint': self.flow_config.get('flow_formset_constraint')
                        }
                    })
                    if self.formset.is_valid():
                        if hasattr(self.formset.forms[0], 'nested'):
                            fo = self.formset.save(request=self.request, related_name_fk=self.related_name_fk)
                        else:
                            fo = self.formset.save()
                    else:
                        print(self.formset.errors)
                        fo = None

                    if fo:
                        for idx, fs_obj in enumerate(fo):
                            fs_obj.extra_data.request = self.request
                            fs_obj.save()
                            # fs_obj.save_user(self.request)
                            setattr(fs_obj, self.formset_fk_field, new_obj)
                            if self.formset.form.image_model and self.formset.form.image_groups:
                                """save formset image and file"""
                                fs_obj.save_image(
                                    request=self.request,
                                    image_groups=self.formset.form.image_groups,
                                    image_model=self.formset.form.image_model,
                                    obj=fs_obj,
                                    fk=self.related_name_fk,
                                    form_idx=idx,
                                )
                            if self.formset.form.file_model and self.formset.form.file_groups:
                                fs_obj.save_file(
                                    request=self.request,
                                    file_groups=self.formset.form.file_groups,
                                    file_model=self.formset.form.file_model,
                                    obj=fs_obj,
                                    fk=self.related_name_fk,
                                    form_idx=idx,
                                )

                    """save formset log"""
                    new_details = getattr(new_obj, self.related_name_fk, None)
                    if new_details:
                        new_details = list(new_details.all())

                    for d in new_details:
                        # ToDo make dynamic
                        app_label = d._meta.app_label
                        model_name = d._meta.model_name
                        ctt_id = ContentType.objects.get_for_model(d._meta.model).pk
                        object_id = d.pk
                        prefix = f'{app_label}__{model_name}__{ctt_id}__{object_id}'
                        comment_form = CommentsForm(self.request.POST, prefix=prefix)
                        if comment_form.is_valid():
                            comment_form.instance.extra_data.request = self.request
                            cmnt = comment_form.save()

                """save main form log"""
                new_obj.attach_image_file(new_obj, form)
                # new_obj = self.attach_image_file(new_obj, form)
                # if not old_obj:
                #     # new_obj.extra_data.request = self.request
                #     new_obj.save_log(self.request, obj=new_obj, action=1)
                # else:
                #     # new_obj.extra_data.request = self.request
                #     new_obj.save_log(self.request, obj=new_obj, old=old_obj, action=2)

                print('form valid base view')

                if self.has_simple_flow:
                    wf_obj = form.wfform.save(commit=False)
                    wf_obj.from_user = self.request.user
                    wf_obj.object_id = new_obj.id
                    wf_obj.content_type = ContentType.objects.filter(app_label=new_obj._meta.app_label,
                                                                     model=new_obj._meta.model_name).first()
                    wf_obj.wf_status = 3  # next
                    print('========= workflow save as next')
                    wf_obj.extra_data.request = self.request
                    wf_obj.current_state_name = self.flow_config.get('flow_state_list')[self.state_index + 1]
                    wf_obj.save()
                    # wf_obj.save_user(self.request)
                # form.instance.pk = None
                try:
                    new_obj.last_work_flow = wf_obj
                    new_obj.save()
                except Exception as e:
                    show_error(e, __file__)
                return super().form_valid(form)
            return super().form_valid(form)
        return HttpResponseRedirect('.')


class Base:
    @classmethod
    def get_view_config(cls, file, view):
        import json
        with open(file, 'r', encoding='utf-8') as f:
            json_config: dict = json.load(f)
            return json_config.get(view)

    @staticmethod
    def get_flow_config(file, view):
        from translator import get_text as _
        res = {
            'flow_name': '',
            'flow_action': '',
            'flow_state_list': [],
            'flow_users_groups': [],
            'flow_deadline': [],
            'flow_form_constraint': [],
            'flow_formset_constraint': []
        }
        cfg: dict = Base.get_view_config(file, view)
        if wf_config := cfg.get('workflow'):
            res['flow_name'] = _(wf_config.get('name'))
            res['flow_action'] = _(wf_config.get('action'))
            if config_list := wf_config.get('list'):
                for config in config_list:
                    res['flow_state_list'].append(config.get('state'))
                    res['flow_users_groups'].append(config.get('group'))
                    res['flow_deadline'].append(config.get('deadline'))
                    res['flow_form_constraint'].append(config.get('form_constraint'))
                    res['flow_formset_constraint'].append(config.get('formset_constraint'))

        return res


def download_excel(request, *args, **kwargs):
    print('get export excel')
    model_name = request.GET.get('model_name')
    app_name = request.GET.get('app_label')
    header = request.GET.get('header')

    from django.apps import apps
    model = apps.get_model(app_label=app_name, model_name=model_name)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="mydata.xlsx"'

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = 'My Data'

    print(header)
    header = header.split(' ')
    print(header)
    for col_num, column_title in enumerate(header, 1):
        cell = worksheet.cell(row=1, column=col_num)
        cell.value = column_title

    queryset = model.objects.all().values_list(*header)
    print(len(queryset))
    for row_num, row in enumerate(queryset, 1):
        for col_num, cell_value in enumerate(row, 1):
            cell = worksheet.cell(row=row_num + 1, column=col_num)
            cell.value = cell_value

    workbook.save(response)
    print(' download response')
    return response


class JsonTemplateResponseMixin:
    def dispatch(self, request, *args, **kwargs):
        if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            print(request.GET)

        return super().dispatch(request, *args, **kwargs)


class CommentsFormView(View):
    def get(self, request, *args, **kwargs):
        from django.apps import apps
        from comments.models import CommentSeen
        app_label = kwargs.get("app_label")
        model_name = kwargs.get('model_name')
        ctt_id = kwargs.get('content_type')
        object_id = kwargs.get('object_id')
        comment_type = self.request.GET.get('comment_type')
        model = apps.get_model(app_label, model_name)
        obj = model.objects.filter(pk=object_id).first()
        comments = Comments.objects.none()
        if comment_type == 'cancel':
            kwargs['submit_type'] = 'cancel'
            # comments = obj.comments.all().filter(comment_title="C").order_by('-created_date')
            comments = obj.comments.all().order_by('-created_date')
        elif comment_type == 'comment':
            kwargs['submit_type'] = 'save_comment'
            # comments = obj.comments.all().filter(~Q(comment_title="C")).order_by('-created_date')
            comments = obj.comments.all().order_by('-created_date')
        prefix = f'{app_label}__{model_name}__{ctt_id}__{object_id}'
        kwargs['comment_title'] = self.request.GET.get('comment_title', '')
        kwargs['comment_content'] = self.request.GET.get('comment_content', '')

        form = CommentsForm(prefix=prefix, initial=kwargs)

        for comment in comments:
            try:
                comment_seen, _ = CommentSeen.objects.get_or_create(comment=comment,
                                                                    creator_user=request.user,
                                                                    editor_user=request.user)
                # comment_seen.save_user(self.request)
                comment_seen.extra_data.request = self.request
                comment_seen.save()
            except Exception:
                continue

        context = {'form': form,
                   'object_id': object_id,
                   'ctt_id': ctt_id,
                   'comments': comments,
                   'comment_type': comment_type,
                   'cancel_btn_text': 'uncanceled' if getattr(obj, 'cancel', None) else 'canceled',
                   'request': request}
        x = render_to_string('core/partial/form.html', context)

        return JsonResponse({'res': x})


############ new ##############hajinezhad###############

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
        app_label = kwargs.pop('app_label', None)
        model_name = kwargs.pop('model_name', None)
        if app_label and model_name:
            self.model = apps.get_model(app_label=app_label.lower(), model_name=model_name.lower())
        return kwargs


class BaseCustomCreateView(BaseCustomView, ProcessFormView):
    template_name = ''

    def __init__(self):
        super().__init__()
        self.form = None
        self.context = None
        self.status = None
        self.instance = None

    def setup(self, request, *args, **kwargs):
        self.instance = None
        try:
            super().setup(request, *args, **kwargs)
            kwargs = self.get_model(**kwargs)
            if pk := request.GET.get('pk'):
                self.instance = self.model.objects.filter(pk=pk).first()
                if not self.instance:
                    self.status = 400
                    self.context = {'status': self.status}
                    return self.context
            else:
                self.instance = self.model()
            form_structures = json.loads(request.POST.get('form_structures','{}'))
            if not form_structures:
                form_structure_index = request.GET.get('form_structure_index')
                if form_structure_index:
                    self.instance.active_form_structure_index = form_structure_index
            else:
                self.instance.form_structures = form_structures
            self.form = self.instance.get_view_forms(request, *args, **kwargs)
            self.status = 200
            self.context = {'form': self.form, 'status': self.status}
            return self.context
        except Exception as e:
            self.status = 500
            self.context = {'status': self.status, 'error': str(e)}
            return self.context
        finally:
            ...

    def get(self, request, *args, **kwargs):
        # return render(request, 'core/create/base.html', context)
        return self.context

    def post(self, request, *args, **kwargs):
        return self.context
        # return render(request, 'core/create/base.html', context)


class CustomCreateView(BaseCustomCreateView):

    def get(self, request, *args, **kwargs):
        super().get(request,*args,**kwargs)
        return render(request, 'core/create/base.html', self.context)

    def post(self, request, *args, **kwargs):
        super().post(request,*args,**kwargs)
        if self.form and self.form.is_valid():
            self.form.save()
            return redirect(f'{self.request.path_info}?pk={self.form.instance.pk}', )
        return render(request, 'core/create/base.html', self.context)


class CustomCreateViewAjax(BaseCustomCreateView):

    def __init__(self):
        super().__init__()
        self.data = None

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        # self.form.instance.get_workflow_forms()
        from django.forms import formset_factory
        from django.forms import inlineformset_factory
        from django.contrib.contenttypes.forms import BaseGenericInlineFormSet, generic_inlineformset_factory
        # workflow_fs = self.instance.WorkFlowForms()
        # ArticleFormSet = formset_factory(self.form.__class__, extra=2, max_num=1)
        # wfs = generic_inlineformset_factory(self.form._meta.model,form=self.form,)
        # d = ArticleFormSet()
        if self.form:
            self.data = self.form.serialized()

    def get(self, request, *args, **kwargs):
        super().get(request, *args, **kwargs)
        return JsonResponse({'data': self.data, 'status': self.status})

    def post(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)
        if self.form and self.form.is_valid():
            self.form.save()
        return JsonResponse({'data': self.data, 'status': self.status})


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

