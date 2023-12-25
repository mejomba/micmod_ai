# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import asyncio
import datetime
import os
import random
import re
import time
import TelethonFakeTLS
from getpass import getpass
from celery import shared_task
from django.core.cache import cache

import tools.utils
from _keenthemes.settings import CACHES
from tools.utils import to_jalali_date


from telethon import TelegramClient, events, errors, Button
#import TelethonFakeTLS
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.events.common import EventBuilder
from telethon.tl.functions.channels import JoinChannelRequest, InviteToChannelRequest
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact, ReplyInlineMarkup, KeyboardButtonRow, KeyboardButtonCallback
from asgiref.sync import sync_to_async

from django.db.models import Q


@shared_task
def pri():
    print("test1")
    bot = Bot.get_session("MicroModernBot_Base2",'6422722067:AAGzAG7MwC3YQyH8rg5-itoFZ5x06P-d6pY')
    bot.async_event_loop(bot.start())
    bot.async_event_loop(bot.send_message())
    print("test2")

con_ = TelethonFakeTLS.ConnectionTcpMTProxyFakeTLS
proxy_ = proxy=('135.181.86.139',
                8085,
                'QAAAAAAAAAAAAAAAAAAAAA=')
# proxy_ = proxy=('88.99.100.137',
#                 3443,
#                 '1603010200010001fc030386e24c3add646e2e79656b74616e65742e636f6d646c2e676f6f676c652e636f6d666172616B61762E636F6D160301020001000100000000000000000000000000000000')





class Singleton(type):
    instance = None

    def __call__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super(Singleton, cls).__call__(*args, **kwargs)
        return cls.instance


class Session:
    session_list = dict()
    folder = "Files/Sessions"
    @staticmethod
    def get_session(phone):
        print(phone)
        if phone in Session.session_list.keys():
            return Session.session_list[phone]
        else:
            print("new")
            Session.session_list[phone] = Session(phone_number=phone, folder=Session.folder)
            return Session.session_list[phone]
        
    def __init__(self,phone_number, folder='Files/Sessions'):
        self.phone = str(phone_number)
        self.folder = str(folder)        
        self.Flood = False
        self.limit = ''
        self.actions = 0
        self.ok = 0
        self.client: TelegramClient
        self.me = None
        self.sent_code = False
        self.loop = asyncio.new_event_loop()
        res = self.async_event_loop(self.m_init())
        print(res)
        print(self.__dict__)        

    def async_event_loop(self,function_,loop=None):
        if loop:
            res = loop.run_until_complete(function_)
        else:
            res = self.loop.run_until_complete(function_)
        return res  


    async def m_init(self):
        self.client = TelegramClient(
            f'{self.folder}/{self.phone}.session'
            , 2626653
            , 'b8d22c3c3c57c4e4ff7d3c523d99dc8c'
            # , connection=con_
            # , proxy=proxy_
        )
        # await self.connect()

        #time.sleep(5)

    def str(self):
        mstr = ''
        mstr += f', {self.phone}'
        mstr += f', {self.folder}'
        mstr += f', {self.Flood}'
        mstr += f', {self.limit}'
        mstr += f', {self.acctions}'
        mstr += f', {self.ok}'
        return mstr

    async def check_connect(self):
        try:
            await self.client.connect()
            if await self.client.is_user_authorized():
                self.me = await self.client.get_me()
                await self.client.disconnect()
                print("connected")
                return True            
            return False
        except Exception as e:
            tools.utils.show_error(e, __file__)
            return False

    async def connect(self):
        await self.client.connect()
        if not await self.client.is_user_authorized():
            await self.client.send_code_request(self.phone)
            try:
                await self.client.sign_in(self.phone,
                                         input('\nWe send a code for ' + self.phone + '\nEnter code: '))
            except SessionPasswordNeededError:
                await self.client.sign_in(password=input('\nPlease enter your password: '))
        self.me = await self.client.get_me()
        #self.client.run_until_disconnected()

    async def send_code(self):
        await self.client.connect()
        if not await self.client.is_user_authorized():
            await self.client.send_code_request(self.phone)
            self.sent_code = True
            return True
        else:
            return False

    async def verify_code(self, verifycode, password=None):
        if self.sent_code:
            try:
                await self.client.sign_in(self.phone, verifycode)
            except SessionPasswordNeededError:
                await self.client.sign_in(password=password)
            self.me = await self.client.get_me()
            self.sent_code = False
            await self.client.disconnect()
            return True

    async def get_user_by_phone(self, phone, disconnect=True):
        try:
            await self.client.connect()
            contact = InputPhoneContact(client_id=0, phone=phone, first_name="", last_name="")
            result = await self.client(ImportContactsRequest([contact]))
            return result.users[0]
        except Exception as e:
            tools.utils.show_error(e, __file__)
        finally:
            if disconnect:
                await self.client.disconnect()

    async def send_message(self, receiver, text,images=None,buttons=None,disconnect=True):
        try:
            await self.client.connect()
            if await self.client.is_user_authorized():
                if not images:
                    message = await self.client.send_message(receiver, text, buttons=buttons, parse_mode='html')
                else:
                    message = await self.client.send_file(receiver, images, caption=text, buttons=buttons, parse_mode='html')
                return True, message
            else:
                return False, "Session not connected"
        except Exception as e:
            return False, str(e)
        finally:
            if disconnect:
                await self.client.disconnect()



class Bot:
    session_list = dict()
    folder = "Files/Sessions"
    footer = """
<b> با تشکر- شرکت رهاورد تجارت آینده ♾<b/>
"""
    static_buttons = [
        [
            Button.text("سفارشات در جریان", ),
            Button.text("همه سفارشات",resize=True)
        ],
        [
            Button.text("♾درباره ما", ),
        ]
    ]

    @staticmethod
    def get_session(bot_name, token):
        if bot_name in Bot.session_list.keys():
            return Bot.session_list[bot_name]
        else:
            print("new")
            Bot.session_list[bot_name] = Bot(name=bot_name, token=token, folder=Bot.folder)
            return Bot.session_list[bot_name]

    async def run(self):
        print("sss")
        await self.start(False)
        print(f"Run Bot {self.name} until disconnected")
        await self.client.run_until_disconnected()

    async def start(self, disconnect=True):
        await self.client.start(bot_token=self.token)
        if disconnect:
            await self.client.disconnect()

    def add_event(self, callback, event):
        self.client.add_event_handler(callback, event)

    def __init__(self, name, token, folder="Files/Sessions"):
        self.name = str(name)
        self.folder = str(folder)
        self.token = token
        self.client: TelegramClient
        self.loop = asyncio.new_event_loop()
        self.async_event_loop(self.m_init())
        self.run_event_lissener = False

    async def m_init(self):
        self.client = TelegramClient(f"{self.folder}/{self.name}", 2626653
                       , 'b8d22c3c3c57c4e4ff7d3c523d99dc8c'
                       # , connection=con_# connection.ConnectionTcpMTProxyRandomizedIntermediate
                       # , proxy=proxy_
                       )
        self.client.parent = self
        await self.start()

    def async_event_loop(self,function_):
        res = self.loop.run_until_complete(function_)
        return res

    def run_until_complete(self):
        #self.run()
        # task = self.loop.create_task(self.run())
        if not self.run_event_lissener:
            loop = asyncio.new_event_loop()
            loop.run_in_executor(None, self.loop.run_until_complete,self.run())
            self.run_event_lissener = True

    async def send_message(self, receiver, text, images=None,buttons=None):
        try:
            await self.client.connect()
            if await self.client.is_user_authorized():
                if not images:
                    message = await self.client.send_message(receiver, text, buttons=buttons, parse_mode='html')
                else:
                    message = await self.client.send_file(receiver, images, caption=text, buttons=buttons, parse_mode='html')
                return True, message
            else:
                return False, "Bot not connected"
        except Exception as e:
            return False,str(e)
        finally:
            # await self.client.disconnect()
            print('finally')


    @staticmethod
    async def usr_bot_commands(event=None):
        from tlg.models import ReceivedMessage as RM, Receiver, MessageDetail, SenderType,ReceiverTelegramBotSession as RTBS
        event.message_id = event.message.id
        event.message_text = event.message.text
        # await event.reply("hi",buttons=Bot.static_buttons)
        # return
        sender_obj = await RM.receive_new_message(event)
        try:
            if event.message.text == '/start':
                await MessageDetail.send_message(SenderType.Bot,event.client.parent,sender_obj,
f'''
با سلام
لطفا کد مشتری خود را جهت احراز هویت وارد نمایید. 
کد مشتری در فاکتور و پیش فاکتورهای شما (صادره توسط شرکت رهاورد تجارت آینده)  درج شده است. 
همچنین می توانید جهت دریافت کد مربوطه با کارشناس فروش خود تماس بگیرید.
و یا شماره تلفن مرتبط خود را به عنوان کد وارد نمایید.
{Bot.footer}''')
                cache.set(f'{event.chat_id}_status', 'get_customer_code', 600)
                return
            if cache.get(f'{event.chat_id}_status') == 'get_customer_code':
                code = event.message.text
                if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
                    receiver = Receiver.objects.filter(Q(customer_code=code) | Q(phone_number=code)).first()
                else:
                    receiver = await Receiver.objects.filter(Q(customer_code=code) | Q(phone_number=code)).afirst()
                if receiver:
                    phone_number = f'98{receiver.phone_number[1:]}' if receiver.phone_number.startswith('0') else receiver.phone_number
                    reg_code = f'{random.randint(10000,99999)}'
                    receiver_obj = await RTBS.get_receiver_by_phone(event.client.parent.session,phone_number)
                    await MessageDetail.send_message(SenderType.Usr,
                                                     event.client.parent.session,receiver_obj,
f"""کد اعتبار سنجی برای ثبت مشتری در ربات تلگرام مشتریان <b>رهاورد تجارت آینده</b>: 
<code>{reg_code}</code>
{Bot.footer}""")
                    await MessageDetail.send_message(SenderType.Bot, event.client.parent, sender_obj,
                                                     f'''
با احترام. کد اعتبار سنجی برای شماره تلفن مرتبط از طریق تلگرام (یا پیامک) ارسال گردید.
{Bot.footer}  ''')
                    cache.set(f'{event.chat_id}_reg_code', reg_code, 600)
                    cache.set(f'{event.chat_id}_status', 'get_verification_code', 600)
                    cache.set(f'{event.chat_id}_receiver', receiver, 600)
                else:
                    await MessageDetail.send_message(SenderType.Bot, event.client.parent, sender_obj,
                                                     f'''
با احترام. شماره تماس/ کد مشتری شما در شرکت رهاورد تجارت آینده ثبت نشده است.
جهت رفع مشکل لطفا با کارشناس فروش خود در ارتباط باشید.
{Bot.footer}  ''')
                return
            if cache.get(f'{event.chat_id}_status') == 'get_verification_code':
                if cache.get(f'{event.chat_id}_reg_code') == event.message.text:
                    receiver = cache.get(f'{event.chat_id}_receiver')
                    sender_obj.receiver = receiver
                    if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
                        sender_obj.save()
                    else:
                        await sender_obj.asave()

                    await MessageDetail.send_message(SenderType.Bot, event.client.parent, sender_obj,
                                                    f'''
اکانت شما به عنوان طرف حساب مرتبط نزد شرکت رهاورد تجارت آینده با اطلاعات کاربری {receiver.name} ثبت کردید.
تلفن معتبر شما: {receiver.phone_number}
شماره مشتری شما: {receiver.customer_code}
{Bot.footer}''',buttons=Bot.static_buttons)
                    cache.set(f'{event.chat_id}_status', 'none', 600)
                return
            if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
                receiver = Receiver.objects.filter(pk=sender_obj.receiver_id).first()
            else:
                receiver = await Receiver.objects.filter(pk=sender_obj.receiver_id).afirst()
            from dw.models import NewOrder
            if event.message_text == "همه سفارشات" or\
                event.message_text == "سفارشات در جریان":
                min_status = 1 if event.message_text=="همه سفارشات" else 3
                f_str = '''/{order.code.replace("-", "_").upper()} ({to_jalali_date(order.create_date)})
    📌 <b>{order.m_status}</b>
    📦- {order.part_number[:100]} 
----------------------------------\n\n'''
                if receiver.customer_code:
                    order_list = NewOrder.get_order_list(customer_code= receiver.customer_code,min_status=min_status)
                    m_str = "لیست سفارشات تامین خارجی شما به شرح ذیل می باشد:\n\n"
                    if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
                        for order in order_list:
                            m_str += f'''/{order.code.replace("-", "_").upper()} ({to_jalali_date(order.create_date)})
        📌 <b>{order.m_status}</b>
        📦- {order.part_number[:100]} 
----------------------------------\n\n'''
                    else:
                        async for order in order_list:
                            m_str +=f'''/{order.code.replace("-","_").upper()} ({to_jalali_date(order.create_date)})
        📌 <b>{order.m_status}</b>
        📦- {order.part_number[:100]} 
    ----------------------------------\n\n'''
                    m_str += "لطفا جهت استعلام وضعیت هر سفارش لینک آن را لمس فرمایید\n"
                    m_str += Bot.footer
                    await MessageDetail.send_message(SenderType.Bot, event.client.parent, sender_obj, m_str)
                return
            if event.message_text.startswith("/A"):
                from dw.models import NewOrder
                if receiver.customer_code:
                    order_number = event.message_text.replace("_","-").replace("/","")
                    order_list = NewOrder.get_order_list(customer_code=receiver.customer_code,order_number=order_number)
                    f_str = """
<b>اطلاعات سفارش</b>

🔖شماره سفارش: {order.code}
📆 تاریخ ثبت: {order.create_date_jalaly}
📌وضعیت سفارش: {order.m_status}

📦شماره کالا: {order.sku}
   عنوان کالا: {order.part_number}

🧮تعداد درخواست: {order.request_qty:,.0f}   
   تعداد حمل شده: {order.total_pack_count:,.0f}
   تعداد رسید شده: {order.total_arrived_count:,.0f}

 ✈️پکینگ های حمل:
  {order.pack_number}

 ⏰موعد تحویل: {order.duty_date_jalaly}
                        """
                    m_str = ""
                    if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
                        for order in order_list:
                            m_str = f"اطلاعات سفارش به شماره {order_number} به شرح ذیل می باشد:\n"
                            order.create_date_jalaly = to_jalali_date(order.create_date)
                            order.duty_date_jalaly = to_jalali_date(order.duty_date)
                            m_str += f_str.format(order=order)
                    else:
                        async for order in order_list:
                            m_str = f"اطلاعات سفارش به شماره {order_number} به شرح ذیل می باشد:\n"
                            order.create_date_jalaly = to_jalali_date(order.create_date)
                            order.duty_date_jalaly = to_jalali_date(order.duty_date)
                            m_str += f_str.format(order=order)
                        m_str = m_str if m_str else "سفارش درخواستی یافت نشد!"
                    m_str += Bot.footer
                    await MessageDetail.send_message(SenderType.Bot, event.client.parent, sender_obj, m_str)
                return

        except Exception as e:
            tools.utils.show_error(e, __file__)

    # '🇮🇷✅❌⭐️✨⚡️🏆🎖🎗🎲🚚⏰⌛️🕰💵💴🛡📆🗃💌📮📩✂️📌🔗🧷🔐🔍🔒🔓💘🔎⭕️⛔️🛂⚠️♾🕐🕐🔔♥️'
    #'🌐🖤🚀🚢⛴🛳🛥🚦🛠⚙📦🧮'

    @staticmethod
    async def usr_bot_callback_query(event):
        from tlg.models import ReceivedMessage as RM, Receiver, MessageDetail, SenderType, \
            ReceiverTelegramBotSession as RTBS
        event.message_text = event.data.decode("utf-8")
        sender_obj = await RM.receive_new_message(event)
        try:
            if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
                receiver = Receiver.objects.filter(pk=sender_obj.receiver_id).first()
            else:
                receiver = await Receiver.objects.filter(pk=sender_obj.receiver_id).afirst()
            event.client.parent.send_message()
        except Exception as e:
            tools.utils.show_error(e, __file__)

def run(folder=None):
    # ses = Session.get_session("989392061165")
    # ses.async_event_loop(ses.send_message())
    my_bot = Bot.get_session("MicroModernBot_Base",'6422722067:AAGzAG7MwC3YQyH8rg5-itoFZ5x06P-d6pY')
    # my_bot2 = Bot.get_session("MicroModernBot_Base2", '6422722067:AAGzAG7MwC3YQyH8rg5-itoFZ5x06P-d6pY')
    # my_bot3= Bot.get_session("MicroModernBot_Base3", '6422722067:AAGzAG7MwC3YQyH8rg5-itoFZ5x06P-d6pY')
    # my_bot2.async_event_loop(my_bot2.start())
    # my_bot2.async_event_loop(my_bot2.send_message())
    # my_bot3.async_event_loop(my_bot3.start())
    # my_bot3.async_event_loop(my_bot3.send_message())
    my_bot.add_event(Bot.usr_bot_commands, events.NewMessage())
    my_bot.async_event_loop(my_bot.run())
    print('rr')
    my_bot.async_event_loop(my_bot.Bot.disconnect())
    print('rr')
    # await my_bot.run()
    # await my_bot.my_bot.Bot.start(bot_token='6422722067:AAGzAG7MwC3YQyH8rg5-itoFZ5x06P-d6pY')
    # await my_bot.Bot.run_until_disconnected()
    # ses = Session("989114281403")
    # await ses.connect()
    # await ses.client.send_message("hajibaba15","salam")



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # my_bot.run_until_disconnected()
    run()
    # print('start codes_coupons_bot')
    # my_bot.run_until_disconnected()


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
