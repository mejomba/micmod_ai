from django.contrib.auth.models import Group
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from core.models_contenttype import BaseContentType
from accounts.models import User
from notifications.models import Messages
from django.apps import apps

from services.notify_service import notify_wf_to_shop
from tools.utils import wf_cache
from translator import get_text as _

from inspect import stack
already_called_recursively = False


def test():
    global already_called_recursively
    function_name = stack()[1].function
    if not already_called_recursively:
        already_called_recursively = True
        print(test())  # One recursive call, leads to Recursion Detected!

    if function_name == test.__name__:
        return True
    else:
        return "Called from {}".format(function_name)

class WorkFlow(BaseContentType):
    STATUS = ((1, _('draft')), (2, _('back')), (3, _('next')), (4, _('change_user')), (5, _('first_draft')))

    wf_status = models.PositiveSmallIntegerField(verbose_name=_("status"), choices=STATUS, null=True, blank=True)
    action = models.CharField(verbose_name=_('action'), null=True, blank=True,
                              max_length=30)  # models.ForeignKey('WorkFlowAction', on_delete=models.CASCADE, related_name='workflow_action', null=True, blank=True)
    flow_name = models.CharField(max_length=100, null=True, blank=True)
    from_user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='flow_from_user',
                                  null=True, blank=True, verbose_name=_('from user'))
    to_user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='flow_to_user', verbose_name=_('to user'))
    state = models.CharField(max_length=255, null=True, blank=True, verbose_name=_('state'))
    duty = models.CharField(max_length=100, null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True, verbose_name=_('deadline'))
    wf_description = models.CharField(max_length=255, null=True, blank=True, verbose_name=_('description'))
    belong_to_group = models.CharField(max_length=255, null=True, blank=True, verbose_name=_('belong to group'))

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING, related_name='flow_content_type',
                                     null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    current_state_name = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("current_state_name"))

    extra_prefix = 'workflows'

    def __str__(self):
        return f'{self.current_state_name}'

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        x = super().save(force_insert=False, force_update=False, using=None, update_fields=None)
        # notify_wf_to_shop(self)
        return x

    def submit_flow(self):
        pass

    def flow_step_index(self):
        self.flow_step_index()

    def get_flow(self):
        return self

    def final_save(self):
        # user
        # ws_group
        # title
        # body
        # icon_url
        # link
        # read_status
        # message_type
        # send_to_group
        # content_type
        # object_id
        self.save()
        model_ = apps.get_model(app_label=self.content_type.app_label, model_name=self.content_type.model)
        if self.creator_user != self.to_user:
            Messages.send_message(
                **{
                    'creator_user_id': self.creator_user_id,
                    'user': self.to_user,
                    'title': f'{_(self.content_type.name)}| {_(self.state)}',
                    'body': f' کاربر {self.creator_user.username} فرایند این موضوع را به شما واگذار کرده است.',
                    'icon_url': getattr(model_, 'icon_url', None) or "cube-2",
                    'link': f'/{self.content_type.app_label}/{self.content_type.model}/view/{self.object_id}',
                    'content_type': self.content_type,
                    'object_id': self.object_id
                }
        )


# class WorkFlowAction(models.Model):
#     content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING, related_name='flow_action_content_type')
#     action = models.CharField(max_length=64, verbose_name=_('action'))
#
#     def __str__(self):
#         return f'{self.action}'
group_memo = dict()
target_group_memo = dict()
class FlowAdminGroup(models.Model):
    group_name = models.CharField(max_length=255, verbose_name=_('group_name'), null=True, blank=True)
    group_rel = models.ForeignKey(Group, on_delete=models.DO_NOTHING, verbose_name=_('group_rel'), null=True,
                                  blank=True, related_name='group_rel')
    group_child = models.ManyToManyField(Group, verbose_name=_('group_child'), null=True, blank=True,
                                         related_name='group_child')

    # group_rel = models.OneToOneField(Group, on_delete=models.DO_NOTHING, verbose_name=_('group_rel'), null=True, blank=True)
    # user_rel = models.ManyToManyField(User)

    def __str__(self):
        return f'{self.group_name}'

    @classmethod
    def is_group_admin(cls, user, group):
        """if user, admin of given group"""
        group_obj = Group.objects.filter(name=group).first()
        flow_admin = cls.objects.filter(group_rel=group_obj).first()
        if flow_admin:
            return user in flow_admin.user_rel.all()

    @classmethod
    @wf_cache(timeout=10)
    def is_admin_of_group_cached(cls, user_id, group_name, state):
        # from django.contrib.auth import get_user_model
        # User = get_user_model()
        # user = User.objects.select_related().get(pk=user_id)
        user = user_id

        return cls.is_admin_of_group(user, group_name)


    @classmethod
    def is_admin_of_group(cls, user, group_name, model=None) -> bool:
        """if user inside of admin group
        Args:
            user -> current user
            group_name -> real name of group, from current state of flow
        return -> bool
        """
        if isinstance(group_name, list):
            group_name = group_name[0]

        if user.is_superuser:
            return True
        
        direct_group_name = f'{model._meta.model_name.lower()}_direct_access' if model else ''
        if model and model._meta.model_name.lower() in ["item", "order"] and direct_group_name in user.groups.values_list('name', flat=True):
            return True

        current_user_group = target_group_memo.get('target_group')
        if not current_user_group:
            current_user_group = Group.objects.filter(name=group_name).first()
            target_group_memo['target_group'] = current_user_group
            group_memo['prev'] = []

        user_all_groups = list(user.groups.all())
        for my_flow_admin in cls.objects.filter(group_rel__in=user_all_groups).distinct().prefetch_related('group_child'):
            my_flow_admin_child = my_flow_admin.group_child.all()
            for ru in my_flow_admin_child:  # get all subgroups
                if ru in group_memo.get('prev', []):
                    pass  # continue
                elif current_user_group in my_flow_admin_child:  # or current_user_group in user_all_groups:
                    group_memo.clear()
                    target_group_memo.clear()
                    return True
                else:
                    group_memo.get('prev', []).append(ru)
                    return cls.is_admin_of_group(user, ru.name)

        # user_all_groups = user.groups.all()
        # for ug in user_all_groups:
        #     for my_flow_admin in cls.objects.filter(group_rel=ug):
        #         my_flow_admin_child = my_flow_admin.group_child.all()
        #         for ru in my_flow_admin_child:  # get all subgroups
        #             if ru in group_memo.get('prev', []):
        #                 # group_memo.clear()
        #                 # group_memo['prev'] = None
        #                 # continue
        #                 pass #continue
        #             elif current_user_group in my_flow_admin_child:# or current_user_group in user_all_groups:
        #                 group_memo.clear()
        #                 target_group_memo.clear()
        #                 # group_memo['prev'] = None
        #                 return True
        #             else:
        #                 group_memo.get('prev', []).append(ru)
        #                 return cls.is_admin_of_group(user, ru.name)
        target_group_memo.clear()
        group_memo.clear()
        return False

    @classmethod
    def get_name(cls, g_name):
        g = Group.objects.filter(name=g_name).first()
        if n := cls.objects.filter(group_rel=g).first():
            return n.group_name
        else:
            return None
