import os

from django.apps import AppConfig
from telethon import events
# from .scripts.telethon_ import Bot, Session


class TelegramConfig(AppConfig):
    default_app_config = 'mydjangoapp.apps.MydjangoappConfig'
    name = 'tlg'

    # def ready(self):
    #     if os.environ.get('RUN_MAIN'):
    #         ...
    #         # from .models import Bot as BotModel, Session as SessionModel
    #         # Bot.folder = f"tlg/scripts/Files/Sessions"
    #         # Session.folder = f"tlg/scripts/Files/Sessions"
    #         # bot_data = BotModel.objects.filter(name='micromodernMainBot').first()
    #         # my_bot = Bot.get_session(f'{bot_data.name}1', bot_data.token)
    #         # my_bot.bot_data = bot_data
    #         # my_bot.add_event(Bot.usr_bot_commands, events.NewMessage())
    #         # my_bot.add_event(Bot.usr_bot_callback_query, events.CallbackQuery())
    #         # session_data = SessionModel.objects.filter(phone_number="989392061165").first()
    #         # session = Session.get_session(session_data.phone_number)
    #         # session.session_data = session_data
    #         # my_bot.session = session
    #         # my_bot.run_until_complete()
    #     else:
    #         print('dd')
