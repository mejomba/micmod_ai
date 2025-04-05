from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.views.generic.detail import SingleObjectMixin

from .forms import WorkFlowModelForm
from .models import WorkFlow


class FlowBaseView(SingleObjectMixin):
    has_flow = None
    has_simple_flow = None
    flow_config = {
        'flow_name': '',
        'flow_action': '',
        'flow_state_list': [],
        'flow_users_groups': [],
        'flow_users_list': [],
        'flow_users_perm': [],
        'flow_deadline': [],
        'flow_extra': {},
    }
    wf_to_user_permission = None
    wf_initial = {'from_user': None}
    workflow_form = WorkFlowModelForm
    flow_model = WorkFlow
    active_state = True
    state_index = None
    # wf_finish = False
    wf_last_step_is_open = None

    def save_flow(self, request, form=None, obj=None, **kwargs):
        state = kwargs.get('state')
        wf_description = kwargs.get('wf_description')
        from_user = kwargs.get('from_user')
        to_user = kwargs.get('to_user')
        current_state_name = kwargs.get('current_state_name')
        object_id = kwargs.get('object_id') or self.object.pk
        wf_status = kwargs.get('wf_status') or 3
        flow_data = {
            "wf_status": wf_status,
            "action": 'ایجاد خودکار',
            "flow_name": 'سفارش',
            "state": state,
            "wf_description": wf_description,
            "belong_to_group": 'order_admin',
            "object_id": object_id,
            "content_type": ContentType.objects.get_for_model(self.object),
            "creator_user": request.user,
            "editor_user": request.user,
            "from_user": from_user,
            "to_user": to_user,
            "current_state_name": current_state_name,
        }

        wf = WorkFlow.objects.create(**flow_data)
        self.object.last_work_flow = wf
        self.object.save()

    def get_flow(self, obj):
        if not obj:
            return None
        content_type = ContentType.objects.filter(model=obj._meta.model_name, app_label=obj._meta.app_label).first()
        return self.flow_model.objects.filter(object_id=obj.id, content_type=content_type).order_by('id')

    def get_flow_user(self, group: str):
        user_list = get_user_model().objects.filter(groups__name__in=[group]).distinct().order_by('id')
        try:
            last_wf = self.object.last_work_flow
            if last_wf.current_state_name == 'استعلام قیمت' or last_wf.current_state_name == 'تایید پیش فاکتور':
                for u in user_list:
                    if last_wf.to_user in u.team.all():
                        return u
        except Exception as e:
            pass
        """if only one user exist"""
        if len(user_list) == 1:
            return user_list.first()

        """if multiple user exist, select next user from last work flow"""
        if len(user_list) > 1:
            """if previous step is change user, select that"""
            flow_belong_to_object = self.get_flow(self.get_object())
            # if flow_belong_to_object:
            #     if flow_belong_to_object.last().wf_status == 4:  # change user status
            #         state = flow_belong_to_object.last().state
            #         try:
            #             return flow_belong_to_object.order_by('id').filter(state=state, wf_status=3).last().to_user
            #         except Exception as e:
            #             print('firm error ', __file__, e.__traceback__.tb_lineno, e)
            #             return user_list.first()
            #         return flow_belong_to_object.last().to_user

            """if any user don't have work flow, select first user"""
            if not self.flow_model.objects.filter(from_user__in=user_list):
                return user_list.first()
            flow_belong_to_group = self.flow_model.objects.filter(belong_to_group=group)

            """if flow object exist select user from that"""
            if flow_belong_to_object:
                flow_belong_to_object = flow_belong_to_object.order_by('id')
                last_change_user_qs = flow_belong_to_object.filter(wf_status=4).last()
                last_change_user = last_change_user_qs.to_user if last_change_user_qs else None
                for flow in flow_belong_to_object:
                    if last_change_user in user_list:
                        return last_change_user
                    if flow.to_user in user_list:
                        return flow.to_user

            """if flow object don't exist select user from group (normally for create step)"""
            if flow_belong_to_group:
                last_wf_user = flow_belong_to_group.order_by('id').last().from_user
                next_users = user_list.filter(id__gt=last_wf_user.id).order_by('id')
                if next_users:
                    return next_users.first()
                else:
                    return user_list.first()
        return user_list.first()

    def _get_flow_state(self, obj):
        try:
            if f := self.get_last_flow(obj):
                return f.state
        except Exception as e:
            print('error: ', __name__, 'line', e.__traceback__.tb_lineno, e)
            return None

    def get_last_flow(self, obj):
        try:
            return self.get_flow(obj).order_by('id').last() if self.get_flow(obj) else None
        except Exception as e:
            print('error: ', __name__, 'line', e.__traceback__.tb_lineno, e)
            return None

    def get_flow_index(self, obj):
        state_list = self.flow_config.get('flow_state_list')
        # if state_list is None:
        #     return None
        if s := self._get_flow_state(obj):
            if state_list.index(s) + 1 == len(state_list):
                self.active_state = False
            if f := self.get_last_flow(obj):
                if f.wf_status == 1:  # if draft
                    return state_list.index(s) if state_list.index(s) < len(state_list) - 1 else len(state_list) - 1
                elif f.wf_status == 2:  # if back
                    return state_list.index(s) - 1 if state_list.index(s) < len(state_list) - 1 else len(state_list) - 2
                elif f.wf_status == 4:  # if change user
                    return state_list.index(s)
                elif f.wf_status == 5:  # if first draft
                    return 0

            return state_list.index(s) + 1 if state_list.index(s) < len(state_list) - 1 else len(state_list) - 1
        else:
            return 0

    def is_group_admin(self, user, group):
        for g in user.flowadmingroup_set.all():
            if g.group_rel.name == group:
                return True

    def is_admin(self, obj, user):
        if obj is None:
            return True
        for access_obj in obj.get_access_object(user):
            if access_obj == obj:
                return True

    def save_flow_stack(self, flow):
        if flow and len(flow) == 1:
            flow
