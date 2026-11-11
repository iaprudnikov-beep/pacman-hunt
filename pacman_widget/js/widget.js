// js/widget.js — главный модуль виджета: связывает ядро (ЛР 4), цикл, ввод, отрисовку и HUD
// Ядро НЕ копируется: импортируем его из ../pacman_js/js (ES-модули)
import { RESULT } from '../../pacman_js/js/constants.js';
import { GameField } from '../../pacman_js/js/gameField.js';
import { Game } from '../../pacman_js/js/game.js';
import { Effect } from '../../pacman_js/js/effect.js';
import { FixedStepLoop, STEP_MS } from './loop.js';
import { Input } from './input.js';
import { Renderer } from './renderer.js';
import { Indicators } from './indicators.js';
import { Hud } from './hud.js';
import { VISION_CELLS } from './palette.js';
import { createScenarios } from './scenarios.js';

const GHOST_STEP_FRAMES = 10; // при зажатой клавише призрак шагает раз в 10 шагов (~170 мс, как в Pygame)

export class Widget {
  constructor(canvas, field) {
    this.field = field;
    this.game = new Game(field);
    this.settings = { fog: true, visionCells: VISION_CELLS, paused: false };
    this.mode = 'menu';            // 'menu' — стартовый экран, 'play' — игра
    this.pops = [];                // вспышки съеденной еды (только картинка)
    this.indicators = new Indicators();
    this.moveTimer = 0;            // сколько шагов ждать до следующего шага призрака
    this.input = new Input(window);
    this.renderer = new Renderer(canvas, field);
    this.hud = new Hud(document);
    this.loop = new FixedStepLoop(() => this.step(), (now) => this.render(now));
    this.scenarios = createScenarios(this);
  }

  start() { this.loop.start(); }

  restart() {
    this.game.reset();
    this.indicators.reset();
    this.pops = [];
    this.mode = 'play';
    this.settings.paused = false;
  }

  // ---------- Один шаг логики (вызывается ровно 60 раз в секунду игрового времени) ----------
  step() {
    const inp = this.input;
    // одиночные нажатия читаем один раз за шаг (старые нажатия не «копятся»)
    const space = inp.consume('Space') || inp.consume('Enter');
    const once = { r: inp.consume('KeyR'), f: inp.consume('KeyF'), p: inp.consume('KeyP') };
    inp.pressed.clear();
    // клавиши тоже вызывают сценарии (способ 3 — из кода)
    if (once.r) this.scenarios.restart();
    if (once.f) this.scenarios.toggleFog();
    if (once.p) this.scenarios.pause();
    if (this.mode === 'menu') {
      if (space) this.restart();
      return;
    }
    if (this.settings.paused || this.game.result !== RESULT.PLAY) return;
    if (space) this.scenarios.boo();

    // направление из флагов: одно действие призрака за шаг, повтор раз в GHOST_STEP_FRAMES
    const k = inp.readInput();
    const dx = (k.right ? 1 : 0) - (k.left ? 1 : 0);
    const dy = dx !== 0 ? 0 : (k.down ? 1 : 0) - (k.up ? 1 : 0); // по диагонали не ходим
    if (dx === 0 && dy === 0) {
      this.moveTimer = 0;                  // отпустили — следующее нажатие сработает сразу
    } else if (this.moveTimer <= 0) {
      this.game.moveGhost(dx, dy);
      this.moveTimer = GHOST_STEP_FRAMES;
    } else {
      this.moveTimer -= 1;
    }

    const before = this.game.food.count;
    this.game.tick(STEP_MS);               // ядро: волны, шаг Пакмана, проверка конца
    if (this.game.food.count < before) {   // съел — маленькая вспышка
      const [x, y] = this.game.pacman.pos;
      this.pops.push(new Effect(x, y, 0.9));
    }
    for (const p of this.pops) p.update(STEP_MS / 4); // в 4 раза медленнее волны «Бу!»
    this.pops = this.pops.filter((p) => p.active);
    this.indicators.update(this.game, STEP_MS);
  }

  // ---------- Отрисовка (каждый кадр браузера) ----------
  render(now) {
    this.renderer.draw(this.game, {
      fog: this.settings.fog,
      visionPx: this.settings.visionCells * 40,
      pops: this.pops,
      indicators: this.indicators,
    }, now);
    this.hud.update(this, now);
  }
}

// ---------- Запуск страницы ----------
const text = await fetch('../pacman_hunt/data/level.json').then((r) => r.text()).catch(() => '');
const { field, error } = GameField.load(text);  // битый файл -> уровень по умолчанию
const widget = new Widget(document.getElementById('game'), field);
if (error) widget.game.log.add(0, 'warn', `Уровень не загружен: ${error}`);

// Способ 1: кнопки с атрибутом data-scenario (аргументы — в data-args как JSON-массив)
for (const btn of document.querySelectorAll('[data-scenario]')) {
  btn.addEventListener('click', () => {
    const args = btn.dataset.args ? JSON.parse(btn.dataset.args) : [];
    widget.scenarios[btn.dataset.scenario](...args);
    btn.blur(); // чтобы пробел не «нажимал» кнопку ещё раз
  });
}
// Способ 2: глобальный объект для консоли браузера
window.PacmanHunt = { widget, game: widget.game, scenarios: widget.scenarios };
console.log('PacmanHunt готов. Пример: PacmanHunt.scenarios.list()');
widget.start();
