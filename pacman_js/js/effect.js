// js/effect.js — волна «Бу!»: растёт от призрака и затухает
import { BOO_WAVE_SPEED } from './constants.js';

export class Effect {
  constructor(x, y, maxRadius, modifier = 1) {
    this.x = x;                 // центр волны (клетка, где был призрак)
    this.y = y;
    this.radius = 0;            // стартовый размер
    this.maxRadius = maxRadius; // докуда долетит
    this.modifier = modifier;   // во сколько раз громче обычного
    this.active = true;         // жизненный цикл: активна -> завершена
    this.hitPacman = false;     // уже задела Пакмана (чтобы не пугать дважды)
  }

  // Один шаг жизни волны: dtMs — сколько миллисекунд прошло
  update(dtMs) {
    if (!this.active) return;
    this.radius += BOO_WAVE_SPEED * (dtMs / 1000);
    if (this.radius >= this.maxRadius) {
      this.radius = this.maxRadius;
      this.active = false; // волна дошла до края и исчезла
    }
  }

  // Прозрачность для рисования: 1 в начале, 0 в конце (геттер = @property)
  get alpha() {
    return Math.max(0, 1 - this.radius / this.maxRadius);
  }

  // Статический метод (= @staticmethod): затухание без this
  static decay(k, d) {
    return Math.exp(-k * d);
  }
}
