from telethon_ import Bot
from telethon import events, errors




if __name__ == '__main__':
    my_bot = Bot.get_session("MicroModernBot_Base", '6422722067:AAGzAG7MwC3YQyH8rg5-itoFZ5x06P-d6pY')
    my_bot.add_event(Bot.usr_bot_commands, events.NewMessage())
    my_bot.async_event_loop(my_bot.run())
    print('rr')
    my_bot.async_event_loop(my_bot.Bot.disconnect())
    print('rr')