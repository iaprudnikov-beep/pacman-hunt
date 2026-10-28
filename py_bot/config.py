"""Конфигурация Telegram-бота Pac-Man Hunt (ЛР 3).

Здесь собраны все настройки бота, чтобы остальные модули не зависели
от того, где лежат файлы и откуда берётся токен:
    * токен и список администраторов (из py_bot/.env или окружения);
    * пути к данным, которые выгружает игра (records.csv, game.log);
    * пути к рабочим файлам бота (сессии, общая база, лог бота);
    * игровые параметры, нужные для проверки результатов.

Формат py_bot/.env:
    BOT_TOKEN=123456789:AA...      # токен от @BotFather (обязательно)
    ADMIN_IDS=111111111,222222222  # id администраторов (необязательно)

Файл .env хранит секрет и добавлен в .gitignore - в репозиторий
он не попадает.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------- Папки ----------
# Все пути абсолютные и считаются от этого файла, поэтому бот
# находит свои файлы, из какой бы папки его ни запустили.
BOT_DIR = Path(__file__).resolve().parent      # папка py_bot/
REPO_ROOT = BOT_DIR.parent                     # корень проекта pacman-hunt/

# ---------- Данные игры (их пишет Pygame-приложение из ЛР 2) ----------
GAME_RECORDS = REPO_ROOT / "records.csv"       # таблица рекордов игры
GAME_LOG = REPO_ROOT / "game.log"              # журнал событий игры

# ---------- Рабочие файлы бота ----------
SESSION_DIR = BOT_DIR / "sessions"             # JSON-сессии: <user_id>.json
DATA_DIR = BOT_DIR / "data"                    # данные, присланные в чат
SCORES_DB = DATA_DIR / "scores.csv"            # общая база загруженных игр
BOT_LOG = BOT_DIR / "bot_flight.log"           # лог событий самого бота

# ---------- Параметры игры ----------
# Значения продублированы из pacman_hunt/constants.py, а не импортированы:
# constants.py импортирует pygame, а боту pygame не нужен.
CSV_FIELDS = ["Дата", "Имя", "Результат", "Время", "Съедено", "Всего"]
RESULT_WIN = "Победа"          # призрак поймал Пакмана
RESULT_LOSE = "Поражение"      # Пакман съел всю еду
VALID_RESULTS = (RESULT_WIN, RESULT_LOSE)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"   # формат столбца «Дата» в records.csv
NAME_MAX_LEN = 16              # максимальная длина имени в игре
DEFAULT_FOOD = 159             # еды на стандартном уровне
MAX_FOOD = 22 * 15             # еды не может быть больше клеток поля
PAC_DELAY = 0.20               # сек между шагами Пакмана

# ---------- Границы проверки (верификация результатов) ----------
MAX_GAME_TIME = 3600.0         # партия дольше часа - неправдоподобно
# Пакман съедает не больше одной еды за шаг. Берём половину задержки
# с запасом (уровень может ускорить Пакмана), и время партии должно быть
# не меньше «съедено x MIN_SEC_PER_FOOD».
MIN_SEC_PER_FOOD = PAC_DELAY / 2

# ---------- Ограничения бота ----------
MAX_UPLOAD_BYTES = 1024 * 1024       # принимаем файлы до 1 МБ
ALLOWED_EXTENSIONS = (".csv", ".txt", ".log")
ALLOWED_MIME = (
    "text/csv", "text/plain", "text/comma-separated-values",
    "application/csv", "application/vnd.ms-excel",
    "application/octet-stream", "text/x-log",
)
TOP_PAGE_SIZE = 10             # строк таблицы лидеров на одной странице
CLICK_COOLDOWN = 0.7           # сек между нажатиями (антифлуд)
WATCH_INTERVAL = 10            # сек между проверками records.csv игры

# ---------- Токен и администраторы ----------
# load_dotenv не перезаписывает уже заданные переменные окружения,
# поэтому BOT_TOKEN из окружения важнее, чем из файла.
load_dotenv(BOT_DIR / ".env")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()


def parse_admin_ids(raw):
    """Разбирает строку «111,222;333» в список id администраторов."""
    ids = []
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            ids.append(int(chunk))
    return ids


ADMIN_IDS = parse_admin_ids(os.environ.get("ADMIN_IDS", ""))
