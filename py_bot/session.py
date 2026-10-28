"""Stateless-сессии пользователей в JSON-файлах.

Бот не держит данные пользователей в глобальных переменных. Всё, что
бот знает о человеке, лежит в файле sessions/<user_id>.json и читается
заново при каждом апдейте. Это даёт:
    * изоляцию: у каждого user_id свой файл, данные не пересекаются;
    * сохранность: после перезапуска бота имя и подписка не теряются;
    * простую рассылку: список подписчиков = все файлы с subscribed=True.

FSM (aiogram) отвечает на вопрос «что бот сейчас ждёт от пользователя»,
а сессия - «кто этот пользователь и что о нём известно».
"""

import json
import logging
import os
from datetime import datetime

import config

logger = logging.getLogger("py_bot.session")

# Ключи сессии и значения по умолчанию
DEFAULTS = {
    "state": "MENU",             # копия состояния FSM (для наглядности/логов)
    "name": None,                # имя игрока из records.csv
    "subscribed": False,         # подписка на новые результаты
    "screen_message_id": None,   # id сообщения-экрана (антифлуд)
    "screen_chat_id": None,      # чат, где живёт сообщение-экран
    "uploads": 0,                # сколько файлов пользователь загрузил
    "last_click": 0.0,           # время последнего нажатия (антифлуд)
}


def _path(user_id):
    """Путь к файлу сессии пользователя."""
    return config.SESSION_DIR / f"{int(user_id)}.json"


def create_new_session(user_id):
    """Новая сессия со значениями по умолчанию.

    Args:
        user_id: id пользователя Telegram.

    Returns:
        Словарь сессии.
    """
    data = dict(DEFAULTS)
    data["user_id"] = int(user_id)
    data["created"] = datetime.now().strftime(config.DATE_FORMAT)
    return data


def load_session(user_id):
    """Читает сессию из JSON. Нет файла или он битый - новая сессия.

    Недостающие ключи (например, после обновления бота) дополняются
    значениями по умолчанию, лишние - сохраняются как есть.
    """
    path = _path(user_id)
    if not path.exists():
        return create_new_session(user_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("корень JSON - не объект")
    except (OSError, ValueError) as err:
        # json.JSONDecodeError - наследник ValueError
        logger.warning("Сессия %s повреждена (%s), создаю новую",
                       user_id, err)
        return create_new_session(user_id)
    session = create_new_session(user_id)
    session.update(data)
    return session


def save_session(user_id, data):
    """Сохраняет сессию в JSON.

    Запись идёт во временный файл, который затем подменяет старый
    (os.replace). Если бот упадёт посреди записи, старая сессия
    останется целой, а не превратится в обрывок JSON.
    """
    config.SESSION_DIR.mkdir(parents=True, exist_ok=True)
    path = _path(user_id)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def update_session(user_id, **changes):
    """Загружает сессию, меняет указанные поля и сразу сохраняет.

    Returns:
        Обновлённый словарь сессии.
    """
    data = load_session(user_id)
    data.update(changes)
    save_session(user_id, data)
    return data


def all_sessions():
    """Все сессии: список пар (user_id, session). Нужен для рассылок."""
    result = []
    if not config.SESSION_DIR.exists():
        return result
    for path in sorted(config.SESSION_DIR.glob("*.json")):
        if not path.stem.isdigit():
            continue
        user_id = int(path.stem)
        result.append((user_id, load_session(user_id)))
    return result


def subscribers(exclude=None):
    """id пользователей с включённой подпиской (кроме exclude)."""
    return [uid for uid, s in all_sessions()
            if s.get("subscribed") and uid != exclude]


def clear_session(user_id):
    """Удаляет файл сессии (сброс пользователя)."""
    path = _path(user_id)
    if path.exists():
        path.unlink()
