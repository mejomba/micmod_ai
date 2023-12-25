import asyncio

from django.contrib import admin
from .models import Session, Bot as BotModel, Email, Receiver, ReceiverTelegramBotSession, SMS, Message, MessageDetail, ReceivedMessage
from .forms import TelegramVerifyFrm
from .scripts.telethon_ import Session as Se, pri, Bot

Se.folder = f"tlg/scripts/Files/Sessions"


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (['id','phone_number','telegram_id','created_date'])
    form = TelegramVerifyFrm
    fieldsets = (
        ('Standard info', {
            'fields': ('phone_number','type',)
        }),
        ('Verification info', {
            'fields': ('telegram_verify_code', 'telegram_password' )
        }),
        ('Verification info', {
            'fields': ('telegram_id','session_string', 'flood_status')
        }),
    )
    change_form_template = "tlg\session_view.html"
    add_form_template = "tlg\session_view.html"

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        # pri.delay()
        extra_context = dict()
        obj = Session.objects.filter(id=object_id).first()
        if obj:
            session = Se.get_session(obj.phone_number)
            extra_context["connected"] = session.async_event_loop(session.check_connect())
            session.async_event_loop(session.send_message())
            bot = Bot.get_session("MicroModernBot_Base5", '6422722067:AAGzAG7MwC3YQyH8rg5-itoFZ5x06P-d6pY')
            bot.async_event_loop(bot.start())
            bot.async_event_loop(bot.send_message())
        return super(SessionAdmin, self).changeform_view(request,object_id,form_url, extra_context)


admin.site.register(BotModel)
admin.site.register([Email, Receiver, ReceiverTelegramBotSession, SMS, Message, MessageDetail, ReceivedMessage])