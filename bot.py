import asyncio
import logging
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

from config import (
    BOT_TOKEN,
    LOGISTICS_BOT_USERNAME,
    MANAGER_CHAT_ID,
    REPOST_GROUP_ID,
    SOURCE_GROUP_IDS,
)
from google_sheets import append_row
from listings import save_listing
from scheduler import channel_push_scheduler, send_channel_push
from text_utils import (
    extract_phones,
    is_free_transport,
    looks_like_our_repost,
    strip_contacts,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

KYIV_TZ = ZoneInfo("Europe/Kyiv")

VEHICLE_TYPES = [
    "Тент",
    "Рефрижератор",
    "Контейнер",
    "Відкритий",
    "Автовоз",
    "Цистерна",
    "Інше",
]

TRANSPORT_STATE: dict[int, dict[str, Any]] = {}
SEEN_GROUP_MESSAGES: set[tuple[int, int]] = set()
SEEN_LIMIT = 3000


def now_kyiv_str() -> str:
    return datetime.now(KYIV_TZ).strftime("%Y-%m-%d %H:%M:%S")


def vehicle_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=VEHICLE_TYPES[0]), KeyboardButton(text=VEHICLE_TYPES[1])],
        [KeyboardButton(text=VEHICLE_TYPES[2]), KeyboardButton(text=VEHICLE_TYPES[3])],
        [KeyboardButton(text=VEHICLE_TYPES[4]), KeyboardButton(text=VEHICLE_TYPES[5])],
        [KeyboardButton(text=VEHICLE_TYPES[6])],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Надіслати номер телефону", request_contact=True)],
        ],
        resize_keyboard=True,
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚛 Зареєструвати вільний транспорт",
                    callback_data="start_transport",
                )
            ],
        ]
    )


def cargo_funnel_keyboard(listing_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📦 Є вантаж? Залишити заявку",
                    url=f"https://t.me/{LOGISTICS_BOT_USERNAME}?start=t_{listing_id}",
                )
            ]
        ]
    )


def clear_state(user_id: int) -> None:
    TRANSPORT_STATE.pop(user_id, None)


def remember_message(chat_id: int, message_id: int) -> bool:
    key = (chat_id, message_id)
    if key in SEEN_GROUP_MESSAGES:
        return False
    SEEN_GROUP_MESSAGES.add(key)
    if len(SEEN_GROUP_MESSAGES) > SEEN_LIMIT:
        extra = len(SEEN_GROUP_MESSAGES) - SEEN_LIMIT
        for _ in range(extra):
            SEEN_GROUP_MESSAGES.pop()
    return True


def format_public_form_post(data: dict[str, Any]) -> str:
    return (
        "🚛 <b>ВІЛЬНИЙ ТРАНСПОРТ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📍 <b>Місце дислокації:</b> {data.get('location', '')}\n"
        f"🚛 <b>Тип авто:</b> {data.get('vehicle_type', '')}\n"
        f"📐 <b>Об'єм:</b> {data.get('volume', '')} м³\n"
        f"⚖️ <b>Вантажопідйомність:</b> {data.get('capacity', '')} т\n"
        f"🔢 <b>Кількість авто:</b> {data.get('vehicle_count', '')}\n"
        f"🗓 <b>Дата готовності:</b> {data.get('ready_date', '')}\n"
        f"🇺🇦 <b>Напрямок:</b> {data.get('direction', '')}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 Маєте вантаж під це направлення?\n"
        "Залиште заявку — організуємо перевезення."
    )


def format_public_group_post(clean_text: str) -> str:
    return (
        "🚛 <b>ВІЛЬНИЙ ТРАНСПОРТ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{clean_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 Маєте вантаж під це направлення?\n"
        "Залиште заявку — організуємо перевезення."
    )


def format_internal_form_message(data: dict[str, Any], user, listing_id: str) -> str:
    username = f"@{user.username}" if user.username else "Не вказано"
    full_name = user.full_name or user.first_name or "—"
    return (
        "🚛 <b>НОВИЙ ВІЛЬНИЙ ТРАНСПОРТ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 <b>Картка:</b> <code>t_{listing_id}</code>\n"
        f"📍 <b>Місце дислокації:</b> {data.get('location', '')}\n"
        f"🚛 <b>Тип авто:</b> {data.get('vehicle_type', '')}\n"
        f"📐 <b>Об'єм:</b> {data.get('volume', '')} м³\n"
        f"⚖️ <b>Вантажопідйомність:</b> {data.get('capacity', '')} т\n"
        f"🔢 <b>Кількість авто:</b> {data.get('vehicle_count', '')}\n"
        f"🗓 <b>Дата готовності:</b> {data.get('ready_date', '')}\n"
        f"🇺🇦 <b>Напрямок:</b> {data.get('direction', '')}\n"
        f"💬 <b>Коментар:</b> {data.get('comment', '—')}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Перевізник:</b> {full_name}\n"
        f"📱 <b>Телефон:</b> {data.get('phone', '')}\n"
        f"💬 <b>Username:</b> {username}\n"
        f"🆔 <b>User ID:</b> {user.id}"
    )


def is_source_group(chat_id: int) -> bool:
    if chat_id in {REPOST_GROUP_ID, MANAGER_CHAT_ID}:
        return False
    if SOURCE_GROUP_IDS:
        return chat_id in SOURCE_GROUP_IDS
    return True


async def send_main_menu(message: Message):
    text = (
        "🚛 Є вільний транспорт?\n\n"
        "Зареєструйте свій автомобіль — наші логісти швидко "
        "підберуть направлення та вантаж.\n\n"
        "Вкажіть місце дислокації, тип авто та готовність — "
        "і ми знайдемо для вас вантаж!"
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


async def start_handler(message: Message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    clear_state(user_id)

    text = message.text or ""
    if "transport" in text.lower():
        TRANSPORT_STATE[user_id] = {"step": "location"}
        await message.answer(
            "👋 Допоможу зареєструвати вільний транспорт.\n\n"
            "📍 Вкажіть місце дислокації авто (місто, країна):",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await send_main_menu(message)


async def start_transport_callback(call: CallbackQuery):
    if call.message.chat.type != "private":
        await call.answer("Будь ласка, напишіть боту в приватні повідомлення.", show_alert=True)
        return

    user_id = call.from_user.id
    clear_state(user_id)
    TRANSPORT_STATE[user_id] = {"step": "location"}

    try:
        await call.message.delete()
    except Exception:
        pass

    await call.message.answer(
        "👋 Допоможу зареєструвати вільний транспорт.\n\n"
        "📍 Вкажіть місце дислокації авто (місто, країна):",
        reply_markup=ReplyKeyboardRemove(),
    )
    await call.answer()


def build_form_listing(state: dict[str, Any], user, phone: str) -> dict[str, Any]:
    public_text = (
        f"Дислокація: {state.get('location', '')}\n"
        f"Тип авто: {state.get('vehicle_type', '')}\n"
        f"Об'єм: {state.get('volume', '')} м³\n"
        f"Вантажопідйомність: {state.get('capacity', '')} т\n"
        f"Кількість авто: {state.get('vehicle_count', '')}\n"
        f"Дата готовності: {state.get('ready_date', '')}\n"
        f"Напрямок: {state.get('direction', '')}"
    )
    return {
        "source": "bot_form",
        "public_text": public_text,
        "original_text": public_text,
        "location": state.get("location", ""),
        "vehicle_type": state.get("vehicle_type", ""),
        "direction": state.get("direction", ""),
        "carrier_name": user.full_name or user.first_name or "—",
        "carrier_username": user.username or "",
        "carrier_user_id": user.id,
        "carrier_phone": phone,
    }


async def publish_public_listing(
    bot: Bot,
    listing_id: str,
    public_html: str,
    photo_id: Optional[str] = None,
) -> None:
    keyboard = cargo_funnel_keyboard(listing_id)
    if photo_id:
        caption = public_html
        if len(caption) > 1024:
            caption = caption[:1020] + "…"
        await bot.send_photo(
            chat_id=REPOST_GROUP_ID,
            photo=photo_id,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        return

    await bot.send_message(
        chat_id=REPOST_GROUP_ID,
        text=public_html,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


async def finalize_transport(message: Message, phone: str) -> None:
    user = message.from_user
    user_id = user.id
    state = TRANSPORT_STATE.get(user_id, {})
    state["phone"] = phone

    listing = build_form_listing(state, user, phone)
    listing_id = save_listing(listing)

    try:
        await publish_public_listing(
            message.bot,
            listing_id,
            format_public_form_post(state),
        )
        log.info("Транспорт %s опубліковано в групу %s", listing_id, REPOST_GROUP_ID)
    except Exception as e:
        log.error("Помилка публікації в групу %s: %s", REPOST_GROUP_ID, e)

    try:
        await message.bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=format_internal_form_message(state, user, listing_id),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        log.error("Помилка надсилання менеджерам %s: %s", MANAGER_CHAT_ID, e)

    answers_text = (
        f"ID: t_{listing_id}; "
        f"Дислокація: {state.get('location', '')}; "
        f"Тип авто: {state.get('vehicle_type', '')}; "
        f"Об'єм: {state.get('volume', '')} м³; "
        f"Вантажопідйомність: {state.get('capacity', '')} т; "
        f"К-сть авто: {state.get('vehicle_count', '')}; "
        f"Дата готовності: {state.get('ready_date', '')}; "
        f"Напрямок: {state.get('direction', '')}; "
        f"Коментар: {state.get('comment', '—')}"
    )
    try:
        append_row(
            date_str=now_kyiv_str(),
            name=user.full_name or user.first_name or "—",
            username=user.username,
            phone=phone,
            answers=answers_text,
            tag="transport",
            contact_method="Вільний транспорт",
        )
        log.info("Дані збережено в Google Sheets для користувача %s", user_id)
    except Exception as e:
        log.error("Помилка збереження в Google Sheets: %s", e)

    clear_state(user_id)

    await message.answer(
        "Дякуємо! Ваш транспорт зареєстровано ✅\n\n"
        "Наші логісти вже підбирають вантаж для вашого авто. "
        "Очікуйте на зворотний зв'язок!",
        reply_markup=ReplyKeyboardRemove(),
    )
    await send_main_menu(message)


async def handle_group_transport(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    if message.chat.type not in {"group", "supergroup"}:
        return
    if not is_source_group(message.chat.id):
        return
    if not remember_message(message.chat.id, message.message_id):
        return

    raw_text = (message.text or message.caption or "").strip()
    if not raw_text or looks_like_our_repost(raw_text):
        return
    if raw_text.startswith("/"):
        return
    if not is_free_transport(raw_text):
        return

    clean_text = strip_contacts(raw_text)
    if len(clean_text) < 12:
        log.info("Пропуск поста %s: після очистки майже не лишилось тексту", message.message_id)
        return

    user = message.from_user
    phones = extract_phones(raw_text)
    listing = {
        "source": "group",
        "public_text": clean_text,
        "original_text": raw_text,
        "carrier_name": user.full_name or user.first_name or "—",
        "carrier_username": user.username or "",
        "carrier_user_id": user.id,
        "carrier_phone": phones,
        "source_chat_id": message.chat.id,
        "source_chat_title": message.chat.title or "",
        "source_message_id": message.message_id,
    }
    listing_id = save_listing(listing)

    photo_id = message.photo[-1].file_id if message.photo else None
    public_html = format_public_group_post(clean_text)
    try:
        await publish_public_listing(message.bot, listing_id, public_html, photo_id=photo_id)
        log.info(
            "Репост транспорту %s з групи %s в %s",
            listing_id,
            message.chat.id,
            REPOST_GROUP_ID,
        )
    except Exception as e:
        log.error("Помилка репосту транспорту %s: %s", listing_id, e)
        return

    answers_text = (
        f"ID: t_{listing_id}; "
        f"Група: {message.chat.title or message.chat.id}; "
        f"Текст: {raw_text}"
    )
    try:
        append_row(
            date_str=now_kyiv_str(),
            name=user.full_name or user.first_name or "—",
            username=user.username,
            phone=phones or "з групи",
            answers=answers_text,
            tag="transport_group",
            contact_method="Вільний транспорт з групи",
        )
    except Exception as e:
        log.error("Помилка збереження групового транспорту в Sheets: %s", e)


async def handle_message(message: Message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    state = TRANSPORT_STATE.get(user_id)

    if not state:
        await send_main_menu(message)
        return

    text = (message.text or "").strip()
    step = state.get("step")

    if step == "location":
        if not text:
            await message.answer("📍 Вкажіть місце дислокації авто (місто, країна):")
            return
        state["location"] = text
        state["step"] = "vehicle_type"
        await message.answer("🚛 Оберіть тип авто:", reply_markup=vehicle_keyboard())
        return

    if step == "vehicle_type":
        if text == "Інше":
            state["step"] = "vehicle_type_custom"
            await message.answer(
                "🚛 Введіть тип авто вручну:",
                reply_markup=ReplyKeyboardRemove(),
            )
            return
        if text not in VEHICLE_TYPES:
            await message.answer(
                "🚛 Оберіть тип авто з кнопок нижче або натисніть «Інше»:",
                reply_markup=vehicle_keyboard(),
            )
            return
        state["vehicle_type"] = text
        state["step"] = "volume"
        await message.answer("📐 Введіть об'єм кузова (м³):", reply_markup=ReplyKeyboardRemove())
        return

    if step == "vehicle_type_custom":
        if not text:
            await message.answer("🚛 Введіть тип авто вручну:")
            return
        state["vehicle_type"] = text
        state["step"] = "volume"
        await message.answer("📐 Введіть об'єм кузова (м³):")
        return

    if step == "volume":
        if not text:
            await message.answer("📐 Введіть об'єм кузова (м³):")
            return
        state["volume"] = text
        state["step"] = "capacity"
        await message.answer("⚖️ Введіть вантажопідйомність (тонн):")
        return

    if step == "capacity":
        if not text:
            await message.answer("⚖️ Введіть вантажопідйомність (тонн):")
            return
        state["capacity"] = text
        state["step"] = "vehicle_count"
        await message.answer("🔢 Введіть кількість вільних авто:")
        return

    if step == "vehicle_count":
        if not text:
            await message.answer("🔢 Введіть кількість вільних авто:")
            return
        state["vehicle_count"] = text
        state["step"] = "ready_date"
        await message.answer("🗓 Вкажіть дату готовності (наприклад: 05.09.2026 або «зараз»):")
        return

    if step == "ready_date":
        if not text:
            await message.answer("🗓 Вкажіть дату готовності:")
            return
        state["ready_date"] = text
        state["step"] = "direction"
        await message.answer(
            "🇺🇦 Вкажіть напрямок / куди готовий їхати\n"
            "(наприклад: Україна, Київ):"
        )
        return

    if step == "direction":
        if not text:
            await message.answer("🇺🇦 Вкажіть напрямок / куди готовий їхати:")
            return
        state["direction"] = text
        state["step"] = "comment"
        await message.answer(
            "💬 Додатковий коментар (або напишіть «—» щоб пропустити):"
        )
        return

    if step == "comment":
        if not text:
            await message.answer("💬 Додатковий коментар (або «—»):")
            return
        state["comment"] = text if text != "—" else "—"
        state["step"] = "phone"
        await message.answer(
            "📞 Надішліть ваш номер телефону для зворотного зв'язку:\n\n"
            "Натисніть кнопку нижче або введіть номер вручну.",
            reply_markup=phone_keyboard(),
        )
        return

    if step == "phone":
        if message.contact and message.contact.phone_number:
            phone = message.contact.phone_number
        elif text:
            phone = text
        else:
            await message.answer(
                "📞 Надішліть номер телефону кнопкою або текстом.",
                reply_markup=phone_keyboard(),
            )
            return
        await finalize_transport(message, phone)
        return

    await send_main_menu(message)


async def test_push_handler(message: Message):
    await message.answer("⏳ Відправляю тестовий пуш в канал...")
    await send_channel_push(message.bot)
    await message.answer("✅ Готово! Перевір канал.")


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    asyncio.create_task(channel_push_scheduler(bot))

    dp.message.register(start_handler, CommandStart())
    dp.message.register(test_push_handler, Command("testpush"))
    dp.callback_query.register(start_transport_callback, F.data == "start_transport")
    dp.message.register(handle_group_transport, F.chat.type.in_({"group", "supergroup"}))
    dp.message.register(handle_message)

    log.info("Transport Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
