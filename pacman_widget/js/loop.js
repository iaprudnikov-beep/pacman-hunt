// js/loop.js — игровой цикл: requestAnimationFrame + фиксированный шаг + накопитель
export const STEP_MS = 1000 / 60;  // один шаг логики = 16.67 мс (60 шагов в секунду)
export const MAX_DELTA_MS = 100;   // защита от «прыжка» после сворачивания вкладки

export class FixedStepLoop {
  constructor(onStep, onRender, stepMs = STEP_MS) {
    this.onStep = onStep;     // что делать на одном шаге логики
    this.onRender = onRender; // как нарисовать кадр
    this.stepMs = stepMs;
    this.accumulator = 0;     // накопитель: сколько времени ещё не «прошагали»
    this.last = null;         // время прошлого кадра
    this.timeScale = 1;       // 0.25 — замедление (сценарий slowMotion)
    this.steps = 0;           // сколько шагов сделано всего
    this.fps = 0;             // кадров браузера в секунду (для HUD)
    this._fpsFrames = 0;
    this._fpsTime = 0;
  }

  // Сколько шагов логики сделать за прошедшее время. Не зависит от браузера — можно тестировать
  advance(deltaMs) {
    const delta = Math.min(deltaMs, MAX_DELTA_MS) * this.timeScale;
    this.accumulator += delta;
    let done = 0;
    while (this.accumulator >= this.stepMs) { // шагаем равными кусочками
      this.onStep();
      this.accumulator -= this.stepMs;
      done += 1;
    }
    this.steps += done;
    return done;
  }

  // Один кадр браузера: посчитать время -> шаги логики -> отрисовка -> заказать следующий кадр
  frame(now) {
    const delta = this.last === null ? 0 : now - this.last;
    this.last = now;
    this.advance(delta);
    this._fpsFrames += 1;
    this._fpsTime += delta;
    if (this._fpsTime >= 500) { // FPS пересчитываем 2 раза в секунду
      this.fps = Math.round((this._fpsFrames * 1000) / this._fpsTime);
      this._fpsFrames = 0;
      this._fpsTime = 0;
    }
    this.onRender(now);
    requestAnimationFrame((t) => this.frame(t)); // браузер сам вызовет перед следующей перерисовкой
  }

  start() {
    requestAnimationFrame((t) => this.frame(t));
  }
}
