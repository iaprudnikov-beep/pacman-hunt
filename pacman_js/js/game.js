// js/game.js — игра без отрисовки: «ввод -> обновление -> проверка конца»
import { RESULT, BOO_MOD_MAX, BOO_THRESHOLD } from './constants.js';
import { Ghost } from './ghost.js';
import { Pacman } from './pacman.js';
import { Food } from './food.js';
import { Physics } from './physics.js';
import { EventLog } from './eventLog.js';

export class Game {
  constructor(field, { log = new EventLog(), antiStuck = true } = {}) {
    this.field = field;
    this.log = log;
    this.antiStuck = antiStuck;
    this.reset();
  }

  reset() {
    const f = this.field;
    this.ghost = new Ghost(f.ghostStart);
    this.pacman = new Pacman(f.pacStart, {
      delay: f.pacDelay, fleeDist: f.fleeDist, fleeExit: f.fleeExit, antiStuck: this.antiStuck,
    });
    this.pacman.onEvent = (type, text) => this.log.add(this.timeMs, type, text);
    this.food = Food.fromField(f);
    this.effects = [];          // активные волны «Бу!»
    this.timeMs = 0;            // свои «игровые часы» (в Node нет performance.now у игры)
    this.pacTimer = 0;          // мс до следующего шага Пакмана
    this.result = RESULT.PLAY;
    this.log.add(0, 'start', `Уровень «${f.name}», еды ${this.food.total}`);
  }

  // Модификатор «Бу!»: чем меньше еды осталось, тем громче (от 1 до 1.5)
  get booModifier() {
    return 1 + BOO_MOD_MAX * (this.food.eaten / this.food.total);
  }

  // ---------- Ввод ----------
  moveGhost(dx, dy) {
    if (this.result !== RESULT.PLAY) return false;
    const old = this.ghost.pos;
    const moved = this.ghost.move(dx, dy, this.field);
    if (moved) this.log.add(this.timeMs, 'ghost', `призрак [${old}] -> [${this.ghost.pos}]`);
    this.checkEnd();
    return moved;
  }

  boo() {
    if (this.result !== RESULT.PLAY) return null;
    const effect = this.ghost.boo(this.timeMs, this.booModifier);
    if (!effect) {
      this.log.add(this.timeMs, 'cooldown', `«Бу!» ещё ${this.ghost.cooldownLeft(this.timeMs)} мс`);
      return null;
    }
    this.effects.push(effect);
    this.log.add(this.timeMs, 'boo', `«Бу!» x${effect.modifier.toFixed(2)}, радиус ${effect.maxRadius.toFixed(1)}`);
    return effect;
  }

  // ---------- Обновление ----------
  tick(dtMs) {
    if (this.result !== RESULT.PLAY) return;
    this.timeMs += dtMs;
    this._updateEffects(dtMs);
    this.pacTimer -= dtMs;
    if (this.pacTimer <= 0) {                     // пора делать шаг
      this.pacTimer = this.pacman.delay * 1000;
      if (!this.pacman.isStunned(this.timeMs)) {
        if (this.pacman.step(this.ghost.pos, this.food, this.field)) {
          this.log.add(this.timeMs, 'eat', `съедено в [${this.pacman.pos}], осталось ${this.food.count}`);
        }
      }
    }
    this.ghost.animate(dtMs);
    this.pacman.animate(dtMs);
    this.checkEnd();
  }

  // Волны растут; когда волна дошла до Пакмана — считаем громкость и сравниваем с порогом
  _updateEffects(dtMs) {
    for (const e of this.effects) {
      e.update(dtMs);
      const d = Physics.distance([e.x, e.y], this.pacman.pos);
      if (!e.hitPacman && d <= e.radius) {
        e.hitPacman = true;
        const loud = Physics.booLoudness(d, e.modifier);
        if (loud >= BOO_THRESHOLD) {
          this.pacman.scare(this.timeMs);
          this.log.add(this.timeMs, 'scared', `Пакман испугался: громкость ${loud.toFixed(3)}`);
        } else {
          this.log.add(this.timeMs, 'quiet', `волна дошла, но тихо: ${loud.toFixed(3)}`);
        }
      }
    }
    this.effects = this.effects.filter((e) => e.active);
  }

  // Один кадр целиком: ввод -> обновление -> проверка конца
  update(dtMs, input = {}) {
    if (input.dx || input.dy) this.moveGhost(input.dx ?? 0, input.dy ?? 0);
    if (input.boo) this.boo();
    this.tick(dtMs);
    return this.result;
  }

  // ---------- Конец игры ----------
  checkEnd() {
    if (this.result !== RESULT.PLAY) return this.result;
    const [g, p] = [this.ghost.pos, this.pacman.pos];
    if (g[0] === p[0] && g[1] === p[1]) {
      this.result = RESULT.WIN;  // призрак поймал Пакмана
      this.log.add(this.timeMs, 'end', `Победа за ${(this.timeMs / 1000).toFixed(1)} с`);
    } else if (this.food.count === 0) {
      this.result = RESULT.LOSE; // Пакман съел всю еду
      this.log.add(this.timeMs, 'end', 'Поражение: еда кончилась');
    }
    return this.result;
  }
}
