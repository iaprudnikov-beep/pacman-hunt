"""Аналитика данных игры Pac-Man Hunt: разбор, проверка, рейтинги.

Бот не играет сам - он работает с файлами, которые выгружает игра:
    records.csv - строка на каждую партию:
        Дата,Имя,Результат,Время,Съедено,Всего
        2026-10-28 14:05:12,Ваня,Победа,23.4,17,159
    game.log    - журнал событий: «время | уровень | сообщение».

Что умеет модуль:
    parse_scores_text  - разбор CSV с проверкой каждой строки;
    verify_record      - проверка одной партии на правдоподобие;
    append_records     - дописывание новых партий в общую базу без дублей;
    leaderboard        - таблица лидеров (те же правила, что в игре);
    player_stats       - личная статистика игрока;
    achievements       - ачивки игрока;
    parse_log_text     - сводка по журналу игры (сколько раз Пакман
                         убегал, сколько побед и т. д.).
Функции format_* превращают результат в HTML-текст для Telegram.
Модуль не зависит от aiogram, поэтому его легко тестировать.
"""

import csv
import html
import io
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

import config

WIN = config.RESULT_WIN
LOSE = config.RESULT_LOSE


# ---------- Запись о партии ----------
@dataclass(frozen=True)
class Record:
    """Одна партия из records.csv."""

    date: str        # «2026-10-28 14:05:12»
    name: str        # имя игрока
    result: str      # «Победа» или «Поражение»
    time_sec: float  # длительность партии, с
    eaten: int       # сколько еды съел Пакман
    total: int       # сколько еды было на уровне

    @property
    def key(self):
        """Ключ для поиска дублей: одна и та же партия = все поля равны."""
        return (self.date, self.name, self.result,
                round(self.time_sec, 1), self.eaten, self.total)

    @property
    def eaten_pct(self):
        """Доля съеденной еды в процентах."""
        return 100.0 * self.eaten / self.total if self.total else 0.0

    @property
    def is_win(self):
        return self.result == WIN

    def as_row(self):
        """Строка для csv.DictWriter (порядок столбцов как в игре)."""
        return {"Дата": self.date, "Имя": self.name,
                "Результат": self.result, "Время": round(self.time_sec, 1),
                "Съедено": self.eaten, "Всего": self.total}


def same_name(a, b):
    """Сравнение имён без учёта регистра и пробелов по краям."""
    return (a or "").strip().casefold() == (b or "").strip().casefold()


# ---------- Проверка (верификация) ----------
def verify_record(rec, now=None):
    """Проверяет партию на непротиворечивость.

    Правила:
        * дата в формате игры и не из будущего;
        * имя не пустое и не длиннее, чем позволяет игра;
        * результат - только «Победа» или «Поражение»;
        * время > 0, конечное и не больше MAX_GAME_TIME;
        * 1 <= всего еды <= клеток поля, 0 <= съедено <= всего;
        * поражение = Пакман съел ВСЮ еду; победа = съел не всё;
        * Пакман ест не больше одной еды за шаг, поэтому время партии
          не может быть меньше «съедено x MIN_SEC_PER_FOOD».

    Returns:
        Список текстов проблем; пустой список - запись в порядке.
    """
    issues = []
    now = now or datetime.now()
    try:
        played = datetime.strptime(rec.date, config.DATE_FORMAT)
        if played > now + timedelta(days=1):
            issues.append("дата из будущего")
    except ValueError:
        issues.append("дата не в формате ГГГГ-ММ-ДД ЧЧ:ММ:СС")
    if not rec.name:
        issues.append("пустое имя игрока")
    elif len(rec.name) > config.NAME_MAX_LEN:
        issues.append(f"имя длиннее {config.NAME_MAX_LEN} символов")
    elif any(not ch.isprintable() for ch in rec.name):
        issues.append("в имени служебные символы")
    if rec.result not in config.VALID_RESULTS:
        issues.append(f"недопустимый результат «{rec.result}»")
    if not math.isfinite(rec.time_sec) or rec.time_sec <= 0:
        issues.append("время партии должно быть больше 0")
    elif rec.time_sec > config.MAX_GAME_TIME:
        issues.append("неправдоподобно долгая партия")
    if not 1 <= rec.total <= config.MAX_FOOD:
        issues.append(f"всего еды должно быть от 1 до {config.MAX_FOOD}")
    if not 0 <= rec.eaten <= rec.total:
        issues.append("съедено больше, чем было еды, или меньше 0")
    if rec.result == LOSE and rec.eaten != rec.total:
        issues.append("поражение, но Пакман съел не всю еду")
    if rec.result == WIN and rec.eaten >= rec.total:
        issues.append("победа, но Пакман уже съел всю еду")
    if (math.isfinite(rec.time_sec) and rec.time_sec > 0
            and rec.time_sec < rec.eaten * config.MIN_SEC_PER_FOOD):
        issues.append("Пакман не успел бы съесть столько за это время")
    return issues


# ---------- Разбор CSV ----------
def parse_scores_text(text):
    """Разбирает CSV-текст таблицы рекордов и проверяет каждую строку.

    Битые строки не ломают разбор: они попадают в список ошибок
    с номером строки и причиной.

    Args:
        text: содержимое файла (уже декодированное из байтов).

    Returns:
        (records, errors): список проверенных Record и список строк-ошибок.
    """
    records, errors = [], []
    text = text.lstrip("\ufeff")  # BOM, если декодировали без utf-8-sig
    try:
        reader = csv.DictReader(io.StringIO(text))
        header = reader.fieldnames
    except csv.Error as err:
        return [], [f"Файл не читается как CSV: {err}"]
    if not header:
        return [], ["Файл пустой"]
    header = [h.strip() for h in header]
    missing = [f for f in config.CSV_FIELDS if f not in header]
    if missing:
        return [], ["Нет столбцов: " + ", ".join(missing)
                    + ". Ожидается заголовок: " + ",".join(config.CSV_FIELDS)]
    reader.fieldnames = header
    while True:
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error as err:
            errors.append(f"Строка {reader.line_num}: {err}")
            continue
        line = reader.line_num
        if not any((v or "").strip() for v in row.values()
                   if isinstance(v, str)):
            continue  # пустая строка
        if None in row or any(row[f] is None for f in config.CSV_FIELDS):
            errors.append(f"Строка {line}: ожидается "
                          f"{len(config.CSV_FIELDS)} полей")
            continue
        try:
            rec = Record(
                date=row["Дата"].strip(),
                name=row["Имя"].strip(),
                result=row["Результат"].strip(),
                time_sec=float(row["Время"].strip().replace(",", ".")),
                eaten=int(row["Съедено"].strip()),
                total=int(row["Всего"].strip()),
            )
        except ValueError:
            errors.append(f"Строка {line}: Время, Съедено и Всего "
                          f"должны быть числами")
            continue
        issues = verify_record(rec)
        if issues:
            errors.append(f"Строка {line}: " + "; ".join(issues))
            continue
        records.append(rec)
    return records, errors


def parse_scores_file(path):
    """Читает и разбирает CSV-файл. Нет файла - пустой результат."""
    if not path.exists():
        return [], []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as err:
        return [], [f"{path.name}: не удалось прочитать ({err})"]
    return parse_scores_text(text)


def dedup(records):
    """Убирает повторы одной и той же партии, сохраняя порядок."""
    seen, result = set(), []
    for rec in records:
        if rec.key not in seen:
            seen.add(rec.key)
            result.append(rec)
    return result


def load_all_records(game_path=None, db_path=None):
    """Все известные партии: records.csv игры + общая база бота.

    Returns:
        (records, bad_rows): список без дублей и число отброшенных строк.
    """
    game_path = game_path or config.GAME_RECORDS
    db_path = db_path or config.SCORES_DB
    game, err1 = parse_scores_file(game_path)
    db, err2 = parse_scores_file(db_path)
    return dedup(game + db), len(err1) + len(err2)


def append_records(records, db_path=None, known=None):
    """Дописывает в общую базу только новые партии.

    Args:
        records: проверенные записи (из parse_scores_text).
        db_path: путь к базе (по умолчанию config.SCORES_DB).
        known: уже известные записи (например, из records.csv игры),
            чтобы не добавлять их второй раз.

    Returns:
        (added, duplicates): список добавленных записей и число дублей.
    """
    db_path = db_path or config.SCORES_DB
    existing, _ = parse_scores_file(db_path)
    keys = {r.key for r in existing}
    keys.update(r.key for r in (known or []))
    added = []
    for rec in records:
        if rec.key in keys:
            continue
        keys.add(rec.key)
        added.append(rec)
    if added:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        need_header = not db_path.exists() or db_path.stat().st_size == 0
        with open(db_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=config.CSV_FIELDS)
            if need_header:
                writer.writeheader()
            for rec in added:
                writer.writerow(rec.as_row())
    return added, len(records) - len(added)


# ---------- Таблица лидеров ----------
def rank_key(rec):
    """Ключ сортировки - те же правила, что у топ-5 в самой игре.

    1. Сначала победы, потом поражения.
    2. Победы: меньше еды отдал Пакману - выше; при равенстве - кто
       поймал быстрее.
    3. Поражения: выше тот, кто дольше продержался.
    """
    if rec.is_win:
        return (0, rec.eaten, rec.time_sec)
    return (1, 0, -rec.time_sec)


def leaderboard(records, limit=None):
    """Отсортированная таблица лидеров (limit=None - все записи)."""
    rows = sorted(records, key=rank_key)
    return rows if limit is None else rows[:limit]


def page_count(n_items, size=config.TOP_PAGE_SIZE):
    """Сколько страниц нужно для n_items строк (минимум одна)."""
    return max(1, math.ceil(n_items / size))


def _cut(text, width):
    """Обрезает текст до width символов (с многоточием)."""
    return text if len(text) <= width else text[:width - 1] + "…"


def format_leaderboard(records, page=0, highlight=None,
                       size=config.TOP_PAGE_SIZE):
    """Страница таблицы лидеров в HTML (<pre> - моноширинный шрифт).

    Имена из файлов - пользовательские данные, поэтому каждое
    экранируется через html.escape, иначе «<» сломает разметку.
    """
    rows = leaderboard(records)
    if not rows:
        return ("🏆 <b>Таблица лидеров</b>\n\nПока нет ни одной партии. "
                "Сыграйте в игру или загрузите records.csv.")
    pages = page_count(len(rows), size)
    page = min(max(page, 0), pages - 1)
    start = page * size
    lines = [f"{'#':>3} {'Имя':<12} {'Итог':<6} {'Время':>6} {'Еда':>7}"]
    for i, rec in enumerate(rows[start:start + size], start=start + 1):
        mark = "▶" if highlight and same_name(rec.name, highlight) else " "
        result = "ПОЙМАЛ" if rec.is_win else "ПРОИГР"
        food = f"{rec.eaten}/{rec.total}"
        name = html.escape(f"{_cut(rec.name, 12):<12}")
        lines.append(f"{mark}{i:>2} {name} {result:<6} "
                     f"{rec.time_sec:>5.1f}с {food:>7}")
    return (f"🏆 <b>Таблица лидеров</b> (стр. {page + 1}/{pages}, "
            f"партий: {len(rows)})\n"
            "Победы: меньше еды у Пакмана → быстрее. "
            "Поражения: кто дольше продержался.\n"
            "<pre>" + "\n".join(lines) + "</pre>")


# ---------- Личная статистика ----------
def player_records(records, name):
    """Партии одного игрока (имя без учёта регистра)."""
    return [r for r in records if same_name(r.name, name)]


def player_stats(records, name):
    """Личная статистика игрока.

    Returns:
        Словарь с показателями или None, если партий нет.
    """
    mine = player_records(records, name)
    if not mine:
        return None
    wins = [r for r in mine if r.is_win]
    losses = [r for r in mine if not r.is_win]
    ranked = leaderboard(records)
    best = min(mine, key=rank_key)
    return {
        "name": mine[0].name,
        "games": len(mine),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": 100.0 * len(wins) / len(mine),
        "fastest_win": min((r.time_sec for r in wins), default=None),
        "least_eaten": min((r.eaten for r in wins), default=None),
        "avg_eaten_pct": (sum(r.eaten_pct for r in wins) / len(wins)
                          if wins else None),
        "longest_loss": max((r.time_sec for r in losses), default=None),
        "avg_time": sum(r.time_sec for r in mine) / len(mine),
        "best_place": ranked.index(best) + 1,
        "last_game": max(r.date for r in mine),
    }


def format_stats(stats, name):
    """Экран личной статистики (HTML)."""
    safe = html.escape(name or "")
    if not stats:
        return (f"📊 <b>Статистика: {safe}</b>\n\nПартий с таким именем "
                "нет. Проверьте имя (как вы вводили его в игре) "
                "или загрузите свой records.csv.")

    def opt(value, fmt):
        return "—" if value is None else fmt.format(value)

    return (
        f"📊 <b>Статистика: {html.escape(stats['name'])}</b>\n\n"
        f"Партий: <b>{stats['games']}</b>  "
        f"(побед {stats['wins']}, поражений {stats['losses']})\n"
        f"Процент побед: <b>{stats['winrate']:.0f}%</b>\n"
        f"Лучшее место в топе: <b>{stats['best_place']}</b>\n"
        f"Самая быстрая поимка: {opt(stats['fastest_win'], '{:.1f} с')}\n"
        f"Меньше всего еды у Пакмана: {opt(stats['least_eaten'], '{}')}\n"
        f"Пакман в среднем успевал съесть: "
        f"{opt(stats['avg_eaten_pct'], '{:.0f}%')}\n"
        f"Дольше всего продержался (поражение): "
        f"{opt(stats['longest_loss'], '{:.1f} с')}\n"
        f"Средняя длина партии: {stats['avg_time']:.1f} с\n"
        f"Последняя игра: {stats['last_game']}"
    )


# ---------- Ачивки ----------
@dataclass(frozen=True)
class Achievement:
    """Достижение: код, значок, название, условие и получено ли оно."""

    code: str
    icon: str
    title: str
    description: str
    unlocked: bool


def _best_streak(records):
    """Самая длинная серия побед подряд (по дате партии)."""
    best = cur = 0
    for rec in sorted(records, key=lambda r: r.date):
        cur = cur + 1 if rec.is_win else 0
        best = max(best, cur)
    return best


def achievements(records, name):
    """Список ачивок игрока (полученных и ещё нет)."""
    mine = player_records(records, name)
    wins = [r for r in mine if r.is_win]
    return [
        Achievement("first", "👻", "Первая охота",
                    "Поймать Пакмана хотя бы раз", bool(wins)),
        Achievement("lightning", "⚡", "Молния",
                    "Поймать Пакмана быстрее чем за 20 секунд",
                    any(r.time_sec < 20 for r in wins)),
        Achievement("hungry", "🍽", "Голодный Пакман",
                    "Поймать, пока Пакман не съел и 25% еды",
                    any(r.eaten_pct < 25 for r in wins)),
        Achievement("crumbs", "🧊", "Ни крошки",
                    "Поймать, пока Пакман съел не больше 5 точек",
                    any(r.eaten <= 5 for r in wins)),
        Achievement("streak", "🔥", "Серия",
                    "Три победы подряд", _best_streak(mine) >= 3),
        Achievement("hunter", "🎯", "Охотник",
                    "Набрать 5 побед", len(wins) >= 5),
        Achievement("veteran", "🏅", "Ветеран лабиринта",
                    "Сыграть 10 партий", len(mine) >= 10),
        Achievement("patience", "🐢", "Терпение",
                    "Сыграть партию длиннее 2 минут",
                    any(r.time_sec > 120 for r in mine)),
    ]


def format_achievements(records, name):
    """Экран ачивок (HTML)."""
    items = achievements(records, name)
    got = sum(a.unlocked for a in items)
    lines = [f"🎖 <b>Ачивки: {html.escape(name)}</b> ({got}/{len(items)})",
             ""]
    for a in items:
        mark = "✅" if a.unlocked else "▫️"
        lines.append(f"{mark} {a.icon} <b>{a.title}</b> — {a.description}")
    if not player_records(records, name):
        lines += ["", "Партий с этим именем пока нет."]
    return "\n".join(lines)


# ---------- Журнал игры (game.log) ----------
LOG_LINE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| ([A-Z]+) \| (.*)$")
WIN_TIME = re.compile(r"ПОБЕДА: .* за ([\d.]+) с")

# Какие события считаем: (ключ, подстрока в сообщении)
LOG_EVENTS = (
    ("launches", "===== Запуск игры"),
    ("games", "Новая партия"),
    ("steps", "Шаг игрока"),
    ("flee", "-> режим БЕГСТВО"),
    ("calm", "-> режим ПОИСК ЕДЫ"),
    ("wins", "ПОБЕДА:"),
    ("losses", "ПОРАЖЕНИЕ:"),
    ("milestones", "Пакман съел"),
    ("saved", "Результат сохранён"),
    ("level_errors", "Уровень не загружен"),
)


def parse_log_text(text):
    """Сводка по журналу игры.

    Строки, не подходящие под формат «время | уровень | сообщение»,
    не ломают разбор, а считаются в bad_lines.

    Returns:
        Словарь счётчиков и показателей.
    """
    counts = Counter()
    levels = Counter()
    win_times = []
    first = last = None
    bad = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = LOG_LINE.match(line)
        if not m:
            bad += 1
            continue
        stamp, level, msg = m.groups()
        first = first or stamp
        last = stamp
        levels[level] += 1
        for key, needle in LOG_EVENTS:
            if needle in msg:
                counts[key] += 1
        wm = WIN_TIME.search(msg)
        if wm:
            win_times.append(float(wm.group(1)))
    games = counts["games"]
    finished = counts["wins"] + counts["losses"]
    return {
        **{key: counts[key] for key, _ in LOG_EVENTS},
        "levels": dict(levels),
        "bad_lines": bad,
        "first": first,
        "last": last,
        "flee_per_game": counts["flee"] / games if games else 0.0,
        "steps_per_game": counts["steps"] / games if games else 0.0,
        "avg_win_time": (sum(win_times) / len(win_times)
                         if win_times else None),
        "abandoned": max(games - finished, 0),
    }


def parse_log_file(path=None):
    """Сводка по файлу журнала. Файла нет - None."""
    path = path or config.GAME_LOG
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return parse_log_text(f.read())


def format_log_summary(summary, title="game.log"):
    """Экран «Статистика по логу» (HTML)."""
    if summary is None:
        return ("📜 <b>Статистика по логу</b>\n\nФайл game.log не найден. "
                "Запустите игру хотя бы раз - она создаст журнал.")
    avg_win = summary["avg_win_time"]
    rows = [
        ("Запусков игры", summary["launches"]),
        ("Партий начато", summary["games"]),
        ("Поймал Пакмана", summary["wins"]),
        ("Пакман съел всё", summary["losses"]),
        ("Брошено партий", summary["abandoned"]),
        ("Шагов призрака", summary["steps"]),
        ("Пакман убегал", summary["flee"]),
        ("Пакман оторвался", summary["calm"]),
        ("Побегов за партию", f"{summary['flee_per_game']:.1f}"),
        ("Шагов за партию", f"{summary['steps_per_game']:.0f}"),
        ("Ср. время поимки", "—" if avg_win is None else f"{avg_win:.1f} с"),
        ("Ошибок уровня", summary["level_errors"]),
        ("Битых строк", summary["bad_lines"]),
    ]
    table = "\n".join(f"{k:<18} {v:>7}" for k, v in rows)
    period = ""
    if summary["first"]:
        period = f"\nПериод: {summary['first']} — {summary['last']}"
    return (f"📜 <b>Статистика по логу</b> ({html.escape(title)})"
            f"{period}\n<pre>{table}</pre>")


def tail_lines(path, n=20):
    """Последние n строк текстового файла (для /log)."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()[-n:]


def format_new_records(records, limit=5):
    """Короткий текст уведомления о новых партиях (HTML)."""
    lines = []
    for rec in records[:limit]:
        verdict = "поймал Пакмана" if rec.is_win else "проиграл"
        lines.append(f"• <b>{html.escape(rec.name)}</b> {verdict} за "
                     f"{rec.time_sec:.1f} с (еда {rec.eaten}/{rec.total})")
    if len(records) > limit:
        lines.append(f"…и ещё {len(records) - limit}")
    return "\n".join(lines)
