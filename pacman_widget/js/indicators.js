// js/indicators.js — анимированные значки над Пакманом, когда срабатывает его реакция
import { STATE } from '../../pacman_js/js/constants.js';

const LIFE_MS = 1400; // сколько живёт значок

// Какой значок показать при переходе в состояние
const MARKS = {
  [STATE.FLEE]: { text: '!', color: [255, 80, 110] },   // заметил призрака — убегает
  [STATE.RETURN]: { text: '?', color: [0, 230, 255] },  // «где моя еда?» — возвращается
  [STATE.CHASE]: { text: '♪', color: [255, 224, 40] },  // успокоился, ищет еду
};

export class Indicators {
  constructor() {
    this.items = [];        // активные значки: { text, color, ageMs }
    this.lastState = null;  // состояние Пакмана на прошлом шаге
    this.lastStuck = 0;     // сколько раз уже срабатывало «антизастревание»
  }

  reset() { this.items = []; this.lastState = null; this.lastStuck = 0; }

  add(text, color) { this.items.push({ text, color, ageMs: 0 }); }

  // Вызывается на каждом шаге: смотрим, не сменилось ли состояние Пакмана
  update(game, dtMs) {
    const state = game.pacman.state;
    if (this.lastState !== null && state !== this.lastState && MARKS[state]) {
      this.add(MARKS[state].text, MARKS[state].color);
    }
    this.lastState = state;
    const stuck = game.log.count('stuck');
    if (stuck > this.lastStuck) this.add('!?', [125, 255, 106]); // «смелый» режим
    this.lastStuck = stuck;
    for (const it of this.items) it.ageMs += dtMs;
    this.items = this.items.filter((it) => it.ageMs < LIFE_MS); // старые удаляем
  }

  // Доля прожитой жизни 0..1 — от неё зависят подъём, размер и прозрачность
  static progress(it) { return Math.min(1, it.ageMs / LIFE_MS); }
}
