from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured

from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget

from accounts.models import User
from core.forms import CustomBaseModelForm

from .models import WorkFlow, FlowAdminGroup
from django import forms

from translator import get_text as _
from notifications.models import Messages

class WorkFlowModelForm(CustomBaseModelForm):
    belong_to_group_ = forms.CharField(max_length=255)
    # to_current_group_user = forms.ModelChoiceField(
    #                     queryset=[],
    #                     to_field_name='pk',  # set as select option value
    #                     required=False,
    #                     widget=forms.Select(),
    #                     label=_('to_user'),
    #                 )

    class Meta:
        model = WorkFlow
        fields = '__all__'

    def __init__(self, content_type_model=None, current_user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            # print(self.initial)
            flow_config = self.initial.get('flow_config')
            flow_user_groups = flow_config.get('flow_users_groups', [])
            state_index = self.initial.get('state_index')
            belong_to_group = self.initial.get('belong_to_group')
            current_user_groups = current_user.groups.values_list('name', flat=True)
            self.owner_user = self.initial.get('from_user')

            self.fields['deadline'] = JalaliDateField(label=_('deadline'), widget=AdminJalaliDateWidget, required=False)
            self.fields['deadline'].initial = self.initial.get('deadline')

            # current_state_user_list = User.objects.filter(groups__name__in=[flow_user_groups[state_index]]).distinct()
            current_state_user_list = User.objects.filter(groups__name__in=[belong_to_group]).distinct()
            self.fields['to_current_group_user'] = forms.ModelChoiceField(
                                                    queryset=current_state_user_list,
                                                    to_field_name='pk',  # set as select option value
                                                    required=False,
                                                    widget=forms.Select(),
                                                    label=_('to user'),
                                                )

            if state_index is not None and state_index < len(flow_user_groups) - 1:
                # try:
                next_state_user_list = User.objects.filter(groups__name__in=[flow_user_groups[state_index + 1]]).distinct()
                prev_state_user_list = None
                # except IndexError:
                #     pass
                    # next_state_user_list = User.objects.filter(groups__name__in=[flow_user_groups[state_index]]).distinct()
            else:
                next_state_user_list = None
                prev_state_user_list = User.objects.filter(groups__name__in=[flow_user_groups[state_index]]).distinct() if flow_user_groups else None

            if self.initial.get('wf_access'):
                self.make_optional(self.fields)

                if self.initial.get('from_user'):
                    self.fields['from_user'].queryset = get_user_model().objects.filter(id=self.initial.get('from_user').id)

                # if content_type_model:
                #     self.fields['action'] = forms.ModelChoiceField(
                #         queryset=[],#WorkFlowAction.objects.filter(content_type__model=content_type_model._meta.model_name),
                #         to_field_name='pk',  # set as select option value
                #         required=False,
                #         widget=forms.Select(),
                #         label=_('action'),
                #     )
                #     self.fields['action'].widget.attrs['class'] = 'LTR-RTL'
                #     self.fields['action'].initial = self.initial.get('action')

                # if next_state_user_list:
                self.fields['to_user'].queryset = next_state_user_list or prev_state_user_list

                self.make_disable(['from_user', 'action', 'state', 'belong_to_group', 'belong_to_group_'])
                # if FlowAdminGroup.is_group_admin(current_user, belong_to_group) or current_user.is_superuser:
                if FlowAdminGroup.is_admin_of_group(current_user, belong_to_group) or current_user.is_superuser:
                    pass
                else:
                    self.make_disable(['to_user', 'to_current_group_user'])

            else:
                self.make_disable(self.fields)
                if self.initial.get('from_user'):
                    self.fields['from_user'].queryset = get_user_model().objects.filter(id=self.initial.get('from_user').id)
                # if next_state_user_list:
                self.fields['to_user'].queryset = next_state_user_list or prev_state_user_list

            if self.initial.get('to_user'):
                self.fields['to_user'].required = True

            self.make_hidden(['belong_to_group', 'to_user'])
            self.fields['belong_to_group_'].label = _('belong to group')
            if not FlowAdminGroup.get_name(belong_to_group):
                raise ImproperlyConfigured(f"table flow admin don't have value for <{belong_to_group}>")
            self.fields['belong_to_group_'].widget.attrs['placeholder'] = FlowAdminGroup.get_name(belong_to_group)
        except Exception as e:
            print('error: ', __file__,  e.__traceback__.tb_lineno, e)

