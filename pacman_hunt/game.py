"""Игра целиком: состояние партии, HUD, экраны меню и конца, главный цикл.

ЛР 2: уровень загружается из JSON (storage.load_level), события пишутся
в лог (logger), а в конце партии игрок вводит имя и результат
дописывается в таблицу рекордов CSV (storage.save_result).
"""

import logging
import math
import sys

import pygame

from pacman_hunt.constants import (
    ACCENT, BAR_BG, BIG_FONT_SIZE, CELL, CHAR_DIRS, COLS, DANGER,
    DEFAULT_NAME, FONT_NAME, FONT_SIZE, FOOD, FPS, GHOST_STEP_MS, HEIGHT,
    HUD_BG, HUD_H, KEY_DIRS, LOG_FILE, NAME_MAX_LEN, PAC, RECORDS_FILE,
    RESULT_LOSE, RESULT_WIN, ROWS, TITLE, WHITE, WIDTH,
)
from pacman_hunt.effects import build_background, draw_title, glow_circle
from pacman_hunt.ghost import Ghost
from pacman_hunt.logger import log_event, setup_logging
from pacman_hunt.maze import MAZE, set_maze
from pacman_hunt.pacman import Pacman
from pacman_hunt.storage import (
    default_level, load_level, load_records, save_result, top_records,
)

# Доли съеденной еды, о которых пишем в лог (25 %, 50 %, 75 %)
FOOD_MILESTONES = (0.25, 0.5, 0.75)


class Game:
    """Одна партия игры.

    Attributes:
        level: словарь уровня из storage.load_level.
        food: множество клеток, где ещё лежит еда.
        ghost: объект Ghost (игрок).
        pacman: объект Pacman (ИИ).
        eaten: сколько еды съел Пакман.
        total: сколько еды было в начале партии.
        elapsed: длительность партии в секундах.
        state: "play" - идёт игра, "win" - победа, "lose" - поражение.
        asking_name: True, пока после конца игры вводится имя.
        name: имя, которое набирает игрок.
        saved: удалось ли сохранить результат (None - ещё не сохраняли).
        top: лучшие результаты из таблицы рекордов для экрана конца.
    """

    def __init__(self, level=None):
        """Создаёт игру для уровня level и сразу готовит новую партию."""
        self.level = level or default_level()
        self.reset(announce=False)

    def reset(self, announce=True):
        """Начинает партию заново: еда во всех проходах, герои на старте.

        Args:
            announce: записать ли начало партии в лог (при создании объекта
                до выхода из меню записывать не нужно).
        """
        lv = self.level
        self.food = {(x, y) for y in range(ROWS) for x in range(COLS)
                     if MAZE[y][x] == 0}
        self.ghost = Ghost(lv["ghost_start"])
        self.pacman = Pacman(lv["pac_start"], lv["pac_delay"],
                             lv["flee_dist"], lv["flee_exit"])
        # на стартовых клетках героев еды нет
        self.food.discard(self.pacman.pos)
        self.food.discard(self.ghost.pos)
        self.eaten = 0
        self.total = len(self.food)
        self.elapsed = 0.0
        self.milestone = 0  # сколько отметок FOOD_MILESTONES уже записано
        self.state = "play"  # play / win / lose
        self.asking_name = False
        self.name = ""
        self.saved = None
        self.top = []
        if announce:
            log_event(f"Новая партия: уровень «{lv['name']}», "
                      f"еды {self.total}, призрак {self.ghost.pos}, "
                      f"Пакман {self.pacman.pos}")

    # ----- Логика -----
    def move_ghost(self, dx, dy):
        """Ход игрока. Если призрак наступил на Пакмана - победа."""
        if self.state != "play":
            return
        old = self.ghost.pos
        if self.ghost.move(dx, dy):
            log_event(f"Шаг игрока: призрак {old} -> {self.ghost.pos}")
            if self.ghost.pos == self.pacman.pos:
                self.finish("win")
        else:
            # DEBUG-сообщения в файл не попадают при уровне INFO
            log_event(f"Призрак {old} упёрся в стену", logging.DEBUG)

    def update(self, dt):
        """Обновление за один кадр.

        Args:
            dt: время с прошлого кадра в секундах.
        """
        # плавное скольжение рисуем всегда, даже после конца игры
        self.ghost.animate(dt)
        self.pacman.animate(dt)
        if self.state != "play":
            return
        self.elapsed += dt
        if self.pacman.tick(dt, self.ghost.pos, self.food):
            self.eaten += 1
            self.log_milestone()
        # проверка условий конца игры
        if self.ghost.pos == self.pacman.pos:
            self.finish("win")
        elif not self.food:
            self.finish("lose")

    def log_milestone(self):
        """Пишет в лог, когда Пакман съел очередную четверть еды."""
        if self.milestone >= len(FOOD_MILESTONES) or not self.total:
            return
        mark = FOOD_MILESTONES[self.milestone]
        if self.eaten / self.total >= mark:
            pct = int(mark * 100)
            log_event(f"Пакман съел {pct}% еды ({self.eaten}/{self.total})")
            self.milestone += 1

    def finish(self, state):
        """Конец партии: запись в лог и переход к вводу имени."""
        self.state = state
        self.asking_name = True
        self.name = ""
        if state == "win":
            log_event(f"ПОБЕДА: призрак поймал Пакмана в клетке "
                      f"{self.ghost.pos} за {self.elapsed:.1f} с, "
                      f"съедено {self.eaten}/{self.total}")
        else:
            log_event(f"ПОРАЖЕНИЕ: Пакман съел всю еду за "
                      f"{self.elapsed:.1f} с")

    # ----- Ввод имени и таблица рекордов -----
    def type_text(self, text):
        """Добавляет набранные символы к имени (работает и кириллица)."""
        if not self.asking_name:
            return
        text = "".join(ch for ch in text if ch.isprintable())
        self.name = (self.name + text)[:NAME_MAX_LEN]

    def backspace(self):
        """Удаляет последний символ имени."""
        if self.asking_name:
            self.name = self.name[:-1]

    def submit_name(self, records_path=RECORDS_FILE):
        """Сохраняет результат в CSV и загружает лучшие результаты.

        Args:
            records_path: путь к таблице рекордов (для тестов).
        """
        if not self.asking_name:
            return
        name = self.name.strip() or DEFAULT_NAME
        result = RESULT_WIN if self.state == "win" else RESULT_LOSE
        self.saved = save_result(name, self.elapsed, self.eaten, self.total,
                                 result, records_path)
        self.top = top_records(load_records(records_path))
        self.asking_name = False

    # ----- Отрисовка -----
    def draw(self, screen, font, big, bg):
        """Рисует кадр: фон, еду, героев, HUD и (если нужно) экран конца."""
        t = pygame.time.get_ticks() / 1000
        screen.blit(bg, (0, 0))
        self.draw_food(screen, t)
        self.pacman.draw(screen, t)
        self.ghost.draw(screen, t, self.pacman.screen_center())
        self.draw_hud(screen, font, t)
        if self.state != "play":
            self.draw_end(screen, font, big, t)

    def draw_food(self, screen, t):
        """Еда: пульсирующие точки с мягким свечением."""
        for fx, fy in self.food:
            cx = fx * CELL + CELL // 2
            cy = HUD_H + fy * CELL + CELL // 2
            # у каждой точки своя фаза, чтобы они пульсировали «волной»
            r = 3.6 + 0.9 * math.sin(t * 4 + fx * 0.7 + fy * 0.5)
            glow_circle(screen, FOOD, (cx, cy), 4, strength=110)
            pygame.draw.circle(screen, FOOD, (cx, cy), max(3, round(r)))

    def draw_hud(self, screen, font, t):
        """Верхняя панель: счёт, прогресс съеденной еды и режим Пакмана."""
        pygame.draw.rect(screen, HUD_BG, (0, 0, WIDTH, HUD_H))
        pygame.draw.line(screen, ACCENT, (0, HUD_H - 1), (WIDTH, HUD_H - 1), 2)
        total = self.eaten + len(self.food)
        score = font.render(f"Съедено {self.eaten} / {total}", True, WHITE)
        screen.blit(score, (14, 10))
        # полоска прогресса: насколько Пакман близок к победе
        bx, bw = 190, 220
        pygame.draw.rect(screen, BAR_BG, (bx, 15, bw, 12), border_radius=6)
        frac = self.eaten / total if total else 0
        pygame.draw.rect(screen, DANGER, (bx, 15, int(bw * frac), 12),
                         border_radius=6)
        if self.pacman.mode == "flee":
            blink = 160 + int(95 * abs(math.sin(t * 8)))  # мигание надписи
            txt, col = "Пакман: БЕГСТВО!", (255, blink, 60)
        else:
            txt, col = "Пакман: ищет еду", ACCENT
        surf = font.render(txt, True, col)
        screen.blit(surf, (WIDTH - surf.get_width() - 14, 10))

    def draw_end(self, screen, font, big, t):
        """Экран завершения поверх игры с полупрозрачным затемнением.

        Сначала игрок вводит имя, потом показывается таблица рекордов.
        """
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((5, 3, 20, 200))
        screen.blit(shade, (0, 0))
        win = self.state == "win"
        title = "ПАКМАН ПОЙМАН!" if win else "ПОРАЖЕНИЕ"
        sub = "Вы победили" if win else "Пакман съел всю еду"
        color = ACCENT if win else DANGER
        a = 140 + int(115 * abs(math.sin(t * 3)))  # пульсация подсказки
        if self.asking_name:
            draw_title(screen, big, title, color, (WIDTH // 2, 190))
            info = (f"{sub}.  Время {self.elapsed:.1f} с,  "
                    f"съедено {self.eaten} / {self.total}")
            blit_center(screen, font, info, WHITE, 245)
            blit_center(screen, font, "Введите имя для таблицы рекордов:",
                        WHITE, 310)
            box = pygame.Rect(0, 0, 380, 46)
            box.center = (WIDTH // 2, 360)
            pygame.draw.rect(screen, HUD_BG, box, border_radius=8)
            pygame.draw.rect(screen, ACCENT, box, 2, border_radius=8)
            cursor = "|" if int(t * 2) % 2 == 0 else " "  # мигающий курсор
            txt = font.render(self.name + cursor, True, WHITE)
            screen.blit(txt, txt.get_rect(midleft=(box.x + 14, box.centery)))
            blit_center(screen, font, "Enter - сохранить    Esc - выход",
                        (a, a, 255), 420)
            return
        draw_title(screen, big, title, color, (WIDTH // 2, 120))
        info = (f"{sub}.  Время {self.elapsed:.1f} с,  "
                f"съедено {self.eaten} / {self.total}")
        blit_center(screen, font, info, WHITE, 172)
        if self.saved:
            note, note_col = "Результат сохранён в records.csv", ACCENT
        else:
            note = "Не удалось сохранить результат (см. game.log)"
            note_col = DANGER
        blit_center(screen, font, note, note_col, 204)
        self.draw_records(screen, font, 250)
        blit_center(screen, font, "R - заново    Esc - выход",
                    (a, a, 255), 560)

    def draw_records(self, screen, font, top):
        """Таблица лучших результатов (колонки с фиксированными отступами)."""
        blit_center(screen, font, "ЛУЧШИЕ РЕЗУЛЬТАТЫ", PAC, top)
        x0 = WIDTH // 2 - 290
        cols = [(x0, "№"), (x0 + 40, "Имя"), (x0 + 270, "Результат"),
                (x0 + 420, "Время"), (x0 + 510, "Еда")]
        y = top + 34
        for x, head in cols:
            screen.blit(font.render(head, True, ACCENT), (x, y))
        if not self.top:
            blit_center(screen, font, "Пока нет записей", WHITE, y + 50)
            return
        for i, r in enumerate(self.top, 1):
            y += 34
            col = WHITE if r["Результат"] == RESULT_WIN else (200, 190, 230)
            values = [str(i), r["Имя"][:NAME_MAX_LEN], r["Результат"],
                      f"{r['Время']:.1f} с", f"{r['Съедено']}/{r['Всего']}"]
            for (x, _), val in zip(cols, values):
                screen.blit(font.render(val, True, col), (x, y))


def blit_center(screen, font, text, color, y):
    """Рисует строку текста по центру окна на высоте y."""
    s = font.render(text, True, color)
    screen.blit(s, s.get_rect(center=(WIDTH // 2, y)))


def draw_menu(screen, font, big, bg, level):
    """Стартовый экран: название, правила, уровень и подсказка."""
    t = pygame.time.get_ticks() / 1000
    screen.blit(bg, (0, 0))
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    shade.fill((5, 3, 20, 200))
    screen.blit(shade, (0, 0))
    draw_title(screen, big, "PAC-MAN HUNT", PAC,
               (WIDTH // 2, HEIGHT // 2 - 110))
    lines = [
        "Вы - призрак. Поймайте Пакмана, пока он не съел всю еду.",
        "Управление: WASD / стрелки",
        f"Пакман убегает, если вы ближе {level['flee_dist']:g} клеток",
    ]
    for i, line in enumerate(lines):
        blit_center(screen, font, line, WHITE, HEIGHT // 2 - 40 + i * 32)
    a = 140 + int(115 * abs(math.sin(t * 3)))  # пульсация подсказки
    blit_center(screen, font, "Нажмите ПРОБЕЛ, чтобы начать", (a, a, 255),
                HEIGHT // 2 + 90)
    # какой уровень загружен; если файл не прочитался - предупреждение
    if level["is_default"]:
        blit_center(screen, font, "Файл уровня не загружен - используется "
                    "уровень по умолчанию (см. game.log)", DANGER,
                    HEIGHT - 50)
    else:
        blit_center(screen, font, f"Уровень: {level['name']}", ACCENT,
                    HEIGHT - 50)


def load_fonts():
    """Создаёт обычный и крупный шрифты (вызывать после pygame.init())."""
    font = pygame.font.SysFont(FONT_NAME, FONT_SIZE, bold=True)
    big = pygame.font.SysFont(FONT_NAME, BIG_FONT_SIZE, bold=True)
    return font, big


def handle_key(game, e):
    """Обработка нажатия клавиши во время партии (не в меню).

    Returns:
        False, если игрок хочет выйти, иначе True.
    """
    if e.key == pygame.K_ESCAPE:
        if game.asking_name:
            log_event("Выход без сохранения результата")
        return False
    if game.asking_name:
        # во время ввода имени буквы идут в имя (через TEXTINPUT),
        # а R и WASD не должны перезапускать игру или двигать призрака
        if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            game.submit_name()
        elif e.key == pygame.K_BACKSPACE:
            game.backspace()
    elif e.key == pygame.K_r:
        log_event("Рестарт по клавише R")
        game.reset()
    else:
        # направление по коду клавиши или по русской букве
        d = KEY_DIRS.get(e.key) or CHAR_DIRS.get(e.unicode.lower())
        if d:
            game.move_ghost(*d)
    return True


def main():
    """Запускает окно игры и главный цикл: события -> логика -> отрисовка."""
    setup_logging(LOG_FILE)
    log_event("===== Запуск игры Pac-Man Hunt =====")
    # загрузка уровня: при любой ошибке вернётся уровень по умолчанию
    level = load_level()
    set_maze(level["maze"])  # до build_background, чтобы нарисовать стены

    pygame.init()
    # зажатая клавиша повторяет шаг призрака каждые GHOST_STEP_MS мс
    pygame.key.set_repeat(GHOST_STEP_MS, GHOST_STEP_MS)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(TITLE)
    pygame.key.start_text_input()  # события TEXTINPUT для ввода имени
    clock = pygame.time.Clock()
    font, big = load_fonts()
    bg = build_background()  # статичный фон рисуется один раз
    game = Game(level)
    in_menu = True  # сначала показываем стартовый экран

    running = True
    while running:
        dt = clock.tick(FPS) / 1000  # секунды с прошлого кадра
        # --- обработка событий ---
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.TEXTINPUT:
                if not in_menu:
                    game.type_text(e.text)  # символы имени (и кириллица)
            elif e.type == pygame.KEYDOWN:
                if in_menu:
                    if e.key == pygame.K_ESCAPE:
                        running = False
                    elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
                        in_menu = False
                        game.reset()
                else:
                    running = handle_key(game, e)
        # --- логика и отрисовка ---
        if in_menu:
            draw_menu(screen, font, big, bg, level)
        else:
            game.update(dt)
            game.draw(screen, font, big, bg)
        pygame.display.flip()
    log_event("Выход из игры")
    logging.shutdown()  # дописать буферы и закрыть лог-файл
    pygame.quit()
    sys.exit()
