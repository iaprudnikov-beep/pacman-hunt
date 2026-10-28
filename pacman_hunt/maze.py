"""Лабиринт и поиск пути.

Модуль хранит сетку лабиринта и реализует поиск в ширину (BFS),
который Пакман использует, чтобы находить еду и убегать от призрака.
"""

from collections import deque

from pacman_hunt.constants import COLS, DIRS, MAZE_STR, ROWS

# Сетка лабиринта: MAZE[y][x] == 1 - стена, 0 - проход.
# Сначала это лабиринт по умолчанию; при старте игры set_maze заменяет его
# лабиринтом из файла уровня.
MAZE = [[int(c) for c in row] for row in MAZE_STR]


def set_maze(matrix):
    """Подставляет лабиринт загруженного уровня.

    Список MAZE меняется «на месте» (MAZE[:] = ...), а не создаётся заново:
    другие модули импортировали именно этот объект и сразу видят изменения.

    Args:
        matrix: проверенная матрица ROWS x COLS из 0 и 1.
    """
    MAZE[:] = [list(row) for row in matrix]


def is_free(x, y):
    """Проверяет, что клетка (x, y) внутри поля и не является стеной.

    Args:
        x: номер столбца.
        y: номер ряда.

    Returns:
        True, если по клетке можно ходить.
    """
    return 0 <= x < COLS and 0 <= y < ROWS and MAZE[y][x] == 0


def bfs_map(start, blocked=()):
    """Поиск в ширину от клетки start по всему лабиринту.

    Args:
        start: стартовая клетка (x, y).
        blocked: клетки, через которые нельзя проходить (например, призрак).

    Returns:
        Кортеж (dist, prev): dist - расстояние в шагах до каждой достижимой
        клетки, prev - «родитель» каждой клетки для восстановления пути.
    """
    dist = {start: 0}
    prev = {start: None}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for dx, dy in DIRS:
            nxt = (cur[0] + dx, cur[1] + dy)
            # пропускаем уже посещённые, заблокированные клетки и стены
            if nxt in dist or nxt in blocked or not is_free(*nxt):
                continue
            dist[nxt] = dist[cur] + 1
            prev[nxt] = cur
            queue.append(nxt)
    return dist, prev


def first_step(prev, start, target):
    """Находит первую клетку кратчайшего пути от start к target.

    Идём от цели назад по «родителям», пока не дойдём до соседа start.

    Args:
        prev: словарь родителей из bfs_map.
        start: откуда начинается путь.
        target: куда нужно прийти (должна быть достижима).

    Returns:
        Клетка (x, y), в которую нужно сделать первый шаг.
    """
    cur = target
    while prev[cur] != start:
        cur = prev[cur]
    return cur


def bfs_path_first_step(start, targets, blocked=()):
    """Первый шаг к ближайшей цели из targets.

    Args:
        start: текущая клетка.
        targets: множество целевых клеток (например, еда).
        blocked: клетки, через которые нельзя проходить.

    Returns:
        Клетка (x, y) первого шага или None, если ни одна цель не достижима.
    """
    dist, prev = bfs_map(start, blocked)
    reachable = [t for t in targets if t in dist and t != start]
    if not reachable:
        return None
    nearest = min(reachable, key=dist.get)
    return first_step(prev, start, nearest)
