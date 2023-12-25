from django.db import models
from django.contrib.auth.models import AbstractUser, Group
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from translator import get_text as _


# class Role(models.Model):
#     IMEI_ADMIN = 1
#     IMEI_USER = 2
#
#     ROLE_CHOICES = (
#         (IMEI_ADMIN, _('imei admin')),
#         (IMEI_USER, _('imei user')),
#     )
#
#     role = models.PositiveSmallIntegerField(choices=ROLE_CHOICES)
#
#     def __str__(self):
#         return self.get_role_display()


class User(AbstractUser):
    sepidar_code = models.IntegerField(null=True, blank=True, verbose_name=_('sepidar code'))
    telegram_code = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('telegram_code'), unique=True)
    customer_code = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('customer_code'))
    phone = models.CharField(max_length=11, null=True, blank=True, verbose_name=_('phone'))
    is_customer = models.BooleanField(default=False, verbose_name=_('is_customer'))

    class Meta:
        db_table = 'auth_user'

    def get_target_user_from_group(self, group, level=1):
        from workflow.models import FlowAdminGroup
        from django.contrib.auth import get_user_model
        print('group: ', group)
        qs = get_user_model().objects.filter(pk=-1)
        if level > 1:
            qs |= group.user_set.all()
            print(qs)
        for g in FlowAdminGroup.objects.filter(group_rel=group):
            for gc in g.group_child.all():
                qs |= self.get_target_user_from_group(gc, level + 1)
        print('qs before return ', qs)
        return qs

    def get_target_users(self):
        from django.contrib.auth import get_user_model
        user_qs = get_user_model().objects.filter(id=self.id)
        for main_user_group in self.groups.all():
            user_qs |= self.get_target_user_from_group(main_user_group)
        print('user_list  > ', user_qs)
        return user_qs

    def get_target_wf(self):
        from workflow.models import WorkFlow
        user_list = self.get_target_users()
        wf = WorkFlow.objects.filter(id=-1)
        for user in user_list:
            wf |= WorkFlow.objects.filter(
                Q(creator_user=user) |
                Q(editor_user=user) |
                Q(from_user=user) |
                Q(to_user=user)
            )
        return wf

# MyUser = User.get_user_model().objects.get()


class ManageFormField(models.Model):
    ACTION = ((1, _('create or update')), (2, _('hide')),)
    title = models.CharField(verbose_name=_('title'), max_length=100)
    content_type = models.ForeignKey(ContentType, verbose_name=_('related model'), on_delete=models.DO_NOTHING)
    action = models.PositiveIntegerField(verbose_name=_('action'), choices=ACTION)
    fields_name = models.CharField(verbose_name=_('fields name'), max_length=250)
    allowed_groups = models.ManyToManyField(verbose_name=_('allowed groups'), to=Group, related_name='allowed_groups_related')

    def __str__(self):
        return f'{self.title}'



