#!/usr/bin/env python3
"""Окремий ретранслятор: копіює нові пости з SOURCE у DEST, без дубля планового пуша."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import Message

from relay_config import BOT_TOKEN, DEST_CHAT_ID, SOURCE_CHAT_ID
from relay_filters import is_transport_promo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("relay")

SEEN: set[int] = set()
SEEN_LIMIT = 4000


class RetryingSession(AiohttpSession):
    async def make_request(self, bot, method, timeout=None):
        last_error = None
        for attempt in range(3):
            try:
                return await super().make_request(bot, method, timeout=timeout)
            except TelegramNetworkError as e:
                last_error = e
                log.warning("Telegram timeout, повтор %s/3", attempt + 1)
                await asyncio.sleep(1.5 * (attempt + 1))
        raise last_error


def remember(message_id: int) -> bool:
    if message_id in SEEN:
        return False
    SEEN.add(message_id)
    while len(SEEN) > SEEN_LIMIT:
        SEEN.pop()
    return True


async def copy_with_retry(bot: Bot, message_id: int) -> None:
    last_error = None
    for attempt in range(3):
        try:
            await bot.copy_message(
                chat_id=DEST_CHAT_ID,
                from_chat_id=SOURCE_CHAT_ID,
                message_id=message_id,
            )
            log.info("Скопійовано %s → %s", message_id, DEST_CHAT_ID)
            return
        except TelegramNetworkError as e:
            last_error = e
            log.warning("Таймаут копіювання %s, повтор %s/3", message_id, attempt + 1)
            await asyncio.sleep(1.5 * (attempt + 1))
        except Exception as e:
            log.error("Не вдалося скопіювати %s: %s", message_id, e)
            return
    log.error("Не вдалося скопіювати %s: %s", message_id, last_error)


async def relay_post(message: Message) -> None:
    if message.chat.id != SOURCE_CHAT_ID:
        return
    if not remember(message.message_id):
        return

    text = message.text or message.caption or ""
    if is_transport_promo(text):
        log.info("Пропуск планового пуша %s, щоб не дублювати в %s", message.message_id, DEST_CHAT_ID)
        return

    await copy_with_retry(message.bot, message.message_id)


async def log_other_post(message: Message) -> None:
    log.info(
        "Ігнор: чат %s (%s), msg %s — це не джерело %s",
        message.chat.id,
        message.chat.type,
        message.message_id,
        SOURCE_CHAT_ID,
    )


async def main() -> None:
    bot = Bot(token=BOT_TOKEN, session=RetryingSession(timeout=90.0))
    dp = Dispatcher()
    dp.channel_post.register(relay_post, F.chat.id == SOURCE_CHAT_ID)
    dp.message.register(relay_post, F.chat.id == SOURCE_CHAT_ID)
    dp.channel_post.register(log_other_post)
    dp.message.register(log_other_post)
    log.info("Ретранслятор запущено: %s → %s", SOURCE_CHAT_ID, DEST_CHAT_ID)
    await dp.start_polling(bot, allowed_updates=["message", "channel_post"])


if __name__ == "__main__":
    asyncio.run(main())
