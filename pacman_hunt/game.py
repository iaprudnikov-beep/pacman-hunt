"""Игра целиком: состояние партии, HUD, экраны меню и конца, главный цикл."""

import math
import sys

import pygame

from pacman_hunt.constants import (
    ACCENT, BAR_BG, BIG_FONT_SIZE, CELL, CHAR_DIRS, COLS, DANGER, FONT_NAME,
    FONT_SIZE, FOOD, FPS, GHOST_START, GHOST_STEP_MS, HEIGHT, HUD_BG, HUD_H,
    KEY_DIRS, PAC, PAC_START, ROWS, TITLE, WHITE, WIDTH,
)
from pacman_hunt.effects import build_background, draw_title, glow_circle
from pacman_hunt.ghost import Ghost
from pacman_hunt.maze import MAZE
from pacman_hunt.pacman import Pacman


class Game:
    """Одна партия игры.

    Attributes:
        food: множество клеток, где ещё лежит еда.
        ghost: объект Ghost (игрок).
        pacman: объект Pacman (ИИ).
        eaten: сколько еды съел Пакман.
        state: "play" - идёт игра, "win" - победа, "lose" - поражение.
    """

    def __init__(self):
        """Создаёт игру и сразу готовит новую партию."""
        self.reset()

    def reset(self):
        """Начинает партию заново: еда во всех проходах, герои на старте."""
        self.food = {(x, y) for y in range(ROWS) for x in range(COLS)
                     if MAZE[y][x] == 0}
        self.ghost = Ghost(GHOST_START)
        self.pacman = Pacman(PAC_START)
        # на стартовых клетках героев еды нет
        self.food.discard(self.pacman.pos)
        self.food.discard(self.ghost.pos)
        self.eaten = 0
        self.state = "play"  # play / win / lose

    # ----- Логика -----
    def move_ghost(self, dx, dy):
        """Ход игрока. Если призрак наступил на Пакмана - победа."""
        if self.state != "play":
            return
        if self.ghost.move(dx, dy) and self.ghost.pos == self.pacman.pos:
            self.state = "win"

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
        if self.pacman.tick(dt, self.ghost.pos, self.food):
            self.eaten += 1
        # проверка условий конца игры
        if self.ghost.pos == self.pacman.pos:
            self.state = "win"
        elif not self.food:
            self.state = "lose"

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
        """Экран завершения поверх игры с полупрозрачным затемнением."""
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((5, 3, 20, 190))
        screen.blit(shade, (0, 0))
        win = self.state == "win"
        title = "ПАКМАН ПОЙМАН!" if win else "ПОРАЖЕНИЕ"
        sub = "Вы победили" if win else "Пакман съел всю еду"
        color = ACCENT if win else DANGER
        draw_title(screen, big, title, color, (WIDTH // 2, HEIGHT // 2 - 30))
        s = font.render(sub, True, WHITE)
        screen.blit(s, s.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20)))
        a = 140 + int(115 * abs(math.sin(t * 3)))
        h = font.render("R - заново    Esc - выход", True, (a, a, 255))
        screen.blit(h, h.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 60)))


def draw_menu(screen, font, big, bg):
    """Стартовый экран: название, правила и подсказка по управлению."""
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
        "Пакман убегает, если вы ближе 5 клеток",
    ]
    for i, line in enumerate(lines):
        s = font.render(line, True, WHITE)
        center = (WIDTH // 2, HEIGHT // 2 - 40 + i * 32)
        screen.blit(s, s.get_rect(center=center))
    a = 140 + int(115 * abs(math.sin(t * 3)))  # пульсация подсказки
    s = font.render("Нажмите ПРОБЕЛ, чтобы начать", True, (a, a, 255))
    screen.blit(s, s.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 90)))


def load_fonts():
    """Создаёт обычный и крупный шрифты (вызывать после pygame.init())."""
    font = pygame.font.SysFont(FONT_NAME, FONT_SIZE, bold=True)
    big = pygame.font.SysFont(FONT_NAME, BIG_FONT_SIZE, bold=True)
    return font, big


def main():
    """Запускает окно игры и главный цикл: события -> логика -> отрисовка."""
    pygame.init()
    # зажатая клавиша повторяет шаг призрака каждые GHOST_STEP_MS мс
    pygame.key.set_repeat(GHOST_STEP_MS, GHOST_STEP_MS)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()
    font, big = load_fonts()
    bg = build_background()  # статичный фон рисуется один раз
    game = Game()
    in_menu = True  # сначала показываем стартовый экран

    running = True
    while running:
        dt = clock.tick(FPS) / 1000  # секунды с прошлого кадра
        # --- обработка событий ---
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif in_menu:
                    if e.key in (pygame.K_SPACE, pygame.K_RETURN):
                        in_menu = False
                        game.reset()
                elif e.key == pygame.K_r:
                    game.reset()
                else:
                    # направление по коду клавиши или по русской букве
                    d = KEY_DIRS.get(e.key) or CHAR_DIRS.get(e.unicode.lower())
                    if d:
                        game.move_ghost(*d)
        # --- логика и отрисовка ---
        if in_menu:
            draw_menu(screen, font, big, bg)
        else:
            game.update(dt)
            game.draw(screen, font, big, bg)
        pygame.display.flip()
    pygame.quit()
    sys.exit()
