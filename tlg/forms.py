from django import forms

from core.forms import CustomBaseModelForm
from files.models import Image
from .models import Session, Bot, SMS, Email, Receiver, Message, MessageDetail, ReceiverTelegramBotSession
from translator import get_text as _


class TelegramVerifyFrm(forms.ModelForm):
    telegram_verify_code = forms.CharField(max_length=6, required=False)

    class Meta:
        model = Session
        fields = '__all__'


class MessageForm(CustomBaseModelForm):
    image_groups = 1
    image_model = Image

    class Meta:
        model = Message
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.make_optional(['image_1'])

            self.fields['text'].widget.attrs['rows'] = 1
            # self.fields['sender_1'].widget.attrs['class'] = 'form-control sender d-none '
            # self.fields['sender_1'].widget.attrs['name'] = 'sender_1'
            # self.fields['sender_1'].label = _('select bot')
            #
            # self.fields['sender_2'].widget.attrs['class'] = 'form-control sender d-none '
            # self.fields['sender_2'].widget.attrs['name'] = 'sender_2'
            # self.fields['sender_2'].label = _('select user')
            #
            # self.fields['sender_3'].widget.attrs['class'] = 'form-control sender d-none '
            # self.fields['sender_3'].widget.attrs['name'] = 'sender_3'
            # self.fields['sender_3'].label = _('select messaging')
            #
            # self.fields['sender_4'].widget.attrs['class'] = 'form-control sender d-none '
            # self.fields['sender_4'].widget.attrs['name'] = 'sender_4'
            # self.fields['sender_4'].label = _('select email')
        except Exception as e:
            print('error: ', __file__,  e.__traceback__.tb_lineno, e)

    @staticmethod
    def get_sender_list():
        from itertools import chain



        qry1 = Session.objects.all()
        # print(qry1)
        qry2 = Bot.objects.all()
        qry3 = SMS.objects.all()
        qry4 = Email.objects.all()
        # qry = qry1 | qry2 | qry3 | qry4
        # print(qry1.union(qry2, qry3, qry4))
        # print(qry)
        return qry1


class ReceiverForm(CustomBaseModelForm):
    class Meta:
        model = Receiver
        fields = '__all__'

    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.fields['sepidar_phones'].widget.attrs['rows'] = 1
            self.fields['sepidar_email'].widget.attrs['rows'] = 1
        except Exception as e:
            print(str(e))


class ReceiverTelegramBotForm(CustomBaseModelForm):
    class Meta:
        model = ReceiverTelegramBotSession
        fields = '__all__'
