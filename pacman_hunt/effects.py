"""Графические эффекты: неоновое свечение, градиенты, заголовки и фон.

Функции модуля не содержат игровой логики, они только рисуют.
"""

import math

import pygame

from pacman_hunt.constants import (
    BG_BOTTOM, BG_TOP, CELL, COLS, HEIGHT, HUD_H, ROWS, WALL_EDGE,
    WALL_FILL, WIDTH,
)
from pacman_hunt.maze import MAZE, is_free


def make_glow(surface, scale=0.25, passes=2):
    """Делает размытую копию поверхности для эффекта мягкого свечения.

    Размытие грубое, но быстрое: поверхность уменьшается и снова
    увеличивается со сглаживанием, и так несколько раз.

    Args:
        surface: исходная поверхность.
        scale: во сколько раз уменьшать (меньше - сильнее размытие).
        passes: количество проходов размытия.

    Returns:
        Новая размытая поверхность того же размера.
    """
    w, h = surface.get_size()
    glow = surface
    for _ in range(passes):
        small = pygame.transform.smoothscale(
            glow, (max(1, int(w * scale)), max(1, int(h * scale))))
        glow = pygame.transform.smoothscale(small, (w, h))
    return glow


def vertical_gradient(w, h, top, bottom):
    """Создаёт поверхность с вертикальным градиентом цвета.

    Args:
        w: ширина поверхности.
        h: высота поверхности.
        top: цвет верхней строки (R, G, B).
        bottom: цвет нижней строки (R, G, B).

    Returns:
        Поверхность pygame.Surface с градиентом.
    """
    surf = pygame.Surface((w, h))
    for y in range(h):
        t = y / max(1, h - 1)  # доля высоты от 0 до 1
        c = [int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)]
        pygame.draw.line(surf, c, (0, y), (w, y))
    return surf


def glow_circle(screen, color, pos, radius, strength=90):
    """Рисует мягкий круглый ореол вокруг точки.

    На чёрной поверхности рисуются затухающие круги, затем она
    добавляется к экрану сложением цветов (BLEND_RGB_ADD), поэтому
    чёрный фон не виден, а светлые места подсвечивают картинку.

    Args:
        screen: поверхность, на которой рисуем.
        color: цвет свечения.
        pos: центр (x, y) в пикселях.
        radius: радиус объекта, вокруг которого свечение.
        strength: яркость свечения (0-255).
    """
    size = radius * 6
    s = pygame.Surface((size, size))
    steps = 10
    for i in range(steps, 0, -1):
        k = i / steps
        f = strength / 255 * (1 - k) ** 2 * 0.5  # яркость падает к краю
        c = tuple(int(ch * f) for ch in color)
        pygame.draw.circle(s, c, (size // 2, size // 2),
                           int(radius * (1 + 1.6 * k)))
    screen.blit(s, (pos[0] - size // 2, pos[1] - size // 2),
                special_flags=pygame.BLEND_RGB_ADD)


def draw_title(screen, big, text, color, center):
    """Рисует крупный заголовок с неоновым свечением.

    Args:
        screen: поверхность, на которой рисуем.
        big: крупный шрифт pygame.font.Font.
        text: текст заголовка.
        color: цвет текста.
        center: центр заголовка (x, y).
    """
    surf = big.render(text, True, color)
    # текст на чёрном фоне с полями, чтобы свечению было куда расплыться
    glow = pygame.Surface((surf.get_width() + 40, surf.get_height() + 40))
    glow.blit(surf, (20, 20))
    glow = make_glow(glow, 0.2)
    screen.blit(glow, glow.get_rect(center=center),
                special_flags=pygame.BLEND_RGB_ADD)
    screen.blit(surf, surf.get_rect(center=center))


def build_background():
    """Один раз рисует статичный фон: градиент и стены с неоновой кромкой.

    Фон не меняется во время игры, поэтому его выгодно нарисовать
    заранее и в каждом кадре просто копировать на экран.

    Returns:
        Поверхность размером с окно.
    """
    bg = vertical_gradient(WIDTH, HEIGHT, BG_TOP, BG_BOTTOM)
    oy = HUD_H  # лабиринт начинается под панелью HUD
    edges = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    m = 3  # отступ кромки внутрь стены
    for y in range(ROWS):
        for x in range(COLS):
            if MAZE[y][x] != 1:
                continue
            rx, ry = x * CELL, oy + y * CELL
            pygame.draw.rect(bg, WALL_FILL, (rx, ry, CELL, CELL))
            # кромку рисуем только с тех сторон, где рядом проход
            if is_free(x, y - 1):
                pygame.draw.line(edges, WALL_EDGE, (rx, ry + m),
                                 (rx + CELL, ry + m), 3)
            if is_free(x, y + 1):
                pygame.draw.line(edges, WALL_EDGE, (rx, ry + CELL - m),
                                 (rx + CELL, ry + CELL - m), 3)
            if is_free(x - 1, y):
                pygame.draw.line(edges, WALL_EDGE, (rx + m, ry),
                                 (rx + m, ry + CELL), 3)
            if is_free(x + 1, y):
                pygame.draw.line(edges, WALL_EDGE, (rx + CELL - m, ry),
                                 (rx + CELL - m, ry + CELL), 3)
    # два слоя размытия разной ширины + чёткая линия сверху = неон
    bg.blit(make_glow(edges, 0.2), (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    bg.blit(make_glow(edges, 0.35), (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    bg.blit(edges, (0, 0))
    return bg


def approach(cur, target, max_step):
    """Сдвигает точку cur к target не более чем на max_step.

    Используется для плавной анимации: логика игры клеточная,
    а на экране персонажи «скользят» между клетками.

    Args:
        cur: текущая экранная позиция (x, y) в клетках (дробная).
        target: целевая клетка (x, y).
        max_step: максимальный сдвиг за кадр (в клетках).

    Returns:
        Новая позиция (x, y).
    """
    dx, dy = target[0] - cur[0], target[1] - cur[1]
    dist = math.hypot(dx, dy)
    if dist <= max_step or dist == 0:
        return (float(target[0]), float(target[1]))
    k = max_step / dist
    return (cur[0] + dx * k, cur[1] + dy * k)
