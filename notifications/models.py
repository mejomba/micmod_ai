import asyncio
import json
from collections import defaultdict

from django.conf import settings
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib import messages as django_message
from django.db import models

from django.apps import apps
from core.models_contenttype import AbsBaseModel, Q, BaseContentType
from accounts.models import User
from translator import get_text as _
from django.template.loader import render_to_string
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
import re

phone_patern = r'^09[0-9]{9}$'


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


class Notification(AbsBaseModel):
    action_choice = (("system", "system"), ("force", "force"))
    CHANNEL_TYPE_CHOICES = (("SMS", "SMS"), ("EMAIL", "EMAIL"))
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING, related_name='notifications',
                                     null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    fake_object_id = models.CharField(max_length=255, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    object_state = models.CharField(max_length=255, verbose_name='عنوان منحصر به فرد هر نوع ارسال پیام')
    action_type = models.CharField(max_length=64, choices=action_choice, null=True, blank=True, verbose_name=('نوع ارسال مثلا سیستمی یا کاربر فورس کرده'))
    chanel_type = models.CharField(max_length=255, choices=CHANNEL_TYPE_CHOICES, null=True, blank=True, verbose_name=_('روش ارسال مثلا پیامک'))
    chanel_id = models.CharField(max_length=255, null=True, blank=True, verbose_name='گیرنده: مثلا شماره تلفن یا ایمیل')
    date = models.DateField(_('date'))
    text = models.TextField(_('text'))

    # =============== quotation notify
    @classmethod
    def notify_customer_for_quotation(cls, quotation, request):
        # if quotation.pk < 13500:
        #     return

        ctt = ContentType.objects.get_for_model(quotation.__class__)

        has_first_notify = cls.objects.filter(object_id=quotation.pk, content_type=ctt, object_state='ثبت پیش فاکتور').exists()
        has_sepidar_notify = cls.objects.filter(object_id=quotation.pk, content_type=ctt, object_state='ثبت پیش فاکتور در سپیدار').exists()
        has_yadavar = cls.objects.filter(object_id=quotation.pk, content_type=ctt, object_state='یاد آور خرید پیش فاکتور').exists()

        last_work_flow = quotation.last_work_flow

        if last_work_flow and quotation.can_observe:
            if not has_first_notify and last_work_flow.current_state_name == 'پیش فاکتور اولیه':
                cls._quotation_first_notify(quotation, ctt, request)

            elif not has_sepidar_notify and quotation.sepidar_number:
                cls._quotation_sepidar_notify(quotation, ctt, request)

            elif last_work_flow and last_work_flow.current_state_name == 'تایید مشتری' and last_work_flow.created_date < (timezone.now() - timezone.timedelta(hours=72)) and not has_yadavar:
                cls._quotation_yadavar_notify(quotation, ctt, request)

    @classmethod
    def _quotation_first_notify(cls, quotation, ctt, request):
        from tlg.scripts.sms import send_sms

        notify_number = quotation.notify_number
        try:
            if not re.match(phone_patern, notify_number):
                return
        except Exception as e:
            return
        message = 'درخواست شما جهت بررسی ثبت شد. نتیجه بررسی حداکثر ظرف ۴۸ تا ۷۲ ساعت کاری توسط کارشناس مربوطه به اطلاع شما خواهد رسید.'
        success, res = send_sms('', [notify_number], message)
        if success:
            data = {
                "content_type": ctt,
                "object_id": quotation.pk,
                "object_state": 'ثبت پیش فاکتور',
                "action_type": 'system',
                "chanel_type": 'sms',
                "chanel_id": quotation.notify_number,
                "date": timezone.now(),
                "text": message,
            }
            obj = cls.objects.create(**data)
            m = f"پیامک ثبت پیش فاکتور ارسال شد. \n {message}"
            django_message.success(request, m)

    @classmethod
    def _quotation_sepidar_notify(cls, quotation, ctt, request):
        from tlg.scripts.sms import send_sms

        notify_number = quotation.notify_number
        try:
            if not re.match(phone_patern, notify_number):
                return
        except Exception as e:
            return
        message = 'پیش فاکتور شما صادر گردید. اعتبار قیمت های اعلام شده حداکثر ۴۸ ساعت می باشد. جهت مشاهده جزیات به لینک پیش فاکتور در shop مراجعه فرمایید.'
        success, res = send_sms('', [notify_number], message)
        if success:
            data = {
                "content_type": ctt,
                "object_id": quotation.pk,
                "object_state": 'ثبت پیش فاکتور در سپیدار',
                "action_type": 'system',
                "chanel_type": 'sms',
                "chanel_id": quotation.notify_number,
                "date": timezone.now(),
                "text": message,
            }
            obj = cls.objects.create(**data)
            m = f"پیامک ثبت پیش فاکتور در سپیدار ارسال شد. \n {message}"
            django_message.success(request, m)

    @classmethod
    def _quotation_yadavar_notify(cls, quotation, ctt, request):
        from tlg.scripts.sms import send_sms

        notify_number = quotation.notify_number
        try:
            if not re.match(phone_patern, notify_number):
                return
        except Exception as e:
            return
        message = 'یادآوری: پیش فاکتور صادر شده همچنان در انتظار تایید و اقدام شما می باشد. لطفا در اسرع وقت نسبت به بررسی و ثبت سفارش اقدام فرمایید.'
        success, res = send_sms('', [notify_number], message)

        if success:
            data = {
                "content_type": ctt,
                "object_id": quotation.pk,
                "object_state": 'یاد آور خرید پیش فاکتور',
                "action_type": 'system',
                "chanel_type": 'sms',
                "chanel_id": quotation.notify_number,
                "date": timezone.now(),
                "text": message,
            }
            obj = cls.objects.create(**data)
    # =============== quotation notify

    # =============== factor notify
    @classmethod
    def notify_customer_for_factor(cls, factor, request):
        # if factor.pk < 1920:
        #     return

        ctt = ContentType.objects.get_for_model(factor.__class__)

        last_work_flow = factor.last_work_flow
        has_sales_admin_confirm = cls.objects.filter(object_id=factor.pk, content_type=ctt, object_state='تایید مدیر فروش فاکتور').exists()
        has_sent_notify = cls.objects.filter(object_id=factor.pk, content_type=ctt, object_state='تسویه حساب فاکتور').exists()

        if last_work_flow:
            if last_work_flow.current_state_name == 'تخصیص کارشناس انبار' and not has_sales_admin_confirm:
                cls._factor_sales_admin_confirm_notify(factor, ctt, request)

            elif factor.sepidar_number and not has_sent_notify:
                cls._factor_sent_notify(factor, ctt, request)

    @classmethod
    def _factor_sales_admin_confirm_notify(cls, factor, ctt, request):
        from tlg.scripts.sms import send_sms

        notify_number = factor.notify_number
        try:
            if not re.match(phone_patern, notify_number):
                return
        except Exception as e:
            return
        from factor.models import FactorItemSupplyLocation
        from django.db.models import Exists, OuterRef

        price = factor.get_price - factor.sum_discount + factor.sum_tax

        trade_order_count = factor.factoritem_set.annotate(
            has_order_supply=Exists(
                FactorItemSupplyLocation.objects.filter(
                    fi=OuterRef('pk'),
                    order__isnull=False
                )
            )
        ).filter(has_order_supply=True).count()

        if trade_order_count:
            message = "سند درخواست شما به شماره {0} به مبلغ {1} و شامل {2} ردیف کالا صادر گردید. همچنین برای {3} ردیف کالا سفارش خارجی ثبت شده و مطابق برنامه زمانبندی تحویل خواهد شد. جهت مشاهده جزئیات فاکتور به پنل خود مراجعه فرمایید.".format(factor.pk, f'{price:0.2f}'.rstrip('0').rstrip('.'), factor.factoritem_set.count(), trade_order_count)
        else:
            message = "سند درخواست شما به شماره {0} به مبلغ {1} و شامل {2} ردیف کالا صادر گردید. جهت مشاهده جزئیات فاکتور به پنل خود مراجعه فرمایید.".format(factor.pk, f'{price:0.2f}'.rstrip('0').rstrip('.'), factor.factoritem_set.count())

        success, res = send_sms('', [notify_number], message)
        if success:
            data = {
                "content_type": ctt,
                "object_id": factor.pk,
                "object_state": 'تایید مدیر فروش فاکتور',
                "action_type": 'system',
                "chanel_type": 'sms',
                "chanel_id": factor.notify_number,
                "date": timezone.now(),
                "text": message,
            }
            obj = cls.objects.create(**data)
            m = f"پیامک تایید فاکتور ارسال شد. \n {message}"
            django_message.success(request, m)

    @classmethod
    def _factor_sent_notify(cls, factor, ctt, request):
        from tlg.scripts.sms import send_sms

        notify_number = factor.notify_number
        try:
            if not re.match(phone_patern, notify_number):
                return
        except Exception as e:
            return
        deliver_method = _(getattr(factor.deliver_method, 'title', None) or '-')

        message = "فاکتور شماره {0} با شماره حواله {1} از طریق {2} ارسال گردید.".format(factor.pk, factor.sepidar_inventory_delivery_number, deliver_method)
        success, res = send_sms('', [notify_number], message)
        if success:
            data = {
                "content_type": ctt,
                "object_id": factor.pk,
                "object_state": 'تسویه حساب فاکتور',
                "action_type": 'system',
                "chanel_type": 'sms',
                "chanel_id": factor.notify_number,
                "date": timezone.now(),
                "text": message,
            }
            obj = cls.objects.create(**data)
            m = f"پیامک تسویه حساب فاکتور ارسال شد. \n {message}"
            django_message.success(request, m)
    # =============== factor notify

    # =============== google sheet order notify

    @classmethod
    def notify_customer_for_google_sheet_order(cls, *, data):
        from tlg.scripts.sms import send_sms
        Customer = apps.get_model('extra_data', 'Customer')

        phone_pattern = r'^09[0-9]{9}$'
        ctt_id = 104

        last_step_map = {
            "supp": "ثبت سفارش",
            "departure": "شروع حمل سفارش",
            "declaration": "ترخیص سفارش"
        }
        message_map = {
            "supp": 'برای پیش‌فاکتور های شما {0} ردیف سفارش ثبت شده است\n زمان تقریبی حمل: {1}',
            "departure": 'برای پیش‌فاکتور های شما {0} ردیف سفارش در حال حمل است. زمان تقریبی حمل: {1}',
            "declaration": 'برای پیش‌فاکتور های شما {0} ردیف سفارش در حال رسیدن است\n زمان تقریبی رسیدن: {1}',
        }

        already_sent_set = set(
            cls.objects.filter(content_type_id=ctt_id)
            .values_list('fake_object_id', 'object_state')
        )

        result = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'dates': []}))

        for item in data:
            customer_code = item['dim_order[customer_code]']
            last_step = item['[last_step]']
            status_str = item['dim_order[status_str]']
            date = item['dim_order[last_end_date_shamsi]']
            current_step = last_step_map.get(last_step)

            if status_str == 'کامل' or not current_step:
                continue
            if (customer_code, current_step) in already_sent_set:
                continue

            result[customer_code][last_step]['count'] += 1
            result[customer_code][last_step]['dates'].append(date)

        for customer_code, steps in result.items():
            notify_number = Customer.get_customer_notify_number(customer_code)
            if not notify_number or not re.match(phone_pattern, notify_number):
                continue

            for last_step, info in steps.items():
                if info['count'] == 0:
                    continue

                current_step = last_step_map[last_step]
                dates_sorted = sorted(info['dates'])

                if len(dates_sorted) == 1:
                    date_str = dates_sorted[0]
                else:
                    date_str = f"{dates_sorted[0]} الی {dates_sorted[-1]}"

                message = message_map[last_step].format(info['count'], date_str)

                success, res = send_sms('', [notify_number], message)
                if success:
                    cls.objects.create(
                        content_type_id=ctt_id,
                        fake_object_id=customer_code,
                        object_state=current_step,
                        action_type='system',
                        chanel_type='sms',
                        chanel_id=notify_number,
                        date=timezone.now(),
                        text=message,
                    )

    # @classmethod
    # def _google_sheet_order_supp_confirm_notify(cls, notify_number, order_id, state_order_count, date):
    #     from tlg.scripts.sms import send_sms
    #
    #     ctt_id = 104
    #
    #     message = 'برای پیش‌فاکتور های شما {0} ردیف سفارش ثبت شده است\n زمان تقریبی حمل: {1}'.format(state_order_count, date)
    #     success, res = send_sms('', [notify_number], message)
    #     if success:
    #         data = {
    #             "content_type_id": ctt_id,
    #             "object_id": order_id,
    #             "object_state": 'ثبت سفارش',
    #             "action_type": 'system',
    #             "chanel_type": 'sms',
    #             "chanel_id": notify_number,
    #             "date": timezone.now(),
    #             "text": message,
    #         }
    #         obj = cls.objects.create(**data)
    # # =============== google sheet order notify
    #
    # @classmethod
    # def _google_sheet_order_departure_notify(cls, notify_number, order_id, state_order_count, date):
    #     from tlg.scripts.sms import send_sms
    #     ctt_id = 104
    #
    #     message = 'برای پیش‌فاکتور های شما {0} ردیف سفارش در حال حمل است. زمان تقریبی حمل{1}'.format(state_order_count, date)
    #     success, res = send_sms('', [notify_number], message)
    #     if success:
    #         data = {
    #             "content_type_id": ctt_id,
    #             "object_id": order_id,
    #             "object_state": 'شروع حمل سفارش',
    #             "action_type": 'system',
    #             "chanel_type": 'sms',
    #             "chanel_id": notify_number,
    #             "date": timezone.now(),
    #             "text": message,
    #         }
    #         obj = cls.objects.create(**data)
    # # =============== google sheet order notify
    #
    # @classmethod
    # def _google_sheet_order_declaration_notify(cls, notify_number, order_id, state_order_count, date):
    #     from tlg.scripts.sms import send_sms
    #     ctt_id = 104
    #
    #     message = 'برای پیش‌فاکتور های شما {0} ردیف سفارش در حال رسیدن است\n زمان تقریبی رسیدن: {1}'.format(state_order_count, date)
    #     success, res = send_sms('', [notify_number], message)
    #     if success:
    #         data = {
    #             "content_type_id": ctt_id,
    #             "object_id": order_id,
    #             "object_state": 'ترخیص سفارش',
    #             "action_type": 'system',
    #             "chanel_type": 'sms',
    #             "chanel_id": notify_number,
    #             "date": timezone.now(),
    #             "text": message,
    #         }
    #         obj = cls.objects.create(**data)
    # =============== google sheet order notify
