"""Призрак - персонаж, которым управляет игрок."""

import math

import pygame

from pacman_hunt.constants import (
    CELL, EYE, GHOST, GHOST_SHINE, GHOST_START, GHOST_VIS_SPEED, HUD_H, WHITE,
)
from pacman_hunt.effects import approach, glow_circle
from pacman_hunt.maze import is_free


class Ghost:
    """Призрак игрока.

    Attributes:
        pos: логическая клетка (x, y).
        vis: экранная позиция (x, y) в клетках для плавной анимации.
    """

    def __init__(self, start=GHOST_START):
        """Создаёт призрака в клетке start."""
        self.pos = start
        self.vis = (float(start[0]), float(start[1]))

    def move(self, dx, dy):
        """Пытается сдвинуть призрака на одну клетку.

        Args:
            dx: сдвиг по горизонтали (-1, 0, 1).
            dy: сдвиг по вертикали (-1, 0, 1).

        Returns:
            True, если ход сделан (в клетке не стена).
        """
        nx, ny = self.pos[0] + dx, self.pos[1] + dy
        if is_free(nx, ny):
            self.pos = (nx, ny)
            return True
        return False

    def animate(self, dt):
        """Плавно сдвигает экранную позицию к логической клетке."""
        self.vis = approach(self.vis, self.pos, GHOST_VIS_SPEED * dt)

    def draw(self, screen, t, look_at):
        """Рисует призрака: ореол, купол, волнистый «подол» и глаза.

        Args:
            screen: поверхность для рисования.
            t: время в секундах (для покачивания и волны подола).
            look_at: точка (x, y) в пикселях, куда смотрят глаза (Пакман).
        """
        cx = self.vis[0] * CELL + CELL / 2
        cy = HUD_H + self.vis[1] * CELL + CELL / 2 + 2 * math.sin(t * 3)
        r = CELL // 2 - 4
        glow_circle(screen, GHOST, (int(cx), int(cy)), r, strength=120)
        body = []
        for i in range(19):  # купол - верхняя полуокружность
            a = math.pi + math.pi * i / 18
            body.append((cx + r * math.cos(a), cy - 2 + r * math.sin(a)))
        waves = 4
        bottom = cy + r
        for i in range(waves * 4 + 1):  # подол-волна справа налево
            px = cx + r - (2 * r) * i / (waves * 4)
            py = bottom - 3 + 3 * math.sin(i * math.pi / 2 + t * 10)
            body.append((px, py))
        pygame.draw.polygon(screen, GHOST, body)
        # блик на куполе
        pygame.draw.circle(screen, GHOST_SHINE,
                           (int(cx - r * 0.4), int(cy - r * 0.45)), 3)
        # глаза следят за целью: зрачок смещён в её сторону
        lx, ly = look_at[0] - cx, look_at[1] - cy
        ln = math.hypot(lx, ly) or 1
        lx, ly = lx / ln * 2.5, ly / ln * 2.5
        for side in (-1, 1):
            exx, eyy = cx + side * r * 0.4, cy - r * 0.2
            pygame.draw.ellipse(screen, WHITE, (exx - 4, eyy - 5, 8, 10))
            pygame.draw.circle(screen, EYE, (int(exx + lx), int(eyy + ly)), 2)
