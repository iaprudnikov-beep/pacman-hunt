// js/pacman.js — Пакман под управлением ИИ: конечный автомат CHASE / FLEE / RETURN
import {
  STATE, DIRS, PAC_DELAY, FLEE_DIST, FLEE_EXIT, BOO_STUN_MS,
  STUCK_WINDOW, STUCK_FLEES, BRAVE_STEPS, BRAVE_FLEE_DIST,
} from './constants.js';
import { Physics } from './physics.js';

const same = (a, b) => a !== null && b !== null && a[0] === b[0] && a[1] === b[1];

export class Pacman {
  constructor(start, { delay = PAC_DELAY, fleeDist = FLEE_DIST, fleeExit = FLEE_EXIT,
    antiStuck = true } = {}) {
    this.pos = [...start];           // клетка [x, y]
    this.vis = [...start];           // экранная позиция (для плавного скольжения)
    this.direction = [1, 0];         // куда смотрит (для рта на картинке)
    this.state = STATE.CHASE;        // начинаем с поиска еды
    this.delay = delay;              // секунд между шагами
    this.fleeDist = fleeDist;
    this.fleeExit = fleeExit;
    // Пороги угрозы выводим из формулы: угроза на расстоянии fleeDist и fleeExit
    this.enterThreshold = Physics.threat(fleeDist); // выше — начинаем убегать
    this.exitThreshold = Physics.threat(fleeExit);  // ниже или равно — хватит убегать
    this.target = null;              // к какой еде идёт сейчас
    this.returnTarget = null;        // ТОЧКА ВОЗВРАТА: еда, к которой шёл до бегства
    this.stunnedUntil = 0;           // до какого момента стоит испуганный («Бу!»)
    this.steps = 0;                  // сколько шагов сделал
    this.antiStuck = antiStuck;      // включена ли защита от застревания
    this.fleeStarts = [];            // номера шагов, когда начинал убегать
    this.braveSteps = 0;             // сколько ещё шагов «смелый»
    this.onEvent = () => {};         // сюда игра подключает журнал событий
  }

  // ---------- Расчёты ----------
  ghostDistance(ghostPos) { return Physics.distance(this.pos, ghostPos); }

  threatFrom(ghostPos) { return Physics.threat(this.ghostDistance(ghostPos)); }

  // Порог входа в бегство. Смелый Пакман убегает только совсем вблизи
  get currentEnterThreshold() {
    return this.braveSteps > 0 ? Physics.threat(BRAVE_FLEE_DIST) : this.enterThreshold;
  }

  isStunned(nowMs) { return nowMs < this.stunnedUntil; }

  // Испугался «Бу!» — стоит на месте BOO_STUN_MS миллисекунд
  scare(nowMs) { this.stunnedUntil = nowMs + BOO_STUN_MS; }

  // ---------- Конечный автомат ----------
  _transitionTo(newState, reason) {
    const old = this.state;
    this.state = newState;
    this.onEvent('state', `Пакман [${this.pos}]: ${old} -> ${newState} (${reason})`);
  }

  // Проверяем угрозу и при необходимости меняем состояние
  updateState(ghostPos, food) {
    const t = this.threatFrom(ghostPos);
    const d = this.ghostDistance(ghostPos).toFixed(1);
    switch (this.state) {
      case STATE.CHASE:
        if (t > this.currentEnterThreshold) {
          this.returnTarget = this.target;   // запоминаем, куда шли
          this._transitionTo(STATE.FLEE, `угроза ${t.toFixed(3)}, расстояние ${d}`);
          this._checkStuck();
        }
        break;
      case STATE.FLEE:
        if (t <= this.exitThreshold) {
          const canReturn = this.returnTarget && food.has(this.returnTarget);
          this._transitionTo(canReturn ? STATE.RETURN : STATE.CHASE,
            `оторвался, угроза ${t.toFixed(3)}`);
        }
        break;
      case STATE.RETURN:
        if (t > this.currentEnterThreshold) {
          this._transitionTo(STATE.FLEE, `снова опасно, угроза ${t.toFixed(3)}`);
          this._checkStuck();
        } else if (!this.returnTarget || !food.has(this.returnTarget)) {
          this._transitionTo(STATE.CHASE, 'прерванной цели больше нет');
        }
        break;
      default:
        break;
    }
  }

  // Защита от застревания: слишком часто начинает убегать — значит, ходит по кругу
  _checkStuck() {
    if (!this.antiStuck) return;
    this.fleeStarts.push(this.steps);
    this.fleeStarts = this.fleeStarts.filter((s) => this.steps - s < STUCK_WINDOW);
    if (this.fleeStarts.length >= STUCK_FLEES) {
      this.fleeStarts = [];
      this.braveSteps = BRAVE_STEPS; // несколько шагов почти не боится
      this.state = this.returnTarget ? STATE.RETURN : STATE.CHASE;
      this.onEvent('stuck', `Пакман [${this.pos}] застрял в цикле -> смелый на ${BRAVE_STEPS} шагов`);
    }
  }

  // ---------- Шаги ----------
  // Бегство: та же логика, что _flee_step в Python
  _fleeStep(ghostPos, field) {
    const gd = field.bfsMap(ghostPos).dist;                  // расстояния от призрака
    const { dist: pd, prev, cells } = field.bfsMap(this.pos, [ghostPos]); // от Пакмана
    let best = null;
    let bestScore = -1e9;
    for (const [k, myDist] of pd) {        // Map перебирается в порядке BFS, как dict
      const cell = cells.get(k);
      if (same(cell, this.pos)) continue;
      const g = gd.has(k) ? gd.get(k) : 999;
      if (myDist < g) {                    // Пакман успевает туда раньше призрака
        const score = g - 0.3 * myDist;    // подальше от призрака и поближе к себе
        if (score > bestScore) { best = cell; bestScore = score; }
      }
    }
    if (best) return field.firstStep(prev, this.pos, best);
    // безопасных клеток нет — шаг в соседнюю, самую далёкую от призрака
    let choice = null;
    let far = -Infinity;
    for (const [dx, dy] of DIRS) {
      const c = [this.pos[0] + dx, this.pos[1] + dy];
      if (!field.isFree(...c) || same(c, ghostPos)) continue;
      const g = gd.get(`${c[0]},${c[1]}`) ?? 0;
      if (g > far) { far = g; choice = c; }
    }
    return choice ?? this.pos;
  }

  // Поиск еды: шаг к ближайшей еде, обходя клетку призрака
  _chaseStep(ghostPos, food, field) {
    const { dist } = field.bfsMap(this.pos, [ghostPos]);
    this.target = null;
    let best = Infinity;
    for (const f of food.list()) {         // запоминаем цель — пригодится для возврата
      const d = dist.get(`${f[0]},${f[1]}`);
      if (d !== undefined && d > 0 && d < best) { best = d; this.target = f; }
    }
    return field.bfsPathFirstStep(this.pos, food.list(), [ghostPos]) ?? this.pos;
  }

  // Возврат: идём именно к той еде, к которой шли до бегства
  _returnStep(ghostPos, food, field) {
    const step = field.bfsPathFirstStep(this.pos, [this.returnTarget], [ghostPos]);
    return step ?? this._chaseStep(ghostPos, food, field);
  }

  // Один логический шаг. Возвращает true, если съел еду
  step(ghostPos, food, field) {
    const old = this.pos;
    this.updateState(ghostPos, food);
    switch (this.state) {
      case STATE.FLEE: this.pos = this._fleeStep(ghostPos, field); break;
      case STATE.RETURN: this.pos = this._returnStep(ghostPos, food, field); break;
      default: this.pos = this._chaseStep(ghostPos, food, field); break;
    }
    this.steps += 1;
    if (this.braveSteps > 0) this.braveSteps -= 1;
    if (!same(old, this.pos)) this.direction = [this.pos[0] - old[0], this.pos[1] - old[1]];
    if (food.eat(this.pos)) {
      if (this.state === STATE.RETURN && same(this.pos, this.returnTarget)) {
        this.returnTarget = null;
        this._transitionTo(STATE.CHASE, 'дошёл до прерванной цели');
      }
      return true;
    }
    return false;
  }

  // Плавное скольжение картинки к клетке
  animate(dtMs, speed = 7) {
    const st = speed * (dtMs / 1000);
    this.vis = this.vis.map((v, i) => {
      const diff = this.pos[i] - v;
      return Math.abs(diff) <= st ? this.pos[i] : v + Math.sign(diff) * st;
    });
  }
}
