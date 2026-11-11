// js/gameField.js — игровое поле: лабиринт, стены, поиск пути, загрузка уровня из JSON
import {
  CELL, HUD_H, COLS, ROWS, DIRS, MAZE_STR, GHOST_START, PAC_START,
  PAC_DELAY, FLEE_DIST, FLEE_EXIT, DEFAULT_LEVEL_NAME, cellKey,
} from './constants.js';
import { Rect } from './rect.js';
import { LevelError } from './levelError.js';

// Маленькие помощники для проверки типов
const isNumber = (v) => typeof v === 'number' && Number.isFinite(v); // true/false сюда не пройдут
const isInt = (v) => Number.isInteger(v);

export class GameField {
  constructor(level) {
    this.name = level.name;
    this.maze = level.maze.map((row) => [...row]); // копия: maze[y][x], 1 — стена, 0 — проход
    this.ghostStart = [...level.ghostStart];
    this.pacStart = [...level.pacStart];
    this.pacDelay = level.pacDelay;
    this.fleeDist = level.fleeDist;
    this.fleeExit = level.fleeExit;
    this.isDefault = Boolean(level.isDefault);
    // Прямоугольники всех стен в пикселях — для проверки столкновений
    this.wallRects = [];
    for (let y = 0; y < ROWS; y++) {
      for (let x = 0; x < COLS; x++) {
        if (this.maze[y][x] === 1) this.wallRects.push(GameField.rectOf(x, y));
      }
    }
    this.board = new Rect(0, HUD_H, COLS * CELL, ROWS * CELL); // всё поле целиком
  }

  // ---------- Клетки и координаты ----------
  static rectOf(x, y) { return new Rect(x * CELL, HUD_H + y * CELL, CELL, CELL); }

  // Можно ли стоять в клетке (внутри поля и не стена) — как is_free в Python
  isFree(x, y) {
    return x >= 0 && x < COLS && y >= 0 && y < ROWS && this.maze[y][x] === 0;
  }

  // Что находится в клетке: 'out' — за полем, 'wall' — стена, 'free' — проход
  cellAt(x, y) {
    if (x < 0 || x >= COLS || y < 0 || y >= ROWS) return 'out';
    return this.maze[y][x] === 1 ? 'wall' : 'free';
  }

  // По пикселю находим клетку (через collidepoint)
  cellAtPoint(px, py) {
    if (!this.board.collidepoint(px, py)) return null;
    return [Math.floor(px / CELL), Math.floor((py - HUD_H) / CELL)];
  }

  // Врезается ли прямоугольник в стену или вылезает за поле
  hitsWall(rect) {
    const inside = rect.x >= this.board.x && rect.y >= this.board.y &&
      rect.x + rect.w <= this.board.x + this.board.w &&
      rect.y + rect.h <= this.board.y + this.board.h;
    return !inside || this.wallRects.some((w) => rect.colliderect(w));
  }

  freeCells() {
    const cells = [];
    for (let y = 0; y < ROWS; y++) {
      for (let x = 0; x < COLS; x++) if (this.maze[y][x] === 0) cells.push([x, y]);
    }
    return cells;
  }

  // ---------- Поиск в ширину (BFS) — тот же алгоритм, что bfs_map в Python ----------
  bfsMap(start, blocked = []) {
    const block = new Set(blocked.map(([x, y]) => cellKey(x, y)));
    const dist = new Map([[cellKey(...start), 0]]);    // клетка -> шагов от старта
    const prev = new Map([[cellKey(...start), null]]); // клетка -> откуда пришли
    const cells = new Map([[cellKey(...start), start]]);
    const queue = [start];
    let head = 0; // вместо deque: просто двигаем «голову» очереди
    while (head < queue.length) {
      const cur = queue[head++];
      for (const [dx, dy] of DIRS) {
        const nxt = [cur[0] + dx, cur[1] + dy];
        const k = cellKey(...nxt);
        if (dist.has(k) || block.has(k) || !this.isFree(...nxt)) continue;
        dist.set(k, dist.get(cellKey(...cur)) + 1);
        prev.set(k, cur);
        cells.set(k, nxt);
        queue.push(nxt);
      }
    }
    return { dist, prev, cells };
  }

  // Первая клетка пути: идём от цели назад по «родителям» до соседа старта
  firstStep(prev, start, target) {
    let cur = target;
    const startKey = cellKey(...start);
    while (cellKey(...prev.get(cellKey(...cur))) !== startKey) {
      cur = prev.get(cellKey(...cur));
    }
    return cur;
  }

  // Первый шаг к ближайшей цели из списка targets (null — никуда не дойти)
  bfsPathFirstStep(start, targets, blocked = []) {
    const { dist, prev } = this.bfsMap(start, blocked);
    let nearest = null;
    let best = Infinity;
    for (const t of targets) {
      const k = cellKey(...t);
      if (!dist.has(k) || k === cellKey(...start)) continue;
      if (dist.get(k) < best) { best = dist.get(k); nearest = t; } // строго <, как min() в Python
    }
    return nearest ? this.firstStep(prev, start, nearest) : null;
  }

  // ---------- Уровень: значения по умолчанию, проверка, JSON ----------
  static defaultLevel() {
    return {
      name: DEFAULT_LEVEL_NAME,
      maze: MAZE_STR.map((row) => [...row].map(Number)),
      ghostStart: [...GHOST_START],
      pacStart: [...PAC_START],
      pacDelay: PAC_DELAY,
      fleeDist: FLEE_DIST,
      fleeExit: FLEE_EXIT,
      isDefault: true,
    };
  }

  // Проверка стартовой клетки: [x, y] из целых, внутри поля, не стена
  static _checkCell(maze, value, what) {
    if (!Array.isArray(value) || value.length !== 2 || !value.every(isInt)) {
      throw new LevelError(`${what}: нужна пара целых чисел [x, y], а не ${JSON.stringify(value)}`);
    }
    const [x, y] = value;
    if (!(x >= 0 && x < COLS && y >= 0 && y < ROWS)) {
      throw new LevelError(`${what}: клетка [${value}] вне поля ${COLS}x${ROWS}`);
    }
    if (maze[y][x] !== 0) throw new LevelError(`${what}: клетка [${value}] - это стена`);
    return [x, y];
  }

  // Есть ли проход от start до target (обход по клеткам)
  static _reachable(maze, start, target) {
    const seen = new Set([cellKey(...start)]);
    const stack = [start];
    while (stack.length) {
      const [x, y] = stack.pop();
      if (x === target[0] && y === target[1]) return true;
      for (const [dx, dy] of DIRS) {
        const nx = x + dx; const ny = y + dy;
        if (nx >= 0 && nx < COLS && ny >= 0 && ny < ROWS && maze[ny][nx] === 0 &&
            !seen.has(cellKey(nx, ny))) {
          seen.add(cellKey(nx, ny));
          stack.push([nx, ny]);
        }
      }
    }
    return false;
  }

  // Те же правила, что validate_level в Python (storage.py). Ошибка -> LevelError
  static validate(data) {
    if (data === null || typeof data !== 'object' || Array.isArray(data)) {
      throw new LevelError('корень файла должен быть объектом {...}');
    }
    for (const key of ['maze', 'ghost', 'pacman']) {
      if (!(key in data)) throw new LevelError(`нет обязательного ключа "${key}"`);
    }
    const maze = data.maze;
    if (!Array.isArray(maze) || maze.length !== ROWS) {
      throw new LevelError(`"maze" должен содержать ${ROWS} рядов`);
    }
    maze.forEach((row, y) => {
      if (!Array.isArray(row) || row.length !== COLS) {
        throw new LevelError(`в ряду ${y} должно быть ${COLS} клеток (ширина лабиринта)`);
      }
      row.forEach((cell, x) => {
        if (cell !== 0 && cell !== 1) { // true/false и "1" тоже не подходят
          throw new LevelError(`клетка (${x}, ${y}) = ${JSON.stringify(cell)}, а нужно 0 или 1`);
        }
      });
    });
    const { ghost, pacman } = data;
    const isObj = (o) => o !== null && typeof o === 'object' && !Array.isArray(o);
    if (!isObj(ghost) || !isObj(pacman)) {
      throw new LevelError('"ghost" и "pacman" должны быть объектами {...}');
    }
    const ghostStart = GameField._checkCell(maze, ghost.start, 'ghost.start');
    const pacStart = GameField._checkCell(maze, pacman.start, 'pacman.start');
    if (ghostStart[0] === pacStart[0] && ghostStart[1] === pacStart[1]) {
      throw new LevelError('призрак и Пакман стоят в одной клетке');
    }
    if (!GameField._reachable(maze, ghostStart, pacStart)) {
      throw new LevelError('призрак не может дойти до Пакмана - нет прохода');
    }
    const free = maze.flat().filter((c) => c === 0).length;
    if (free <= 2) throw new LevelError('в лабиринте нет места для еды');

    // Необязательные настройки: нет ключа — берём значение по умолчанию
    const settings = {};
    for (const [key, def] of [['delay', PAC_DELAY], ['flee_dist', FLEE_DIST], ['flee_exit', FLEE_EXIT]]) {
      const value = key in pacman ? pacman[key] : def;
      if (!isNumber(value) || value <= 0) {
        throw new LevelError(`pacman.${key} должен быть положительным числом`);
      }
      settings[key] = value;
    }
    if (settings.flee_exit < settings.flee_dist) {
      throw new LevelError('pacman.flee_exit не может быть меньше flee_dist');
    }
    return {
      name: 'name' in data ? String(data.name) : 'Без названия',
      maze: maze.map((row) => [...row]),
      ghostStart,
      pacStart,
      pacDelay: settings.delay,
      fleeDist: settings.flee_dist,
      fleeExit: settings.flee_exit,
      isDefault: false,
    };
  }

  // Текст JSON -> поле. Ошибки разбора превращаем в LevelError
  static fromJSON(text) {
    let config;
    try {
      config = JSON.parse(text);
    } catch (e) {
      throw new LevelError(`Ошибка парсинга JSON: ${e.message}`);
    }
    return new GameField(GameField.validate(config));
  }

  // Как load_level в Python: при любой ошибке — уровень по умолчанию, игра не падает
  static load(text) {
    try {
      return { field: GameField.fromJSON(text), error: null };
    } catch (e) {
      if (!(e instanceof LevelError)) throw e; // чужие ошибки не прячем
      return { field: new GameField(GameField.defaultLevel()), error: e.message };
    }
  }
}
