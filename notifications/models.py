import asyncio
import json

from django.conf import settings
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
from core.models_contenttype import AbsBaseModel, Q, BaseContentType
from accounts.models import User
from translator import get_text as _
from django.template.loader import render_to_string
from django.contrib.contenttypes.models import ContentType
# Create your models here.


class Groups(AbsBaseModel):
    group_id = models.CharField(max_length=30, verbose_name=_("group_name"))
    members = models.ManyToManyField(User,verbose_name=_("members"),related_name="ws_groups")

class ReadStatus(models.TextChoices):
    Unread = "0", _("unread")
    Read = "1", _("read")


class MessageType(models.TextChoices):
    Success = "0", "success"
    Info = "1", "info"
    Warning = "2", "warning"
    Error = "3", "error"


class Messages(BaseContentType):
    user = models.ForeignKey(User, related_name="assigned_messages",verbose_name=_("user"), on_delete=models.DO_NOTHING)
    ws_group = models.ForeignKey(Groups, related_name="assigned_messages",verbose_name=_("group"), on_delete=models.DO_NOTHING,null=True,blank=True)
    title = models.CharField(max_length=50, verbose_name=_("title"))
    body = models.CharField(max_length=150, verbose_name=_("body"),null=True,blank=True)
    icon_url = models.URLField(verbose_name=_("icon_url"),null=True,blank=True)
    link = models.URLField(verbose_name=_("link"),null=True,blank=True)
    read_status = models.URLField(verbose_name=_("read_status"), default=ReadStatus.Unread)
    message_type = models.URLField(verbose_name=_("message_type"), default=MessageType.Info)
    send_to_group = models.BooleanField(verbose_name=_('send_to_group'),default=False)

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING, related_name='notification_content_type',
                                     null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    @classmethod
    def send_unread_count(cls, user):
        unread_count = cls.get_unread_messages(user,ReadStatus.Unread).count()
        asyncio.run(cls._send_message(f"notify_group_{user.id}",
                                      {'type': "notification_count", 'count': unread_count,
                                            'title': 'System', 'body': f'You have {unread_count} messages',
                                            'message_type': 'success'})
                    )

    @classmethod
    def send_message(cls, **kwargs):
        obj = cls.objects.create(**kwargs)
        if obj:
            unread_count = cls.get_unread_messages(obj.user).count()
            rendered_html = render_to_string('notifications/partials/notification_message.html',
                                             context={'notification': obj})
            asyncio.run(cls._send_message(f"notify_group_{obj.user.id}",
                                          {'type': "notification_msg", 'count': unread_count,
                                           'title': obj.title,'body': rendered_html,
                                           'message_type': dict(MessageType.choices)[obj.message_type]}))
        return obj



    @staticmethod
    async def _send_message(group, dict_):
        channel_layer = get_channel_layer()
        notify_group_id = group
        await channel_layer.group_send(
            notify_group_id,
            {
                'type': 'send_push_notify',
                'message':  json.dumps(dict_)
            }
        )

    @staticmethod
    def get_unread_messages(user, status=None, order_by=['read_status','-created_date']):
        qs = Messages.objects.filter(user=user)
        user_ws_groups = user.ws_groups
        if user_ws_groups.count():
            qs = qs | Messages.objects.filter(ws_group__in=user_ws_groups,send_to_group=True)
        if status:
            qs = qs.filter(read_status=ReadStatus.Unread)
        return qs.order_by(*order_by)

    @classmethod
    @database_sync_to_async
    def start_connection(cls, user):
        # cls.send_message()
        cls.send_unread_count(user)

    @classmethod
    @database_sync_to_async
    def read_message(cls, message_id):
        obj = cls.objects.filter(id=message_id).first()
        if obj:
            obj.read_status = ReadStatus.Read
            obj.save()

    @classmethod
    def read_message_by_contenttype(cls, user_id, contenttype_id, object_id):
        objs = cls.objects.filter(user_id=user_id, contenttype_id=contenttype_id,object_id=object_id)
        for obj in objs:
            obj.read_status = ReadStatus.Read
            obj.save()


# begin clude
# models.py (یا notifications/models.py)


class SupplyNotification(models.Model):
    RESERVE_TAKEN    = 'reserve_taken'
    RESERVE_RETURNED = 'reserve_returned'
    KIND_CHOICES = [
        (RESERVE_TAKEN,    'برداشت از رزرو شما'),
        (RESERVE_RETURNED, 'بازگشت رزرو'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='supply_notifications',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        help_text='کسی که این رویداد را ایجاد کرد (در RESERVE_RETURNED می‌تواند None باشد)',
    )
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    factor_item = models.ForeignKey(
        'factor.FactorItem', on_delete=models.CASCADE, related_name='+',
        help_text='ردیف فاکتور منشأ (آن‌که از رزرو این کاربر برداشت/بازگردانده شد)',
    )
    qty = models.FloatField()
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'is_read', '-created_at'])]

    def __str__(self):
        return f"{self.user} — {self.get_kind_display()} — {self.qty}"

#  end clude