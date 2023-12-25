import asyncio
from . import task
from ajax_datatable import AjaxDatatableView
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView
from core.views import BaseView
from .forms import MessageForm, ReceiverForm, ReceiverTelegramBotForm
from .scripts.telethon_ import Session as Se,Bot
Se.folder = f"tlg/scripts/Files/Sessions"
Bot.folder = f"tlg/scripts/Files/Sessions"
from .models import Session, Message, Receiver, ReceiverTelegramBotSession, SMS, Bot as BotModel, Email
from translator import get_text as _


def send_code(request):
    if request.method == "POST":
        phone = request.POST.get("phone_number")
        id_type = request.POST.get("type")
        session = Se.get_session(phone)
        res = session.async_event_loop(session.send_code())
        print(res)
        if res:
            obj = Session.objects.get_or_create(phone_number=phone)[0]
            obj.phone_number = phone
            obj.type = id_type
            obj.save()
        return JsonResponse({"detail": res})


def verify_code(request):
    if request.method == "POST":
        phone = request.POST.get("phone_number")
        id_type = request.POST.get("type")
        telegram_verify_code = request.POST.get("telegram_verify_code")
        telegram_password = request.POST.get("telegram_password")
        session = Se.get_session(phone)
        res = session.async_event_loop(session.verify_code(telegram_verify_code,telegram_password))
        print(res)
        if res:
            obj = Session.objects.get_or_create(phone_number=phone)[0]
            obj.phone_number = phone
            obj.type = id_type
            obj.telegram_password = telegram_password
            obj.telegram_id = session.me.id
            obj.save()
        return JsonResponse({"detail": res})


class MessageView(BaseView):
    form_class = MessageForm
    # main_form = ReceiptCreateForm2
    model = Message
    # formset = inlineformset_factory(Receipt, ReceiptDetail, form=ReceiptDetailCreateForm2, extra=1, )
    # formset_model = ReceiptDetail
    # formset_form = ReceiptDetailCreateForm2
    template_name = 'tlg/message_view.html'
    # formset_fk_field = 'receipt_id'
    # related_name_fk = 'receiptdetail_set'
    success_url = reverse_lazy('tlg:message.list')
    # has_flow = True
    # has_simple_flow = True
    # wf_to_user_permission = 'tlg.change_receipt'
    # allow_perms = ['inventory.add_receipt', 'inventory.add_receiptdetail']
    # permission_strategy = 'and'
    # create = True
    
    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs)


class MessageList(ListView):
    template_name = 'tlg/message_list.html'
    model = Message


class MessageListDatatableView(AjaxDatatableView):
    model = Message
    title = 'tlg_messaage_list'
    # initial_order = [["last_update_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'abstract_text', 'visible': True, 'title': _('abstract_text'), 'className': 'py-1 border'},
        {'name': 'text', 'visible': True, 'title': _('text'), 'className': 'py-1 border'},
        {'name': 'reply_to', 'visible': True, 'title': _('reply to'), 'className': 'py-1 border'},
        {'name': 'sender_type', 'visible': True, 'title': _('sender type'), 'className': 'py-1 border'},
        {'name': 'sender', 'visible': True, 'title': _('sender'), 'className': 'py-1 border'},
        {'name': 'automation_status', 'visible': True, 'title': _('automation status'), 'className': 'py-1 border'},
        {'name': 'id', 'visible': False, },
    ]

    def get_initial_queryset(self, request=None):
        return self.model.objects.all()
        # param = self.request.POST.get('q', 'all').strip('/')
        # if param == 'all':
        #     qs = self.model.objects.all()

    def customize_row(self, row, obj):
        row['abstract_text'] = '<a class="fw-bold" href="%s">%s</a>' % (
                      reverse('tlg:message.create_update', args=(obj.id,)),
                      obj.abstract_text if obj.abstract_text else '_'
                    )


class ReceiverListView(ListView):
    template_name = 'tlg/receiver_list.html'
    model = Receiver
    form_class = ReceiverForm
    # success_url = '.'


class ReceiverListDatatableView(AjaxDatatableView):
    model = Receiver
    title = 'tlg_receiver_list'
    initial_order = [["name", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'name', 'visible': True, 'title': _('name'), 'className': 'py-1 border'},
        {'name': 'customer_code', 'visible': True, 'title': _('customer_code'), 'className': 'py-1 border'},
        {'name': 'phone_number', 'visible': True, 'title': _('phone number'), 'className': 'py-1 border'},
        {'name': 'sepidar_phones', 'visible': True, 'title': _('sepidar phones'), 'className': 'py-1 border'},
        {'name': 'telegram_username', 'visible': True, 'title': _('telegram username'), 'className': 'py-1 border'},
        {'name': 'email', 'visible': True, 'title': _('email'), 'className': 'py-1 border'},
        {'name': 'bot_is_active', 'visible': True, 'title': _('bot is active'), 'className': 'py-1 border'},
        {'name': 'session_is_active', 'visible': True, 'title': _('session is active'), 'className': 'py-1 border'},
        {'name': 'messaging_is_active', 'visible': True, 'title': _('messaging is active'), 'className': 'py-1 border'},
        {'name': 'email_is_active', 'visible': True, 'title': _('email is active'), 'className': 'py-1 border'},
        {'name': 'id', 'visible': False, },
    ]

    def get_initial_queryset(self, request=None):
        param = self.request.POST.get('q', 'all').strip('/')
        if param == 'all' or param == '':
            qs = self.model.objects.all()
        # elif param == 'phone':
        #     qs = self.model.objects.filter_with_phone()
        elif param == 'no_phone':
            qs = self.model.objects.filter_no_phone()
        elif param == 'new':
            qs = self.model.objects.filter_new()
        else:
            qs = self.model.objects.none()
        return qs

    def customize_row(self, row, obj):
        row['name'] = '<a class="fw-bold" href="%s">%s</a>' % (
                      reverse('tlg:receiver.create_update', args=(obj.id,)),
                      obj.name if obj.name else '_'
                    )


class ReceiverCreateOrUpdateView(BaseView):
    template_name = 'tlg/receiver_create_or_update.html'
    model = Receiver
    form_class = ReceiverForm
    success_url = reverse_lazy('tlg:receiver.list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


def get_sender(request):
    q = request.GET.get('q')
    res = dict()
    if q == '1':  # bot
        res.update({'label': _('select bot')})
        for item in BotModel.objects.all():
            res.update({item.pk: item.username})
    elif q == '2':  # user
        res.update({'label': _('select user')})
        ...
    elif q == '3':  # messaging
        res.update({'label': _('select messaging')})
        SMS.objects.all()
    elif q == '4':  # email
        res.update({'label': _('select email')})
        Email.objects.all()
    return JsonResponse(res)