import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from config import CHANNEL_ID

log = logging.getLogger(__name__)

KYIV_TZ = ZoneInfo("Europe/Kyiv")

PUSH_WEEKDAYS = {0, 1, 2, 3, 4}
PUSH_HOUR = 11
PUSH_MINUTE = 30

PUSH_TEXT = (
    "🚛 Є вільний транспорт?\n\n"
    "Зареєструйте свій автомобіль — наші логісти швидко підберуть "
    "направлення та вантаж для вас.\n\n"
    "Працюємо з перевізниками по всій Європі та Україні."
)


def push_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚛 Зареєструвати транспорт",
                    url=f"https://t.me/{bot_username}?start=transport",
                )
            ]
        ]
    )


async def send_channel_push(bot: Bot) -> None:
    if not CHANNEL_ID:
        log.warning("CHANNEL_ID не встановлено, пуш не відправлено")
        return

    try:
        bot_info = await bot.get_me()
        keyboard = push_keyboard(bot_info.username)

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=PUSH_TEXT,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
        log.info("Пуш-повідомлення відправлено в канал %s", CHANNEL_ID)
    except Exception as e:
        log.error("Помилка відправки пушу в канал: %s", e)


async def channel_push_scheduler(bot: Bot) -> None:
    log.info("Планувальник пушів запущено")

    while True:
        now = datetime.now(KYIV_TZ)

        if (
            now.weekday() in PUSH_WEEKDAYS
            and now.hour == PUSH_HOUR
            and now.minute == PUSH_MINUTE
        ):
            await send_channel_push(bot)
            await asyncio.sleep(61)
        else:
            await asyncio.sleep(30)
