"""Пакман - персонаж под управлением ИИ.

Поведение:
    * режим "chase" (поиск еды) - BFS до ближайшей клетки с едой;
    * режим "flee" (бегство) - включается, когда призрак ближе FLEE_DIST
      клеток; Пакман идёт в клетку, до которой успевает раньше призрака
      и которая от призрака дальше всего;
    * гистерезис: из бегства Пакман выходит, только когда призрак дальше
      FLEE_EXIT клеток, чтобы режимы не «мигали» на границе.
"""

import math

import pygame

from pacman_hunt.constants import (
    CELL, DIRS, FLEE_DIST, FLEE_EXIT, HUD_H, PAC, PAC_DELAY, PAC_EYE,
    PAC_FLEE, PAC_START, PAC_VIS_SPEED,
)
from pacman_hunt.effects import approach, glow_circle
from pacman_hunt.maze import bfs_map, bfs_path_first_step, first_step, is_free


class Pacman:
    """Пакман: позиция, режим ИИ, таймер шагов и отрисовка.

    Attributes:
        pos: логическая клетка (x, y).
        vis: экранная позиция (x, y) в клетках для плавной анимации.
        direction: последнее направление движения (dx, dy) - для рта.
        mode: "chase" (ищет еду) или "flee" (убегает).
        timer: сколько секунд осталось до следующего шага.
    """

    def __init__(self, start=PAC_START):
        """Создаёт Пакмана в клетке start."""
        self.pos = start
        self.vis = (float(start[0]), float(start[1]))
        self.direction = (1, 0)
        self.mode = "chase"
        self.timer = 0.0

    # ----- ИИ -----
    def ghost_distance(self, ghost_pos):
        """Евклидово расстояние (в клетках) от Пакмана до призрака."""
        return math.hypot(self.pos[0] - ghost_pos[0],
                          self.pos[1] - ghost_pos[1])

    def update_mode(self, ghost_pos):
        """Переключает режим с гистерезисом.

        Вход в бегство при d < FLEE_DIST, выход при d >= FLEE_EXIT.
        """
        d = self.ghost_distance(ghost_pos)
        if self.mode == "chase" and d < FLEE_DIST:
            self.mode = "flee"
        elif self.mode == "flee" and d >= FLEE_EXIT:
            self.mode = "chase"

    def _flee_step(self, ghost_pos):
        """Выбирает следующую клетку в режиме бегства."""
        # gd - расстояния от призрака, pd - расстояния от Пакмана
        gd, _ = bfs_map(ghost_pos)
        pd, prev = bfs_map(self.pos, blocked={ghost_pos})
        best, best_score = None, -1e9
        for cell, my_dist in pd.items():
            if cell == self.pos:
                continue
            g = gd.get(cell, 999)
            if my_dist < g:  # Пакман успевает туда раньше призрака
                # чем дальше клетка от призрака и ближе к Пакману - тем лучше
                score = g - 0.3 * my_dist
                if score > best_score:
                    best, best_score = cell, score
        if best is not None:
            self.pos = first_step(prev, self.pos, best)
        else:
            # безопасных клеток нет - шаг в соседнюю, самую далёкую от призрака
            options = [(self.pos[0] + dx, self.pos[1] + dy) for dx, dy in DIRS]
            options = [c for c in options if is_free(*c) and c != ghost_pos]
            if options:
                self.pos = max(options, key=lambda c: gd.get(c, 0))

    def _chase_step(self, ghost_pos, food):
        """Делает шаг к ближайшей еде, обходя клетку призрака."""
        step = bfs_path_first_step(self.pos, food, blocked={ghost_pos})
        if step:
            self.pos = step

    def step(self, ghost_pos, food):
        """Один логический шаг Пакмана.

        Args:
            ghost_pos: клетка призрака.
            food: множество клеток с едой (изменяется на месте).

        Returns:
            True, если на этом шаге Пакман съел еду.
        """
        old = self.pos
        self.update_mode(ghost_pos)
        if self.mode == "flee":
            self._flee_step(ghost_pos)
        else:
            self._chase_step(ghost_pos, food)
        if self.pos != old:
            self.direction = (self.pos[0] - old[0], self.pos[1] - old[1])
        if self.pos in food:
            food.remove(self.pos)
            return True
        return False

    def tick(self, dt, ghost_pos, food):
        """Отсчитывает таймер и делает шаг раз в PAC_DELAY секунд.

        Returns:
            True, если на этом кадре была съедена еда.
        """
        self.timer -= dt
        if self.timer <= 0:
            self.timer = PAC_DELAY
            return self.step(ghost_pos, food)
        return False

    def animate(self, dt):
        """Плавно сдвигает экранную позицию к логической клетке."""
        self.vis = approach(self.vis, self.pos, PAC_VIS_SPEED * dt)

    # ----- Отрисовка -----
    def screen_center(self):
        """Центр Пакмана на экране в пикселях (x, y)."""
        return (int(self.vis[0] * CELL + CELL / 2),
                int(HUD_H + self.vis[1] * CELL + CELL / 2))

    def draw(self, screen, t):
        """Рисует Пакмана: ореол, тело с анимированным ртом и глаз.

        Args:
            screen: поверхность для рисования.
            t: время в секундах (для анимации рта).
        """
        pcx, pcy = self.screen_center()
        pr = CELL // 2 - 4
        color = PAC if self.mode == "chase" else PAC_FLEE
        glow_circle(screen, color, (pcx, pcy), pr, strength=110)
        mouth = math.radians(4 + 38 * abs(math.sin(t * 9)))  # раскрытие рта
        base = math.atan2(self.direction[1], self.direction[0])
        # тело рисуем многоугольником-сектором, чтобы рот был ровным
        pts = [(pcx, pcy)]
        steps = 28
        for i in range(steps + 1):
            a = base + mouth + (2 * math.pi - 2 * mouth) * i / steps
            pts.append((pcx + pr * math.cos(a), pcy + pr * math.sin(a)))
        pygame.draw.polygon(screen, color, pts)
        # глаз всегда сверху от направления движения
        eye_a = base - math.pi / 2 * (1 if self.direction[0] >= 0 else -1)
        ex = pcx + pr * 0.45 * math.cos(eye_a) + pr * 0.15 * math.cos(base)
        ey = pcy + pr * 0.45 * math.sin(eye_a) + pr * 0.15 * math.sin(base)
        pygame.draw.circle(screen, PAC_EYE, (int(ex), int(ey)), 2)
