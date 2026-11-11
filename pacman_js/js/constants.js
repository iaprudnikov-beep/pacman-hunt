// js/constants.js — все настройки игры в одном месте (аналог constants.py)

// ---------- Поле ----------
export const CELL = 40;        // размер клетки в пикселях
export const HUD_H = 40;       // высота верхней панели
export const COLS = 22;        // столбцов в лабиринте
export const ROWS = 15;        // рядов в лабиринте
export const WIDTH = COLS * CELL;          // 880
export const HEIGHT = ROWS * CELL + HUD_H; // 640

// Четыре направления: вправо, влево, вниз, вверх (тот же порядок, что в Python!)
export const DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1]];

// ---------- Пакман (значения по умолчанию, level.json может их поменять) ----------
export const PAC_DELAY = 0.2;  // секунд между шагами Пакмана
export const FLEE_DIST = 5;    // ближе этого (клетки) — Пакман убегает
export const FLEE_EXIT = 7;    // дальше или ровно столько — перестаёт убегать

// ---------- Формула угрозы ----------
// threat(d) = THREAT_0 * exp(-THREAT_DECAY * d)
export const THREAT_0 = 1.0;      // угроза, когда призрак стоит прямо на Пакмане
export const THREAT_DECAY = 0.3;  // как быстро угроза падает с расстоянием (1/клетка)
// Пороги ВЫВОДИМ из формулы, а не подбираем на глаз:
// порог входа = угроза на расстоянии FLEE_DIST, порог выхода = на FLEE_EXIT
export const FLEE_ENTER_THRESHOLD = THREAT_0 * Math.exp(-THREAT_DECAY * FLEE_DIST); // ≈ 0.223
export const FLEE_EXIT_THRESHOLD = THREAT_0 * Math.exp(-THREAT_DECAY * FLEE_EXIT);  // ≈ 0.122

// ---------- Действие призрака «Бу!» ----------
export const BOO_COOLDOWN_MS = 4000; // перезарядка «Бу!» — 4 секунды
export const BOO_RADIUS = 6;         // докуда долетает волна (клетки) при модификаторе 1
export const BOO_WAVE_SPEED = 12;    // скорость волны (клеток в секунду)
export const BOO_POWER_0 = 1.0;      // громкость «Бу!» у самого призрака
export const BOO_DECAY = 0.35;       // затухание громкости (1/клетка)
export const BOO_THRESHOLD = 0.25;   // Пакман пугается, если громкость >= порога
export const BOO_STUN_MS = 1200;     // сколько Пакман стоит испуганный
export const BOO_MOD_MAX = 0.5;      // модификатор растёт до 1.5 к концу игры

// ---------- Защита от застревания ----------
export const STUCK_WINDOW = 30;   // смотрим на последние 30 шагов
export const STUCK_FLEES = 3;     // 3 раза начал убегать за это время — застрял
export const BRAVE_STEPS = 12;    // столько шагов Пакман «смелый»
export const BRAVE_FLEE_DIST = 2; // смелый убегает, только если призрак ближе 2 клеток

// ---------- Состояния конечного автомата ----------
// Object.freeze — объект нельзя изменить: STATE.CHASE = 'x' ничего не сделает
export const STATE = Object.freeze({
  CHASE: 'Chase',   // ищет еду (основное поведение)
  FLEE: 'Flee',     // убегает от призрака (реакция на угрозу)
  RETURN: 'Return', // возвращается к еде, к которой шёл до бегства
});

// Итог игры
export const RESULT = Object.freeze({ PLAY: 'play', WIN: 'win', LOSE: 'lose' });

// ---------- Уровень по умолчанию (запасной, как MAZE_STR в Python) ----------
export const MAZE_STR = [
  '1111111111111111111111',
  '1000000000110000000001',
  '1011110111110111101101',
  '1000000000000000000001',
  '1011010111111101101101',
  '1000010000110000100001',
  '1111011110110111101111',
  '1000000000000000000001',
  '1011110111111011110101',
  '1000010000110000100001',
  '1110010111111010100111',
  '1000000000110000000001',
  '1011110110110110111101',
  '1000000000000000000001',
  '1111111111111111111111',
];
export const GHOST_START = [1, 1];
export const PAC_START = [COLS - 2, ROWS - 2];
export const DEFAULT_LEVEL_NAME = 'Уровень по умолчанию';

// Ключ клетки для Map/Set: [3, 5] -> "3,5" (массивы в JS сравниваются по ссылке)
export const cellKey = (x, y) => `${x},${y}`;
