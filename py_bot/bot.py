"""Telegram-бот «Аналитик Pac-Man Hunt» (ЛР 3, вариант 22).

Бот - это сервис-помощник для игры, а НЕ копия игры в чате. Сама игра
(лабиринт, Призрак, ИИ Пакмана) живёт в Pygame-приложении из ЛР 1-2.
Бот работает только с данными, которые игра выгружает:
    records.csv - таблица рекордов (строка на партию);
    game.log    - журнал событий игры.

Что умеет:
    кнопки меню  - топ игроков, моя статистика, ачивки, статистика по логу,
                   загрузка результатов, указать имя, подписка;
    /start /help /menu /cancel /top /stats /whoami - команды для всех;
    /log [N], /broadcast - команды администратора (id из ADMIN_IDS).

Архитектура:
    * stateless - данные пользователя в sessions/<user_id>.json (session.py);
    * FSM aiogram - режимы MENU / UPLOAD / WAIT_NAME / BROADCAST;
    * антифлуд - у пользователя одно сообщение-экран, бот его редактирует
      (bot.edit_message_text) вместо отправки новых;
    * тяжёлый разбор файлов вынесен в поток (asyncio.to_thread);
    * лог событий бота - py_bot/bot_flight.log.

Запуск из корня проекта:  python py_bot/bot.py
"""

import asyncio
import html
import io
import logging
import sys
import time
from pathlib import Path

# Папка бота в sys.path: модули config, session... находятся при любом
# способе запуска (python py_bot/bot.py, из тестов, из VS Code).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aiogram import Bot, Dispatcher, F  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402
from aiogram.exceptions import (  # noqa: E402
    TelegramAPIError, TelegramBadRequest, TelegramNetworkError,
    TelegramRetryAfter, TelegramServerError, TelegramUnauthorizedError,
)
from aiogram.filters import Command, CommandObject, CommandStart  # noqa: E402
from aiogram.filters import StateFilter  # noqa: E402
from aiogram.fsm.context import FSMContext  # noqa: E402
from aiogram.fsm.state import State, StatesGroup  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.types import CallbackQuery, ErrorEvent, Message  # noqa: E402
from aiogram.utils.token import TokenValidationError  # noqa: E402

import analytics  # noqa: E402
import config  # noqa: E402
import keyboards  # noqa: E402
import session  # noqa: E402

logger = logging.getLogger("py_bot")


# ---------- Логирование ----------
def setup_logging(path=None):
    """Лог бота в файл (и в консоль) в формате «время | уровень | текст»."""
    path = path or config.BOT_LOG
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s",
                                  datefmt="%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for old in list(root.handlers):
        root.removeHandler(old)
    for handler in (logging.FileHandler(path, encoding="utf-8"),
                    logging.StreamHandler(sys.stdout)):
        handler.setFormatter(formatter)
        root.addHandler(handler)


# ---------- FSM: режимы диалога ----------
class BotState(StatesGroup):
    """Конечный автомат: что бот сейчас ждёт от пользователя."""

    MENU = State()        # свободный выбор в меню
    UPLOAD = State()      # ждём файл records.csv (или game.log)
    WAIT_NAME = State()   # ждём имя игрока
    BROADCAST = State()   # админ вводит текст рассылки


# Диспетчер создаётся без токена, поэтому модуль можно импортировать
# в тестах. Сам Bot создаётся в create_bot() при запуске.
dp = Dispatcher(storage=MemoryStorage())


def create_bot(token=None):
    """Создаёт Bot с HTML-разметкой по умолчанию.

    Raises:
        SystemExit: токен не задан или имеет неверный формат -
            с понятной подсказкой, что делать.
    """
    token = (token if token is not None else config.BOT_TOKEN).strip()
    if not token:
        raise SystemExit(
            "Не задан BOT_TOKEN. Создайте бота у @BotFather и впишите токен "
            "в файл py_bot/.env (строка BOT_TOKEN=...), образец - "
            "py_bot/.env.example.")
    try:
        return Bot(token=token,
                   default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    except TokenValidationError:
        raise SystemExit(
            "BOT_TOKEN в py_bot/.env имеет неверный формат. Скопируйте "
            "токен от @BotFather целиком (вид 123456789:AAE...).") from None


# ---------- Вспомогательные функции ----------
def is_admin(user_id):
    """Есть ли пользователь в списке администраторов."""
    return user_id in config.ADMIN_IDS


async def set_mode(state, user_id, mode):
    """Переводит FSM в состояние и записывает его название в сессию."""
    await state.set_state(getattr(BotState, mode))
    session.update_session(user_id, state=mode)


async def safe_answer(callback, text=None, alert=False):
    """callback.answer() в try/except.

    Без answer у кнопки крутятся «часики». Если бот долго не отвечал,
    Telegram вернёт «query is too old» - это не повод падать.
    """
    try:
        await callback.answer(text, show_alert=alert)
    except TelegramAPIError as err:
        logger.info("callback.answer не прошёл: %s", err)


async def send_with_retry(bot, chat_id, text, **kwargs):
    """send_message с одним повтором при сетевом сбое или 429."""
    try:
        return await bot.send_message(chat_id, text, **kwargs)
    except TelegramRetryAfter as err:
        logger.warning("Лимит Telegram, ждём %s с", err.retry_after)
        await asyncio.sleep(err.retry_after)
    except (TelegramNetworkError, TelegramServerError) as err:
        logger.warning("Сбой отправки (%s), повтор", err)
        await asyncio.sleep(1)
    return await bot.send_message(chat_id, text, **kwargs)


async def show_screen(bot, chat_id, user_id, text, keyboard=None):
    """Показывает экран: редактирует сообщение-экран или шлёт новое.

    1. id экрана есть в сессии и чат тот же - edit_message_text;
    2. «message is not modified» - текст не изменился, это норма;
    3. «message to edit not found» и прочее - экран удалён/недоступен,
       шлём новое сообщение и запоминаем его id в сессии.
    """
    sess = session.load_session(user_id)
    screen_id = sess.get("screen_message_id")
    if screen_id and sess.get("screen_chat_id") == chat_id:
        try:
            await bot.edit_message_text(text=text, chat_id=chat_id,
                                        message_id=screen_id,
                                        reply_markup=keyboard)
            return
        except TelegramBadRequest as err:
            if "message is not modified" in str(err):
                return
            logger.info("Экран %s недоступен (%s), отправляю новый",
                        screen_id, err)
        except TelegramAPIError as err:
            logger.info("Не удалось отредактировать экран %s: %s",
                        screen_id, err)
    msg = await send_with_retry(bot, chat_id, text, reply_markup=keyboard)
    session.update_session(user_id, screen_message_id=msg.message_id,
                           screen_chat_id=chat_id)


async def new_screen(bot, message, text, keyboard=None):
    """Экран в ответ на команду: новое сообщение внизу чата.

    Команду пользователь набирает сам, поэтому старый экран где-то выше
    по чату не редактируем, а заводим новый (он и станет экраном).
    """
    session.update_session(message.from_user.id, screen_message_id=None)
    await show_screen(bot, message.chat.id, message.from_user.id,
                      text, keyboard)


def menu_text(sess):
    """Текст главного меню."""
    name = sess.get("name")
    who = (f"Игрок: <b>{html.escape(name)}</b>" if name
           else "Имя игрока не указано - нажмите «✏️ Указать имя».")
    return ("👻 <b>Аналитик Pac-Man Hunt</b>\n"
            "Бот-помощник игры: рейтинги, статистика и ачивки по "
            "records.csv и game.log. Играть - в самой игре на компьютере.\n\n"
            + who)


def menu_markup(user_id, sess):
    return keyboards.menu_keyboard(bool(sess.get("subscribed")),
                                   is_admin(user_id))


async def show_menu(bot, chat_id, user_id, state, note=""):
    """Возврат в главное меню (FSM -> MENU)."""
    await set_mode(state, user_id, "MENU")
    sess = session.load_session(user_id)
    text = (note + "\n\n" if note else "") + menu_text(sess)
    await show_screen(bot, chat_id, user_id, text, menu_markup(user_id, sess))


async def get_records():
    """Все партии (игра + база бота). Разбор файлов - в отдельном потоке,
    чтобы не блокировать event loop."""
    records, _bad = await asyncio.to_thread(analytics.load_all_records)
    return records


async def notify_subscribers(bot, records, exclude=None, source=""):
    """Рассылает подписчикам уведомление о новых партиях.

    Returns:
        Сколько сообщений доставлено.
    """
    if not records:
        return 0
    text = (f"🔔 <b>Новые результаты</b>{source}\n"
            + analytics.format_new_records(records))
    sent = 0
    for uid in session.subscribers(exclude=exclude):
        try:
            await send_with_retry(bot, uid, text)
            sent += 1
        except TelegramAPIError as err:
            logger.info("Уведомление %s не доставлено: %s", uid, err)
        await asyncio.sleep(0.05)  # не больше ~20 сообщений в секунду
    logger.info("Уведомление о %d партиях: доставлено %d", len(records), sent)
    return sent


async def guard_callback(callback):
    """Общие проверки для нажатия кнопки.

    * сообщение-экран недоступно (слишком старое) - просим /start;
    * в группе чужой экран нажимать нельзя (проверка from_user.id);
    * слишком частые нажатия (антифлуд) - вежливо отказываем.
    Нажатое сообщение становится экраном пользователя.

    Returns:
        True, если обработку можно продолжать.
    """
    user_id = callback.from_user.id
    msg = callback.message
    if msg is None or not isinstance(msg, Message):
        await safe_answer(callback, "Экран устарел, отправьте /start", True)
        return False
    sess = session.load_session(user_id)
    if (msg.chat.type != "private"
            and sess.get("screen_message_id") != msg.message_id):
        await safe_answer(callback, "Это меню другого пользователя. "
                                    "Откройте своё через /start", True)
        return False
    now = time.time()
    if now - float(sess.get("last_click") or 0) < config.CLICK_COOLDOWN:
        await safe_answer(callback, "Не так быстро 🙂")
        return False
    session.update_session(user_id, last_click=now,
                           screen_message_id=msg.message_id,
                           screen_chat_id=msg.chat.id)
    return True


HELP_TEXT = (
    "ℹ️ <b>Справка</b>\n\n"
    "Бот анализирует результаты игры Pac-Man Hunt: файл рекордов "
    "<code>records.csv</code> и журнал <code>game.log</code>.\n\n"
    "<b>Кнопки:</b>\n"
    "🏆 Топ игроков - таблица лидеров по правилам игры\n"
    "📊 Моя статистика / 🎖 Ачивки - по вашему имени из игры\n"
    "📜 Статистика по логу - что происходило в игре (побеги Пакмана и т.д.)\n"
    "📤 Загрузить результаты - прислать свой records.csv (или game.log)\n"
    "✏️ Указать имя - имя, под которым вы играете\n"
    "🔔 Подписка - уведомления о новых результатах\n\n"
    "<b>Команды:</b> /start, /help, /menu, /cancel, /top, /stats, "
    "/whoami\n<b>Админ:</b> /log [N] - хвост лога бота, /broadcast - "
    "рассылка подписчикам"
)


# ===================================================================
# Команды. /start и /help - без StateFilter и зарегистрированы первыми,
# поэтому работают из любого состояния (выход из «залипшего» режима).
# ===================================================================
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    """Главное меню (новый экран). Сбрасывает любой режим ввода."""
    user_id = message.from_user.id
    logger.info("User %d (@%s): /start", user_id, message.from_user.username)
    await state.clear()
    session.update_session(user_id, screen_message_id=None)
    await show_menu(bot, message.chat.id, user_id, state)


@dp.message(Command("help"))
async def cmd_help(message: Message, bot: Bot):
    """Справка по кнопкам и командам."""
    logger.info("User %d: /help", message.from_user.id)
    await new_screen(bot, message, HELP_TEXT, keyboards.back_keyboard())


@dp.message(Command("menu", "cancel"))
async def cmd_menu(message: Message, state: FSMContext, bot: Bot):
    """Отмена текущего режима и возврат в меню."""
    logger.info("User %d: %s", message.from_user.id, message.text)
    session.update_session(message.from_user.id, screen_message_id=None)
    await show_menu(bot, message.chat.id, message.from_user.id, state)


@dp.message(Command("whoami"))
async def cmd_whoami(message: Message):
    """Показывает id пользователя (нужен для ADMIN_IDS в .env)."""
    uid = message.from_user.id
    role = "администратор" if is_admin(uid) else "пользователь"
    await message.answer(f"Ваш id: <code>{uid}</code> ({role})")


@dp.message(Command("top"))
async def cmd_top(message: Message, bot: Bot):
    """Таблица лидеров командой."""
    records = await get_records()
    sess = session.load_session(message.from_user.id)
    pages = analytics.page_count(len(records))
    await new_screen(bot, message,
                     analytics.format_leaderboard(records, 0, sess.get("name")),
                     keyboards.top_keyboard(0, pages))


@dp.message(Command("stats"))
async def cmd_stats(message: Message, command: CommandObject, bot: Bot):
    """/stats [имя] - статистика по имени (по умолчанию - своё)."""
    sess = session.load_session(message.from_user.id)
    name = (command.args or "").strip() or sess.get("name")
    if not name:
        await new_screen(bot, message, "Сначала укажите имя игрока.",
                         keyboards.need_name_keyboard())
        return
    records = await get_records()
    await new_screen(bot, message,
                     analytics.format_stats(
                         analytics.player_stats(records, name), name),
                     keyboards.back_keyboard())


@dp.message(Command("log"))
async def cmd_log(message: Message, command: CommandObject):
    """/log [N] - последние N строк bot_flight.log (только админ)."""
    uid = message.from_user.id
    if not is_admin(uid):
        logger.warning("User %d: /log без прав", uid)
        await message.answer("⛔ Команда только для администратора.")
        return
    arg = (command.args or "").strip()
    n = min(int(arg), 50) if arg.isdigit() and int(arg) > 0 else 20
    await message.answer(await log_tail_text(n))


@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext, bot: Bot):
    """Начало рассылки (только админ): ждём текст."""
    uid = message.from_user.id
    if not is_admin(uid):
        logger.warning("User %d: /broadcast без прав", uid)
        await message.answer("⛔ Команда только для администратора.")
        return
    await set_mode(state, uid, "BROADCAST")
    await new_screen(bot, message, broadcast_prompt(),
                     keyboards.cancel_keyboard())


async def log_tail_text(n):
    """Хвост лога бота, экранированный и уложенный в лимит 4096."""
    lines = await asyncio.to_thread(analytics.tail_lines, config.BOT_LOG, n)
    body = html.escape("\n".join(lines)) or "(лог пуст)"
    if len(body) > 3800:
        body = "…" + body[-3800:]
    return f"🗒 <b>bot_flight.log</b> (последние {len(lines)})\n<pre>{body}</pre>"


def broadcast_prompt():
    count = len(session.subscribers())
    return (f"📢 <b>Рассылка</b>\nПодписчиков: {count}.\n"
            "Отправьте текст сообщения одним сообщением.")


# ===================================================================
# Кнопки (callback-запросы)
# ===================================================================
@dp.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """«Назад» / «Отмена» - из любого режима в главное меню."""
    if not await guard_callback(callback):
        return
    await show_menu(bot, callback.message.chat.id, callback.from_user.id,
                    state)
    await safe_answer(callback)


@dp.callback_query(F.data.startswith("top:"))
async def cb_top(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Таблица лидеров, страница из callback_data «top:N»."""
    if not await guard_callback(callback):
        return
    page_raw = callback.data.split(":", 1)[1]
    page = int(page_raw) if page_raw.isdigit() else 0
    records = await get_records()
    pages = analytics.page_count(len(records))
    page = min(page, pages - 1)
    uid = callback.from_user.id
    sess = session.load_session(uid)
    await set_mode(state, uid, "MENU")
    await show_screen(bot, callback.message.chat.id, uid,
                      analytics.format_leaderboard(records, page,
                                                   sess.get("name")),
                      keyboards.top_keyboard(page, pages))
    await safe_answer(callback)


async def ask_name(bot, chat_id, user_id, state, after=None):
    """Переход в WAIT_NAME. after - какой экран открыть после ввода."""
    await set_mode(state, user_id, "WAIT_NAME")
    await state.update_data(after=after)  # данные контекста FSM
    await show_screen(bot, chat_id, user_id,
                      "✏️ Напишите имя, под которым вы играете в Pac-Man Hunt "
                      f"(как в records.csv, до {config.NAME_MAX_LEN} символов).",
                      keyboards.cancel_keyboard())


@dp.callback_query(F.data.in_({"stats", "ach"}))
async def cb_stats(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Моя статистика / ачивки. Нет имени - сначала спросим его."""
    if not await guard_callback(callback):
        return
    uid = callback.from_user.id
    chat_id = callback.message.chat.id
    name = session.load_session(uid).get("name")
    if not name:
        await ask_name(bot, chat_id, uid, state, after=callback.data)
    else:
        await set_mode(state, uid, "MENU")
        await show_player_screen(bot, chat_id, uid, name, callback.data)
    await safe_answer(callback)


async def show_player_screen(bot, chat_id, user_id, name, what):
    """Экран статистики (what="stats") или ачивок (what="ach")."""
    records = await get_records()
    if what == "ach":
        text = analytics.format_achievements(records, name)
    else:
        text = analytics.format_stats(analytics.player_stats(records, name),
                                      name)
    await show_screen(bot, chat_id, user_id, text, keyboards.back_keyboard())


@dp.callback_query(F.data == "logstats")
async def cb_logstats(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Сводка по game.log игры."""
    if not await guard_callback(callback):
        return
    summary = await asyncio.to_thread(analytics.parse_log_file, config.GAME_LOG)
    await set_mode(state, callback.from_user.id, "MENU")
    await show_screen(bot, callback.message.chat.id, callback.from_user.id,
                      analytics.format_log_summary(summary),
                      keyboards.back_keyboard())
    await safe_answer(callback)


@dp.callback_query(F.data == "upload")
async def cb_upload(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Переход в UPLOAD: ждём документ."""
    if not await guard_callback(callback):
        return
    uid = callback.from_user.id
    await set_mode(state, uid, "UPLOAD")
    await show_screen(
        bot, callback.message.chat.id, uid,
        "📤 <b>Загрузка результатов</b>\n\nПришлите файлом "
        "<code>records.csv</code> из папки игры (столбцы: "
        f"<code>{','.join(config.CSV_FIELDS)}</code>).\n"
        "Каждая строка будет проверена, новые партии попадут в общую базу.\n"
        "Можно прислать и <code>game.log</code> - бот покажет по нему сводку.\n"
        f"До {config.MAX_UPLOAD_BYTES // 1024} КБ, форматы: "
        f"{', '.join(config.ALLOWED_EXTENSIONS)}.",
        keyboards.cancel_keyboard())
    await safe_answer(callback)


@dp.callback_query(F.data == "name")
async def cb_name(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Кнопка «Указать имя»."""
    if not await guard_callback(callback):
        return
    await ask_name(bot, callback.message.chat.id, callback.from_user.id, state)
    await safe_answer(callback)


@dp.callback_query(F.data == "sub")
async def cb_subscribe(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Включает/выключает подписку на новые результаты."""
    if not await guard_callback(callback):
        return
    uid = callback.from_user.id
    sess = session.load_session(uid)
    subscribed = not sess.get("subscribed")
    session.update_session(uid, subscribed=subscribed)
    logger.info("User %d: подписка %s", uid, "вкл" if subscribed else "выкл")
    note = ("🔔 Подписка включена: пришлю, когда появятся новые результаты."
            if subscribed else "🔕 Подписка выключена.")
    await show_menu(bot, callback.message.chat.id, uid, state, note)
    await safe_answer(callback, "Подписка включена" if subscribed
                      else "Подписка выключена")


@dp.callback_query(F.data.startswith("admin:"))
async def cb_admin(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Кнопки администратора. Права проверяются здесь, а не только тем,
    что кнопки не показаны: callback_data можно подделать."""
    if not await guard_callback(callback):
        return
    uid = callback.from_user.id
    if not is_admin(uid):
        logger.warning("User %d: попытка админ-действия %s", uid,
                       callback.data)
        await safe_answer(callback, "⛔ Только для администратора", True)
        return
    chat_id = callback.message.chat.id
    if callback.data == "admin:log":
        await set_mode(state, uid, "MENU")
        await show_screen(bot, chat_id, uid, await log_tail_text(20),
                          keyboards.back_keyboard())
    else:
        await set_mode(state, uid, "BROADCAST")
        await show_screen(bot, chat_id, uid, broadcast_prompt(),
                          keyboards.cancel_keyboard())
    await safe_answer(callback)


@dp.callback_query()
async def cb_unknown(callback: CallbackQuery):
    """Неизвестная или устаревшая кнопка."""
    logger.info("User %d: неизвестный callback %r", callback.from_user.id,
                callback.data)
    await safe_answer(callback, "Кнопка устарела, отправьте /start", True)


# ===================================================================
# Сценарные хендлеры: срабатывают только в своём состоянии FSM
# ===================================================================
def check_document(doc):
    """Проверка файла ДО скачивания: размер, расширение, MIME-тип.

    Returns:
        Текст причины отказа или None, если файл подходит.
    """
    name = (doc.file_name or "").lower()
    if doc.file_size and doc.file_size > config.MAX_UPLOAD_BYTES:
        return (f"файл больше {config.MAX_UPLOAD_BYTES // 1024} КБ - "
                "это точно не records.csv")
    if not name.endswith(config.ALLOWED_EXTENSIONS):
        return ("нужен файл " + ", ".join(config.ALLOWED_EXTENSIONS))
    if doc.mime_type and doc.mime_type not in config.ALLOWED_MIME:
        return f"тип файла {doc.mime_type} не подходит"
    return None


@dp.message(StateFilter(BotState.UPLOAD), F.document)
async def handle_upload(message: Message, state: FSMContext, bot: Bot):
    """Приём файла: проверка -> скачивание в память -> разбор -> база."""
    uid = message.from_user.id
    doc = message.document
    chat_id = message.chat.id
    logger.info("User %d: загрузка %s (%s байт, %s)", uid, doc.file_name,
                doc.file_size, doc.mime_type)
    problem = check_document(doc)
    if problem:
        logger.info("User %d: файл отклонён - %s", uid, problem)
        await show_screen(bot, chat_id, uid,
                          f"❌ Файл не принят: {html.escape(problem)}.\n"
                          "Пришлите другой файл или нажмите «Отмена».",
                          keyboards.cancel_keyboard())
        return

    buffer = io.BytesIO()
    await bot.download(doc, destination=buffer)
    try:
        text = buffer.getvalue().decode("utf-8-sig")  # -sig убирает BOM
    except UnicodeDecodeError:
        await show_screen(bot, chat_id, uid,
                          "❌ Файл не в кодировке UTF-8. Пришлите файл, "
                          "который сохранила игра.",
                          keyboards.cancel_keyboard())
        return

    sess = session.update_session(
        uid, uploads=int(session.load_session(uid).get("uploads", 0)) + 1)
    if (doc.file_name or "").lower().endswith(".log"):
        summary = await asyncio.to_thread(analytics.parse_log_text, text)
        logger.info("User %d: разобран лог, партий %d", uid, summary["games"])
        await show_menu(bot, chat_id, uid, state,
                        analytics.format_log_summary(summary,
                                                     doc.file_name or "log"))
        return

    records, errors = await asyncio.to_thread(analytics.parse_scores_text,
                                              text)
    game_records, _ = await asyncio.to_thread(analytics.parse_scores_file,
                                              config.GAME_RECORDS)
    added, duplicates = await asyncio.to_thread(
        analytics.append_records, records, None, game_records)
    logger.info("User %d: добавлено %d, дублей %d, отклонено %d", uid,
                len(added), duplicates, len(errors))

    lines = [f"📥 <b>Файл {html.escape(doc.file_name or '')} разобран</b>",
             f"Добавлено новых партий: <b>{len(added)}</b>",
             f"Уже были в базе: {duplicates}",
             f"Отклонено строк: <b>{len(errors)}</b>"]
    if errors:
        shown = "\n".join(html.escape(e) for e in errors[:10])
        more = f"\n…и ещё {len(errors) - 10}" if len(errors) > 10 else ""
        lines.append(f"<pre>{shown}{more}</pre>")
    await show_menu(bot, chat_id, uid, state, "\n".join(lines))
    if added:
        who = sess.get("name") or message.from_user.first_name or "игрок"
        await notify_subscribers(bot, added, exclude=uid,
                                 source=f" (загрузил {html.escape(who)})")


@dp.message(StateFilter(BotState.UPLOAD))
async def handle_upload_wrong(message: Message, bot: Bot):
    """В режиме загрузки пришёл не файл."""
    await show_screen(bot, message.chat.id, message.from_user.id,
                      "📎 Жду именно файл (records.csv) - прикрепите его "
                      "как документ, или нажмите «Отмена».",
                      keyboards.cancel_keyboard())


@dp.message(StateFilter(BotState.WAIT_NAME), F.text)
async def handle_name(message: Message, state: FSMContext, bot: Bot):
    """Сохраняет имя игрока в сессию."""
    uid = message.from_user.id
    name = message.text.strip()
    if (not name or len(name) > config.NAME_MAX_LEN
            or not name.isprintable() or name.startswith("/")):
        await show_screen(bot, message.chat.id, uid,
                          f"Имя должно быть от 1 до {config.NAME_MAX_LEN} "
                          "символов. Попробуйте ещё раз.",
                          keyboards.cancel_keyboard())
        return
    data = await state.get_data()
    session.update_session(uid, name=name)
    logger.info("User %d: имя игрока «%s»", uid, name)
    after = data.get("after")
    if after in ("stats", "ach"):
        await set_mode(state, uid, "MENU")
        await show_player_screen(bot, message.chat.id, uid, name, after)
    else:
        await show_menu(bot, message.chat.id, uid, state,
                        f"✅ Имя сохранено: <b>{html.escape(name)}</b>")


@dp.message(StateFilter(BotState.WAIT_NAME))
async def handle_name_wrong(message: Message, bot: Bot):
    """В режиме ввода имени пришёл не текст (стикер, фото...)."""
    await show_screen(bot, message.chat.id, message.from_user.id,
                      "Напишите имя текстом или нажмите «Отмена».",
                      keyboards.cancel_keyboard())


@dp.message(StateFilter(BotState.BROADCAST), F.text)
async def handle_broadcast(message: Message, state: FSMContext, bot: Bot):
    """Рассылка текста всем подписчикам (повторная проверка прав)."""
    uid = message.from_user.id
    if not is_admin(uid):
        await show_menu(bot, message.chat.id, uid, state)
        return
    text = "📢 " + html.escape(message.text)
    sent = failed = 0
    for target in session.subscribers():
        try:
            await send_with_retry(bot, target, text)
            sent += 1
        except TelegramAPIError as err:
            failed += 1
            logger.info("Рассылка %s не доставлена: %s", target, err)
        await asyncio.sleep(0.05)
    logger.info("User %d: рассылка - доставлено %d, ошибок %d", uid, sent,
                failed)
    # новый экран под сообщением админа, а не где-то выше по чату
    session.update_session(uid, screen_message_id=None)
    await show_menu(bot, message.chat.id, uid, state,
                    f"📢 Рассылка отправлена: {sent}, не доставлено: {failed}")


@dp.message(F.document)
async def handle_stray_document(message: Message, bot: Bot):
    """Файл прислан вне режима загрузки - StateFilter его не пропустил."""
    await message.answer("Чтобы загрузить результаты, нажмите "
                         "«📤 Загрузить результаты» в меню (/start).")


@dp.message()
async def handle_other(message: Message):
    """Любое другое сообщение в режиме меню."""
    if message.from_user is None:
        return  # посты каналов и служебные сообщения
    await message.answer("Я управляюсь кнопками 🙂 Откройте меню: /start")


# ---------- Глобальный обработчик ошибок ----------
@dp.errors()
async def on_error(event: ErrorEvent, bot: Bot):
    """Страхует все хендлеры: traceback в лог, пользователю - понятный
    ответ вместо молчания."""
    logger.error("Ошибка апдейта: %s", event.exception,
                 exc_info=event.exception)
    update = event.update
    chat_id = None
    if update.message:
        chat_id = update.message.chat.id
    elif update.callback_query and update.callback_query.message:
        chat_id = update.callback_query.message.chat.id
        await safe_answer(update.callback_query)
    if chat_id:
        try:
            await bot.send_message(chat_id,
                                   "⚠️ Временный сбой. Попробуйте /start")
        except TelegramAPIError:
            pass
    return True


# ---------- Слежение за records.csv игры ----------
async def check_game_updates(bot, known):
    """Ищет в records.csv игры новые партии и уведомляет подписчиков.

    Args:
        known: множество ключей уже известных партий (меняется на месте).

    Returns:
        Список новых записей.
    """
    records, _ = await asyncio.to_thread(analytics.parse_scores_file,
                                         config.GAME_RECORDS)
    fresh = [r for r in records if r.key not in known]
    known.update(r.key for r in fresh)
    if fresh:
        logger.info("В records.csv игры новых партий: %d", len(fresh))
        await notify_subscribers(bot, fresh, source=" (из игры)")
    return fresh


async def watch_game_records(bot):
    """Фоновая задача: раз в WATCH_INTERVAL секунд проверяет, не сыграли
    ли новую партию (по времени изменения records.csv)."""
    records, _ = await asyncio.to_thread(analytics.parse_scores_file,
                                         config.GAME_RECORDS)
    known = {r.key for r in records}
    last_mtime = None
    while True:
        await asyncio.sleep(config.WATCH_INTERVAL)
        try:
            path = config.GAME_RECORDS
            mtime = path.stat().st_mtime if path.exists() else None
            if mtime != last_mtime:
                last_mtime = mtime
                await check_game_updates(bot, known)
        except Exception as err:  # фоновая задача не должна умирать
            logger.warning("Ошибка слежения за records.csv: %s", err)


_background = []


@dp.startup()
async def on_startup(bot: Bot):
    me = await bot.get_me()
    logger.info("Бот @%s запущен. Админов: %d. Данные игры: %s",
                me.username, len(config.ADMIN_IDS), config.REPO_ROOT)
    _background.append(asyncio.create_task(watch_game_records(bot)))


@dp.shutdown()
async def on_shutdown():
    for task in _background:
        task.cancel()
    logger.info("Бот остановлен")


async def main():
    """Точка входа: лог, бот, long polling."""
    config.SESSION_DIR.mkdir(parents=True, exist_ok=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    setup_logging()
    bot = create_bot()
    logger.info("Запуск поллинга")
    try:
        await dp.start_polling(bot)
    except TelegramUnauthorizedError:
        logger.error("Telegram отклонил токен (Unauthorized)")
        raise SystemExit("Telegram не принял BOT_TOKEN: токен неверный или "
                         "отозван. Возьмите актуальный у @BotFather "
                         "(/mybots -> API Token) и обновите py_bot/.env.")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
