import asyncio
from datetime import datetime
from datetime import timedelta
import os

from asgiref.sync import sync_to_async, async_to_sync
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils import timezone

from translator import get_text as _
from core.models import AbsBaseModel
from .scripts.telethon_ import Session as Se,Bot as Bot_
Se.folder = f"tlg/scripts/Files/Sessions"
Bot_.folder = f"tlg/scripts/Files/Sessions"

# Create your models here.


class Type(models.TextChoices):
    Tel = "1", _("Telethon")
    Sel = "2", _("Selenium")


class SenderType(models.TextChoices):
    Alg = "0", _("select_depend_receiver")
    Bot = "1", _("sent_by_bot")
    Usr = "2", _("sent_by_user")
    Msg = "3", _("sent_by_messaging")
    Eml = "4", _("sent_by_email")


class AutomaticStatus(models.TextChoices):
    automat = "1", _("automat")
    manual = "2", _("manual")


class SeenStatus(models.TextChoices):
    NotSent = "1", _("not_sent")
    Sent = "2", _("sent")
    Received = "3", _("received")
    Seen = "4", _("seen")


class SenderSubSystem(models.TextChoices):
    Quotation = "1", _("quotation")
    Order = "2", _("order")
    invoice = "3", _("invoice")


class Session(AbsBaseModel):
    telegram_id = models.BigIntegerField(null=True, blank=True, verbose_name=_('telegram_id'))
    phone_number = models.CharField(max_length=15, verbose_name=_('phone_number'))
    type = models.CharField(max_length=2, choices=Type.choices, default=Type.Tel, verbose_name=_('type'))
    session_string = models.CharField(null=True, blank=True, max_length=1000, verbose_name=_('session_string'))
    flood_status = models.DateField(blank=True, null=True, verbose_name=_('flood_status'))
    telegram_password = models.CharField(null=True, blank=True, max_length=50, verbose_name=_('telegram_password'))
    phone_owner = models.CharField(blank=True, null=True, max_length=50, verbose_name=_('phone_owner'))


class Bot(AbsBaseModel):
    telegram_id = models.BigIntegerField(null=True, blank=True, verbose_name=_('telegram_id'))
    username = models.CharField(max_length=50, verbose_name=_('username'))
    name = models.CharField(max_length=50,null=True,blank=True, verbose_name=_('name'),unique=True)
    type = models.CharField(max_length=2, choices=Type.choices, default=Type.Tel, verbose_name=_('type'))
    token = models.CharField(null=True, blank=True, max_length=100, verbose_name=_('token'))
    is_active = models.BooleanField(default=False, verbose_name=_('is_active'))


class SMS(AbsBaseModel):
    service_company = models.CharField(null=True, blank=True, max_length=50, verbose_name=_('service_company'))
    phone_number = models.CharField(max_length=20, verbose_name=_('phone_number'), unique=True)
    username = models.CharField(max_length=50, verbose_name=_('username'))
    password = models.CharField(max_length=50, verbose_name=_('password'))


class Email(AbsBaseModel):
    server = models.CharField(null=True, blank=True, max_length=50, verbose_name=_('service_company'))
    username = models.CharField(max_length=50, verbose_name=_('username'))
    password = models.CharField(max_length=50, verbose_name=_('password'))


class ReceiverModelManager(models.Manager):
    def get_query_set(self):
        return self.filter(is_deleted=False)

    def filter_no_phone(self):
        return self.get_query_set().filter(phone_number__isnull=True)

    def filter_with_phone(self):
        return self.get_query_set().filter(phone_number__isnull=False)

    def filter_new(self):
        yesterday = datetime.today() - timedelta(hours=24)
        return self.get_query_set().filter(created_date__gte=yesterday)


class Receiver(AbsBaseModel):
    name = models.CharField(null=True, blank=True, max_length=100, verbose_name=_('name'))
    customer_code = models.CharField(null=True, blank=True, max_length=20, verbose_name=_('customer_code'),unique=True)
    phone_number = models.CharField(null=True, blank=True, max_length=20, verbose_name=_('phone number'), unique=True)
    sepidar_phones = models.TextField(null=True,blank=True,max_length=1000,verbose_name=_('sepidar phones'))

    telegram_username = models.CharField(null=True, blank=True, max_length=100, verbose_name=_('telegram username'))

    email = models.EmailField(null=True, blank=True, verbose_name=_('email'))
    sepidar_email = models.TextField(max_length=1000, null=True, blank=True, verbose_name=_('sepidar_email'))

    bot_is_active = models.BooleanField(default=True, verbose_name=_('bot_is_active'))
    session_is_active = models.BooleanField(default=True, verbose_name=_('session_is_active'))
    messaging_is_active = models.BooleanField(default=True, verbose_name=_('messaging_is_active'))
    email_is_active = models.BooleanField(default=True, verbose_name=_('email_is_active'))

    objects = ReceiverModelManager()


class ReceiverTelegramBotSession(AbsBaseModel):
    active_sender_session_tlg = models.ForeignKey(Session, on_delete=models.DO_NOTHING, related_name='session_const',
                                                  null=True, blank=True, verbose_name=_('active_sender_session_tlg'))
    receiver = models.ForeignKey(Receiver, on_delete=models.CASCADE, verbose_name=_('receiver'),
                                 related_name='receiver_const', blank=True, null=True)
    telegram_phone = models.CharField(null=True, blank=True, max_length=20, verbose_name=_('telegram_phone'))
    telegram_username = models.CharField(null=True, blank=True, max_length=100, verbose_name=_('telegram_username'))
    telegram_name = models.CharField(null=True, blank=True, max_length=100, verbose_name=_('telegram_name'))
    telegram_id = models.BigIntegerField(null=True, blank=True, verbose_name=_('telegram_id'), unique=True)
    access_hash = models.BigIntegerField(null=True, blank=True, verbose_name=_('access_hash'))
    is_admin = models.BooleanField(verbose_name=_('is_admin'), default=False)

    @staticmethod
    async def get_receiver_by_phone(session, phone, user_id=None):
        if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
            obj = ReceiverTelegramBotSession.objects.filter(telegram_phone=phone).first()
        else:
            obj = await ReceiverTelegramBotSession.objects.filter(telegram_phone=phone).afirst()
        if not obj:
            if user_id:
                try:
                    user_id = int(user_id)
                except:
                    ...
            receiver_ses = await session.get_user_by_phone(phone, user_id)
            receiver_data = {
                'active_sender_session_tlg': session.session_data,
                'telegram_phone': phone,
                'telegram_username': receiver_ses.username,
                'telegram_name': f'{receiver_ses.first_name if receiver_ses.first_name else ""}{" - " + receiver_ses.last_name if receiver_ses.last_name else ""}',
                'telegram_id': receiver_ses.id,
                'access_hash': receiver_ses.access_hash
            }
            if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
                obj, _ = ReceiverTelegramBotSession.objects.get_or_create(telegram_id=receiver_ses.id, defaults=receiver_data)
            else:
                obj, _ = await ReceiverTelegramBotSession.objects.aget_or_create(telegram_id=receiver_ses.id, defaults=receiver_data)
        return obj


class Message(AbsBaseModel):
    title = models.CharField(max_length=255, null=True, blank=True)
    abstract_text = models.CharField(null=True, blank=True, max_length=50, verbose_name=_('abstract_text'))
    text = models.TextField(max_length=1000, verbose_name=_('text'))
    reply_to = models.BigIntegerField(null=True, blank=True, verbose_name=_('repy_to'))

    sender_type = models.CharField(max_length=2, choices=SenderType.choices, default=SenderType.Alg,
                                   verbose_name=_("sender_type"))
    sender = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("sender"))
    automation_status = models.CharField(max_length=2, choices=AutomaticStatus.choices, default=AutomaticStatus.manual,
                                   verbose_name=_("automation_status"))
    sender_sub_system = models.CharField(max_length=2, choices=SenderSubSystem.choices, null=True, blank=True,
                                   verbose_name=_("base_obj_type"))
    sender_sub_system_id = models.CharField(max_length=20, verbose_name=_('sender_sub_system_id'), blank=True, null=True)



class MessageDetail(AbsBaseModel):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, verbose_name=_('message'),
                                related_name='message_const')
    receiver_id = models.BigIntegerField(verbose_name=_('receiver_id'))

    sender_type = models.CharField(max_length=2, choices=SenderType.choices, default=SenderType.Alg,
                                   verbose_name=_("sender_type"))
    sender = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("sender"))

    sent_date = models.DateTimeField(blank=True, null=True, verbose_name=_('sent_date'))

    _message_id = models.BigIntegerField(blank=True, null=True, verbose_name=_('message_id'))
    send_err = models.CharField(max_length=200, blank=True, null=True, verbose_name=_('send_err'))
    seen_status = models.CharField(max_length=2, choices=SeenStatus.choices, default=SeenStatus.NotSent,
                                   verbose_name=_('seen_status'))

    @staticmethod
    async def send_message(sender_type, sender, receiver, text, images=None,buttons=None):
        sent_message = None
        status = None
        if sender_type == SenderType.Alg or sender_type == SenderType.Bot:
            status, sent_message = await sender.send_message(receiver.telegram_id,text,images,buttons)
            sender = sender.bot_data.pk
        elif sender_type == SenderType.Usr:
            status, sent_message = await sender.send_message(receiver.telegram_id, text, images, buttons)
            sender = sender.session_data.pk

        message_data = {
            'text': text,
            'sender_type': sender_type,
            'sender': sender,
            'automation_status': AutomaticStatus.automat
            }
        if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
            message = Message.objects.create(**message_data)
        else:
            message = await Message.objects.acreate(**message_data)
        message_dtail_data = {
            'message':  message,
            'receiver_id': receiver.pk,
            'sender_type': sender_type,
            'sender': sender,
            'sent_date': timezone.now(),
            '_message_id': sent_message.id if status else None,
            'send_err': sent_message if not status else None,
            'seen_status': SeenStatus.Sent if status else SeenStatus.NotSent,
        }
        if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
            MessageDetail.objects.create(**message_dtail_data)
        else:
            await MessageDetail.objects.acreate(**message_dtail_data)


class ObjectRelated(AbsBaseModel):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, verbose_name=_('message'),
                                related_name='message_related')
    object_type = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('object_type'))
    object_code = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('object_code'))
    object_status = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('status'))

class ReceivedMessage(AbsBaseModel):
    # received_date = models.DateTimeField(verbose_name=_('received_date'))
    text = models.CharField(max_length=1000, verbose_name=_('text'))
    sender_type = models.CharField(max_length=2, choices=SenderType.choices, default=SenderType.Alg,
                                   verbose_name=_("sender_type"))
    receiver_id = models.BigIntegerField(verbose_name=_('receiver_id'), null=True,blank=True)
    sender_id = models.BigIntegerField(verbose_name=_('sender_id'),null=True,blank=True)
    message_id = models.BigIntegerField(verbose_name=_('message_id'), blank=True, null=True)

    @staticmethod
    async def receive_new_message(event,receiver_id=None, sender_type=SenderType.Bot):
        if sender_type == SenderType.Bot:
            receiver_data = {
                    'telegram_phone': event.chat.phone,
                    'telegram_username':event.chat.username,
                    'telegram_name': f'{event.chat.first_name if event.chat.first_name else ""}{" - " +event.chat.last_name if event.chat.last_name else ""}',
                    'telegram_id': event.chat.id,
                    'access_hash': event.chat.access_hash
            }
            if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
                obj,_ = ReceiverTelegramBotSession.objects.get_or_create(telegram_id=event.chat.id, defaults=receiver_data)
            else:
                obj,_ = await ReceiverTelegramBotSession.objects.aget_or_create(telegram_id=event.chat.id, defaults=receiver_data)

            message_data = {
                'text': event.message_text,
                'sender_type': SenderType.Bot,
                'receiver_id': receiver_id,
                'sender_id': obj.pk,
                'message_id': event.message_id,
            }
            if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
                ReceivedMessage.objects.create(**message_data)
            else:
                await ReceivedMessage.objects.acreate(**message_data)
            return obj

