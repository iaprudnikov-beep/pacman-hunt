"""Логирование событий игры в файл («чёрный ящик»).

Каждое событие записывается отдельной строкой с меткой времени:
    2026-10-28 14:05:12 | INFO | Старт новой партии
По логу после игры можно восстановить, что происходило и в какой момент.
"""

import logging
import sys

from pacman_hunt.constants import LOG_DATEFMT, LOG_FILE, LOG_FORMAT

# Общий именованный логгер игры: все модули пишут через него
logger = logging.getLogger("pacman_hunt")


def setup_logging(path=LOG_FILE, level=logging.INFO):
    """Настраивает запись лога в файл.

    Файл открывается в режиме "a" (дописывание), поэтому записи прошлых
    запусков сохраняются. Если файл открыть нельзя (нет прав, диск только
    для чтения), лог выводится в консоль - игра при этом не падает.

    Args:
        path: путь к файлу лога (pathlib.Path).
        level: минимальный уровень сообщений, которые попадут в лог.

    Returns:
        True, если лог пишется в файл, False - если в консоль.
    """
    logger.setLevel(level)
    logger.propagate = False  # не дублировать записи в корневой логгер
    # при повторном вызове убираем старые обработчики, чтобы строки
    # не записывались по два раза
    for old in list(logger.handlers):
        logger.removeHandler(old)
        old.close()
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)
    try:
        handler = logging.FileHandler(path, mode="a", encoding="utf-8")
    except OSError as err:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.warning("Не удалось открыть лог-файл %s: %s. "
                       "Лог идёт в консоль", path, err)
        return False
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return True


def log_event(message, level=logging.INFO):
    """Записывает одно событие в лог.

    Args:
        message: текст события.
        level: уровень важности (logging.INFO, logging.WARNING, ...).
    """
    logger.log(level, message)
