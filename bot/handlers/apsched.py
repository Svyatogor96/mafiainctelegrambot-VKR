from aiogram import Bot


async def send_message_time(bot: Bot):
    await bot.send_message(chat_id=111, text="Text")


async def send_message_cron(bot: Bot):
    await bot.send_message(chat_id=111, text="Text")


async def send_message_interval(bot: Bot):
    await bot.send_message(chat_id=111, text="Text")

