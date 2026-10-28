"""Работа с файлами: загрузка уровня из JSON и таблица рекордов в CSV.

Все операции с файлами собраны в этом модуле, чтобы остальной код игры
не знал, как и где хранятся данные:
    load_level   - читает и проверяет файл уровня, при ошибке - уровень
                   по умолчанию;
    save_result  - дописывает результат партии в CSV (создаёт заголовок
                   при первом запуске);
    load_records - читает таблицу рекордов;
    top_records  - выбирает лучшие результаты.
Файлы всегда открываются через with и с encoding="utf-8" (кириллица).
"""

import csv
import json
import logging
from datetime import datetime

from pacman_hunt.constants import (
    COLS, CSV_FIELDS, FLEE_DIST, FLEE_EXIT, GHOST_START, LEVEL_FILE, MAZE_STR,
    PAC_DELAY, PAC_START, RECORDS_FILE, RESULT_WIN, ROWS, TOP_N,
)
from pacman_hunt.logger import log_event

DEFAULT_LEVEL_NAME = "Уровень по умолчанию"


class LevelError(ValueError):
    """Файл уровня прочитан, но его содержимое не подходит для игры."""


# ---------- Уровень (JSON) ----------
def default_level():
    """Встроенный уровень из constants.py (запасной вариант).

    Returns:
        Словарь уровня того же вида, что возвращает validate_level.
    """
    return {
        "name": DEFAULT_LEVEL_NAME,
        "maze": [[int(c) for c in row] for row in MAZE_STR],
        "ghost_start": GHOST_START,
        "pac_start": PAC_START,
        "pac_delay": PAC_DELAY,
        "flee_dist": FLEE_DIST,
        "flee_exit": FLEE_EXIT,
        "is_default": True,
    }


def _is_number(value):
    """True для int/float (bool не считается числом)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_cell(maze, value, what):
    """Проверяет стартовую клетку: [x, y] внутри поля и не стена.

    Returns:
        Клетка в виде кортежа (x, y).
    """
    if (not isinstance(value, list) or len(value) != 2
            or not all(isinstance(v, int) and not isinstance(v, bool)
                       for v in value)):
        raise LevelError(f"{what}: нужна пара целых чисел [x, y], "
                         f"а не {value!r}")
    x, y = value
    if not (0 <= x < COLS and 0 <= y < ROWS):
        raise LevelError(f"{what}: клетка {value} вне поля {COLS}x{ROWS}")
    if maze[y][x] != 0:
        raise LevelError(f"{what}: клетка {value} - это стена")
    return (x, y)


def _reachable(maze, start, target):
    """Есть ли проход от start до target (обход в ширину по сетке)."""
    seen, stack = {start}, [start]
    while stack:
        x, y = stack.pop()
        if (x, y) == target:
            return True
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (0 <= nx < COLS and 0 <= ny < ROWS and maze[ny][nx] == 0
                    and (nx, ny) not in seen):
                seen.add((nx, ny))
                stack.append((nx, ny))
    return False


def validate_level(data):
    """Проверяет структуру уровня, прочитанного из JSON.

    Правила:
        * корень - объект (словарь) с ключами "maze", "ghost", "pacman";
        * "maze" - прямоугольная матрица ROWS x COLS из чисел 0 и 1
          (размер фиксирован, потому что от него зависит размер окна);
        * стартовые клетки призрака и Пакмана внутри поля, не стены,
          не совпадают, и между ними есть проход;
        * в лабиринте есть хотя бы одна клетка для еды;
        * настройки Пакмана (delay, flee_dist, flee_exit) необязательны,
          но если заданы - это положительные числа и flee_exit >= flee_dist.

    Args:
        data: объект, который вернул json.load.

    Returns:
        Словарь уровня с проверенными и приведёнными к нужным типам данными.

    Raises:
        LevelError: если что-то из правил нарушено (с описанием причины).
    """
    if not isinstance(data, dict):
        raise LevelError("корень файла должен быть объектом {...}")
    for key in ("maze", "ghost", "pacman"):
        if key not in data:
            raise LevelError(f"нет обязательного ключа \"{key}\"")

    maze = data["maze"]
    if not isinstance(maze, list) or len(maze) != ROWS:
        raise LevelError(f"\"maze\" должен содержать {ROWS} рядов")
    for y, row in enumerate(maze):
        if not isinstance(row, list) or len(row) != COLS:
            raise LevelError(f"в ряду {y} должно быть {COLS} клеток "
                             f"(ширина лабиринта)")
        for x, cell in enumerate(row):
            if isinstance(cell, bool) or cell not in (0, 1):
                raise LevelError(f"клетка ({x}, {y}) = {cell!r}, "
                                 f"а нужно 0 или 1")
    maze = [[int(c) for c in row] for row in maze]

    ghost, pacman = data["ghost"], data["pacman"]
    if not isinstance(ghost, dict) or not isinstance(pacman, dict):
        raise LevelError("\"ghost\" и \"pacman\" должны быть объектами {...}")
    ghost_start = _check_cell(maze, ghost.get("start"), "ghost.start")
    pac_start = _check_cell(maze, pacman.get("start"), "pacman.start")
    if ghost_start == pac_start:
        raise LevelError("призрак и Пакман стоят в одной клетке")
    if not _reachable(maze, ghost_start, pac_start):
        raise LevelError("призрак не может дойти до Пакмана - нет прохода")
    free = sum(row.count(0) for row in maze)
    if free <= 2:  # кроме двух стартовых клеток нужна хотя бы одна еда
        raise LevelError("в лабиринте нет места для еды")

    # необязательные настройки: если ключа нет - берём значение по умолчанию
    settings = {}
    for key, default in (("delay", PAC_DELAY), ("flee_dist", FLEE_DIST),
                         ("flee_exit", FLEE_EXIT)):
        value = pacman.get(key, default)
        if not _is_number(value) or value <= 0:
            raise LevelError(f"pacman.{key} должен быть положительным числом")
        settings[key] = value
    if settings["flee_exit"] < settings["flee_dist"]:
        raise LevelError("pacman.flee_exit не может быть меньше flee_dist")

    name = data.get("name", "Без названия")
    return {
        "name": str(name),
        "maze": maze,
        "ghost_start": ghost_start,
        "pac_start": pac_start,
        "pac_delay": float(settings["delay"]),
        "flee_dist": settings["flee_dist"],
        "flee_exit": settings["flee_exit"],
        "is_default": False,
    }


def load_level(path=LEVEL_FILE):
    """Загружает уровень из JSON-файла.

    Порядок: проверка существования -> чтение (with) -> разбор JSON ->
    валидация. Любая ошибка записывается в лог как WARNING, и игра
    получает уровень по умолчанию, то есть не падает.

    Args:
        path: путь к файлу уровня (pathlib.Path).

    Returns:
        Словарь уровня; ключ "is_default" показывает, взят ли запасной.
    """
    try:
        if not path.exists():
            raise FileNotFoundError(f"файл {path} не найден")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        level = validate_level(data)
    except FileNotFoundError as err:
        log_event(f"Уровень не загружен: {err}. Используется уровень "
                  f"по умолчанию", logging.WARNING)
    except json.JSONDecodeError as err:
        # повреждённый JSON: лишняя запятая, незакрытая скобка и т. п.
        log_event(f"Уровень не загружен: ошибка JSON в {path.name}, строка "
                  f"{err.lineno}, столбец {err.colno}: {err.msg}. "
                  f"Используется уровень по умолчанию", logging.WARNING)
    except LevelError as err:
        log_event(f"Уровень не загружен: неверная структура {path.name}: "
                  f"{err}. Используется уровень по умолчанию",
                  logging.WARNING)
    except (OSError, UnicodeDecodeError) as err:
        # нет прав на чтение, это папка, файл не в UTF-8 и т. п.
        log_event(f"Уровень не загружен: не удалось прочитать {path}: {err}. "
                  f"Используется уровень по умолчанию", logging.WARNING)
    else:
        # сюда попадаем, только если исключений не было
        log_event(f"Уровень «{level['name']}» загружен из {path.name}")
        return level
    return default_level()


# ---------- Таблица рекордов (CSV) ----------
def save_result(name, time_sec, eaten, total, result, path=RECORDS_FILE):
    """Дописывает результат партии в конец CSV-файла.

    Файл открывается в режиме "a", поэтому старые результаты не стираются.
    Если файла ещё нет (или он пустой) - сначала пишется строка заголовка.

    Args:
        name: имя игрока.
        time_sec: длительность партии в секундах.
        eaten: сколько еды съел Пакман.
        total: сколько еды было всего.
        result: RESULT_WIN или RESULT_LOSE.
        path: путь к CSV-файлу.

    Returns:
        True, если запись удалась, иначе False.
    """
    row = {
        "Дата": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Имя": name,
        "Результат": result,
        "Время": round(float(time_sec), 1),
        "Съедено": eaten,
        "Всего": total,
    }
    saved = False
    try:
        need_header = not path.exists() or path.stat().st_size == 0
        # newline="" обязателен для csv, иначе в Windows появятся пустые строки
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if need_header:
                writer.writeheader()  # первый запуск: создаём заголовок
            writer.writerow(row)
    except OSError as err:
        log_event(f"Не удалось записать результат в {path}: {err}",
                  logging.ERROR)
    else:
        saved = True
        log_event(f"Результат сохранён в {path.name}: {name}, {result}, "
                  f"{row['Время']} с, съедено {eaten}/{total}")
    finally:
        # выполняется всегда - и после успеха, и после ошибки
        log_event(f"Сохранение результата завершено (успех: {saved})")
    return saved


def load_records(path=RECORDS_FILE):
    """Читает таблицу рекордов через csv.DictReader.

    Испорченные строки (не число во «Времени» и т. п.) пропускаются,
    а при ошибке чтения файла возвращается пустой список.

    Returns:
        Список словарей с ключами из CSV_FIELDS; «Время» - float,
        «Съедено» и «Всего» - int.
    """
    if not path.exists():
        return []
    records = []
    try:
        with open(path, "r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    row["Время"] = float(row["Время"])
                    row["Съедено"] = int(row["Съедено"])
                    row["Всего"] = int(row["Всего"])
                except (KeyError, TypeError, ValueError):
                    continue  # строка повреждена - пропускаем её
                records.append(row)
    except (OSError, UnicodeDecodeError, csv.Error) as err:
        log_event(f"Не удалось прочитать таблицу рекордов {path}: {err}",
                  logging.WARNING)
        return []
    return records


def top_records(records, n=TOP_N):
    """Лучшие результаты для экрана рекордов.

    Сначала идут победы: выше тот, кто отдал Пакману меньше еды,
    а при равенстве - кто поймал быстрее. Потом поражения: выше тот,
    кто дольше продержался.

    Args:
        records: список из load_records.
        n: сколько записей вернуть.
    """
    def key(r):
        if r["Результат"] == RESULT_WIN:
            return (0, r["Съедено"], r["Время"])
        return (1, 0, -r["Время"])
    return sorted(records, key=key)[:n]
