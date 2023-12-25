from typing import Dict

from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.views.generic.edit import FormMixin, ModelFormMixin

from accounts.models import ManageFormField
from tools.utils import show_error


class IMEIAdminMixin:
    pass
    # def dispatch(self, request, *args, **kwargs):
    #     for role in request.user.role.all():
    #         if str(role) == 'imei admin':
    #             return super().dispatch(request, *args, **kwargs)
    #     raise Http404


class FormFieldAccessMixin(FormMixin):
    def formset_field_access_by_config(self, config: Dict):
        hide = config.get('hide')
        read = config.get('read')
        print(hide)
        print(read)

    def form_field_access_by_config(self, config: Dict):
        hide = config.get('hide')
        read = config.get('read')
        print(hide)
        print(read)

    def field_access_by_user_permission(self):
        if self.request.user.is_superuser:
            return {}
        try:
            app_label = self.model._meta.app_label
            model_name = self.model._meta.model_name
            user_groups = self.request.user.groups.all()
            print(app_label, model_name)
            p = ManageFormField.objects.filter(content_type__app_label=app_label,
                                               content_type__model=model_name,
                                               allowed_groups__in=user_groups)
            print('===============', p)
            fields_access = {}
            if p:
                for i in p:
                    fields_access[i.action] = []
                for item in p:
                    fields_access[item.action] += [i for i in item.fields_name.split(',')]
                print()
                return fields_access
        except Exception as e:
            show_error(e, __file__)
        # return None, None
        return {}

    def formset_field_access_by_user_permission(self):
        # if self.request.user.is_superuser:
        #     return None, None
        try:
            app_label = self.formset_model._meta.app_label
            model_name = self.formset_model._meta.model_name
            user_groups = self.request.user.groups.all()
            print(app_label, model_name)
            p = ManageFormField.objects.filter(content_type__app_label=app_label,
                                               content_type__model=model_name,
                                               allowed_groups__in=user_groups)
            # print('===============', p)
            fields_access = {}
            if p:
                for i in p:
                    fields_access[i.action] = []
                for item in p:
                    fields_access[item.action] += [i for i in item.fields_name.split(',')]
                    # fields += [i for i in item.fields_name.split(',')]
                # fields = list(map(lambda x: x.strip(), item.fields_name.split(',') for item in p ))
                print()
                return fields_access
                # return fields, p.action
        except Exception as e:
            show_error(e, __file__)
        return {}

    def field_access_by_user_permission_(self, request=None):
        if request and request.user.is_superuser:
            return {}
        try:
            app_label = self.Meta.model._meta.app_label
            model_name = self.Meta.model._meta.model_name
            user_groups = request.user.groups.all()
            p = ManageFormField.objects.filter(content_type__app_label=app_label,
                                               content_type__model=model_name,
                                               allowed_groups__in=user_groups)
            fields_access = {}
            temp = {}
            if p:
                for i in p:
                    temp[i.action] = []
                for item in p:
                    temp[item.action] += [i for i in item.fields_name.split(',')]
                print()
                fields_access['access_limit'] = temp
                return fields_access
        except Exception as e:
            show_error(e, __file__)
        return {}

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = super().get_form_kwargs()
        if hasattr(self, "object"):
            kwargs.update({"instance": self.object})
        return kwargs
