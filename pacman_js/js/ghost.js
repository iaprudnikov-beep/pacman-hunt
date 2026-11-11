// js/ghost.js — призрак, которым управляет игрок
import { CELL, BOO_COOLDOWN_MS, BOO_RADIUS } from './constants.js';
import { GameField } from './gameField.js';
import { Effect } from './effect.js';

export class Ghost {
  constructor(start) {
    this.pos = [...start];                      // клетка [x, y]
    this.rect = GameField.rectOf(...start);     // прямоугольник в пикселях
    this.vis = [...start];                      // экранная позиция для плавного скольжения
    this.cooldown = BOO_COOLDOWN_MS;            // перезарядка «Бу!» в мс
    this.lastBooTime = -Infinity;               // когда кричал последний раз
  }

  // Шаг на одну клетку. Сначала «пробный» прямоугольник-копия, потом проверка стен
  move(dx, dy, field) {
    const newRect = this.rect.move(dx * CELL, dy * CELL); // копия, оригинал цел
    if (field.hitsWall(newRect)) return false;              // упёрлись в стену
    this.rect = newRect;                                    // ход подтверждён
    this.pos = [this.pos[0] + dx, this.pos[1] + dy];
    return true;
  }

  // Сколько мс осталось до следующего «Бу!» (0 — можно кричать)
  cooldownLeft(nowMs) {
    return Math.max(0, this.cooldown - (nowMs - this.lastBooTime));
  }

  // Действие «Бу!»: волна-эффект или null, если кулдаун ещё не прошёл
  boo(nowMs, modifier = 1) {
    if (nowMs - this.lastBooTime < this.cooldown) return null; // рано — защита от спама
    this.lastBooTime = nowMs;
    return new Effect(this.pos[0], this.pos[1], BOO_RADIUS * modifier, modifier);
  }

  // Плавное скольжение картинки к клетке (speed — клеток в секунду)
  animate(dtMs, speed = 8) {
    const step = speed * (dtMs / 1000);
    this.vis = this.vis.map((v, i) => {
      const diff = this.pos[i] - v;
      return Math.abs(diff) <= step ? this.pos[i] : v + Math.sign(diff) * step;
    });
  }
}
