"""Инлайн-клавиатуры бота.

Кнопки привязаны к сообщению-экрану. Нажатие присылает боту
callback-запрос с коротким кодом действия (callback_data до 64 байт):
"top:0", "stats", "upload"... Никаких данных в кнопках не храним -
всё, что нужно, лежит в JSON-сессии пользователя.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def menu_keyboard(subscribed=False, is_admin=False):
    """Главное меню.

    Args:
        subscribed: включена ли подписка (меняется подпись кнопки).
        is_admin: показывать ли кнопки администратора.
    """
    rows = [
        [_btn("🏆 Топ игроков", "top:0")],
        [_btn("📊 Моя статистика", "stats"), _btn("🎖 Ачивки", "ach")],
        [_btn("📜 Статистика по логу", "logstats")],
        [_btn("📤 Загрузить результаты", "upload"),
         _btn("✏️ Указать имя", "name")],
        [_btn("🔔 Подписка: вкл" if subscribed else "🔕 Подписка: выкл",
              "sub")],
    ]
    if is_admin:
        rows.append([_btn("🗒 Лог бота", "admin:log"),
                     _btn("📢 Рассылка", "admin:broadcast")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_keyboard():
    """Одна кнопка «Назад» в главное меню."""
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ Назад", "menu")]])


def cancel_keyboard():
    """Кнопка «Отмена» для экранов ввода (файл, имя, рассылка)."""
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("✖️ Отмена", "menu")]])


def top_keyboard(page, pages):
    """Таблица лидеров: листание страниц + обновить + назад."""
    nav = []
    if page > 0:
        nav.append(_btn("◀️", f"top:{page - 1}"))
    nav.append(_btn("🔄 Обновить", f"top:{page}"))
    if page < pages - 1:
        nav.append(_btn("▶️", f"top:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[nav,
                                                 [_btn("⬅️ Назад", "menu")]])


def need_name_keyboard():
    """Экран «сначала укажите имя»."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✏️ Указать имя", "name")],
        [_btn("⬅️ Назад", "menu")],
    ])
