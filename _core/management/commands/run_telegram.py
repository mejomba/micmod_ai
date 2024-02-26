import os

from django.core.management.base import BaseCommand
from telethon import events

import _keenthemes.settings
from tlg.scripts.telethon_ import Bot, Session


class Command(BaseCommand):
    help = 'This command run main bots in telegram for lessening commands of customers'

    def handle(self, *args, **kwargs):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dason.settings")
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        import django
        django.setup()
        dason.settings.DATABASES = {
            'default': {
                'ENGINE': os.environ.get('PG_ENGIN'),
                'NAME': os.environ.get('PG_NAME'),
                'USER': os.environ.get('PG_USER'),
                'PASSWORD': os.environ.get('PG_PASSWORD'),
                'HOST': os.environ.get('PG_HOST'),
                'PORT': os.environ.get('PG_PORT'),
            },
            'sepidar': {
                'ENGINE': os.environ.get('SE_ENGIN'),
                'NAME': os.environ.get('SE_NAME'),
                'USER': os.environ.get('SE_USER'),
                'PASSWORD': os.environ.get('SE_PASSWORD'),
                'HOST': os.environ.get('SE_HOST'),
                # 'PORT': DB_PIRINEOS_PORT,
                'OPTIONS': {'driver': 'ODBC Driver 17 for SQL Server', },
            },
            'dw': {
                'ENGINE': os.environ.get('DW_ENGIN'),
                'NAME': os.environ.get('DW_NAME'),
                'USER': os.environ.get('DW_USER'),
                'PASSWORD': os.environ.get('DW_PASSWORD'),
                'HOST': os.environ.get('DW_HOST'),
                # 'PORT': DB_PIRINEOS_PORT,
                'OPTIONS': {'driver': 'ODBC Driver 17 for SQL Server', },
            },
        }
        from tlg.models import Bot as BotModel, Session as SessionModel
        Bot.folder = f"tlg/scripts/Files/Sessions"
        Session.folder = f"tlg/scripts/Files/Sessions"
        bot_data = BotModel.objects.filter(name='micromodernMainBot').first()
        if not bot_data:
            bot_data = BotModel.objects.create(creator_user_id=1, editor_user_id=1,
                                    username="MicroModernBot", name="micromodernMainBot",
                                    token="6422722067:AAGzAG7MwC3YQyH8rg5-itoFZ5x06P-d6pY")
        my_bot = Bot.get_session(f'{bot_data.name}1', bot_data.token)
        my_bot.bot_data = bot_data
        my_bot.add_event(Bot.usr_bot_commands, events.NewMessage())
        my_bot.add_event(Bot.usr_bot_callback_query, events.CallbackQuery())
        session_data = SessionModel.objects.filter(phone_number="989392061165").first()
        if not session_data:
            session_data = SessionModel.objects.create(creator_user_id=1, editor_user_id=1,
                                    telegram_id="1137854879", phone_number="989392061165",
                                    session_string="چاوشی", telegram_password="667327")
        session = Session.get_session(session_data.phone_number)
        session.session_data = session_data
        my_bot.session = session
        my_bot.run_until_complete()
