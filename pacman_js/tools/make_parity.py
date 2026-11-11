"""Генерирует tests/parity_cases.json — эталонные ответы НАСТОЯЩЕГО Python-кода ЛР 1-2.

selftest.js сравнивает с ними JS-версию (паритет Python <-> JS).
Запуск из папки pacman_js:  python3 tools/make_parity.py
pygame не нужен: подставляем заглушку, логике он не требуется.
"""
import copy
import json
import random
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # корень репозитория
sys.path.insert(0, str(ROOT))


class _Stub(types.ModuleType):
    """Заглушка pygame: любые pygame.K_w и т. п. — просто 0."""
    def __getattr__(self, name):
        return 0


sys.modules.setdefault("pygame", _Stub("pygame"))

from pacman_hunt.maze import bfs_map, set_maze          # noqa: E402
from pacman_hunt.pacman import Pacman                    # noqa: E402
from pacman_hunt.storage import LevelError, validate_level  # noqa: E402

LEVEL = ROOT / "pacman_hunt" / "data" / "level.json"
raw = json.loads(LEVEL.read_text(encoding="utf-8"))
level = validate_level(raw)
set_maze(level["maze"])
free = [(x, y) for y, row in enumerate(level["maze"])
        for x, c in enumerate(row) if c == 0]

rnd = random.Random(2026)
steps = []
for _ in range(120):
    pac, ghost = rnd.sample(free, 2)
    food = set(rnd.sample([c for c in free if c != pac], rnd.randint(1, 40)))
    food_order = list(food)          # порядок, в котором Python перебирает множество
    p1 = Pacman(start=pac)
    p1._chase_step(ghost, food)  # тот же объект: порядок перебора = food_order
    p2 = Pacman(start=pac)
    p2._flee_step(ghost)
    dist, _ = bfs_map(pac)
    steps.append({
        "pac": list(pac), "ghost": list(ghost), "food": [list(c) for c in food_order],
        "chase": list(p1.pos), "flee": list(p2.pos),
        "reach": len(dist), "distSum": sum(dist.values()),
    })

# Гистерезис: для каждого расстояния — режим после update_mode из обоих режимов
modes = []
for dx in range(0, 10):
    for dy in range(0, 10):
        pos, gpos = (10, 7), (10 + dx, 7 + dy)
        row = {"dx": dx, "dy": dy}
        for start in ("chase", "flee"):
            p = Pacman(start=pos)
            p.mode = start
            p.update_mode(gpos)
            row[start] = p.mode
        modes.append(row)

# Валидация: набор испорченных уровней и ответ Python (принят / отклонён)
def broken(fn):
    d = copy.deepcopy(raw)
    fn(d)
    return d

variants = {
    "исходный уровень": raw,
    "нет ключа maze": broken(lambda d: d.pop("maze")),
    "14 рядов": broken(lambda d: d["maze"].pop()),
    "клетка = 2": broken(lambda d: d["maze"][1].__setitem__(1, 2)),
    "клетка = true": broken(lambda d: d["maze"][1].__setitem__(1, True)),
    "старт в стене": broken(lambda d: d["ghost"].__setitem__("start", [0, 0])),
    "старт вне поля": broken(lambda d: d["pacman"].__setitem__("start", [30, 3])),
    "одинаковые старты": broken(lambda d: d["pacman"].__setitem__("start", d["ghost"]["start"])),
    "старт строкой": broken(lambda d: d["ghost"].__setitem__("start", "1,1")),
    "delay = 0": broken(lambda d: d["pacman"].__setitem__("delay", 0)),
    "delay = true": broken(lambda d: d["pacman"].__setitem__("delay", True)),
    "flee_exit < flee_dist": broken(lambda d: d["pacman"].__setitem__("flee_exit", 3)),
    "без необязательных": broken(lambda d: [d["pacman"].pop(k, None) for k in ("delay", "flee_dist", "flee_exit")]),
    "без имени": broken(lambda d: d.pop("name")),
    "корень - список": [1, 2, 3],
}
validation = []
for name, data in variants.items():
    try:
        validate_level(data)
        ok = True
    except LevelError:
        ok = False
    validation.append({"name": name, "data": data, "ok": ok})

out = {"level": str(LEVEL.relative_to(ROOT)), "food": len(free) - 2,
       "steps": steps, "modes": modes, "validation": validation}
dest = Path(__file__).resolve().parents[1] / "tests" / "parity_cases.json"
dest.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(f"Записано {dest.name}: {len(steps)} шагов, {len(modes)} расстояний, "
      f"{len(validation)} уровней")
