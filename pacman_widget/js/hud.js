// js/hud.js — показатели в ГОТОВЫХ HTML-элементах: меняем только textContent, узлы не создаём
import { STATE, RESULT, FLEE_ENTER_THRESHOLD, FLEE_EXIT_THRESHOLD } from '../../pacman_js/js/constants.js';
import { COLORS, rgba } from './palette.js';

const STATE_RU = { [STATE.CHASE]: 'ищет еду', [STATE.FLEE]: 'БЕГСТВО!', [STATE.RETURN]: 'возвращается' };

// Меняем текст только если он изменился — меньше работы браузеру
function setText(el, value) {
  const text = String(value);
  if (el.textContent !== text) el.textContent = text;
}

export class Hud {
  constructor(doc = document) {
    const $ = (id) => doc.getElementById(id);
    this.el = {
      eaten: $('hud-eaten'), bar: $('hud-bar'), mode: $('hud-mode'),
      state: $('st-state'), dist: $('st-dist'), threat: $('st-threat'), thresholds: $('st-thr'),
      boo: $('st-boo'), time: $('st-time'), steps: $('st-steps'), fps: $('st-fps'),
      fog: $('st-fog'), paused: $('st-paused'), log: $('log'),
      menu: $('menu'), menuLevel: $('menu-level'),
      result: $('result'), resTitle: $('res-title'), resInfo: $('res-info'),
    };
    setText(this.el.thresholds, `${FLEE_ENTER_THRESHOLD.toFixed(3)} / ${FLEE_EXIT_THRESHOLD.toFixed(3)}`);
  }

  update(w, nowMs) {
    const { game } = w;
    const e = this.el;
    const p = game.pacman;
    // Верхняя полоса — как HUD в Pygame
    setText(e.eaten, `Съедено ${game.food.eaten} / ${game.food.total}`);
    e.bar.style.width = `${(100 * game.food.eaten) / game.food.total}%`;
    setText(e.mode, `Пакман: ${STATE_RU[p.state]}`);
    if (p.state === STATE.FLEE) {          // мигание надписи, как blink в Pygame
      const blink = 160 + Math.round(95 * Math.abs(Math.sin((nowMs / 1000) * 8)));
      e.mode.style.color = `rgb(255, ${blink}, 60)`;
    } else {
      e.mode.style.color = rgba(COLORS.ACCENT);
    }
    // Боковая панель
    setText(e.state, p.state);
    setText(e.dist, p.ghostDistance(game.ghost.pos).toFixed(2));
    setText(e.threat, p.threatFrom(game.ghost.pos).toFixed(3));
    const left = game.ghost.cooldownLeft(game.timeMs);
    setText(e.boo, left > 0 ? `${(left / 1000).toFixed(1)} с` : 'готово');
    setText(e.time, `${(game.timeMs / 1000).toFixed(1)} с`);
    setText(e.steps, w.loop.steps);
    setText(e.fps, w.loop.fps);
    setText(e.fog, w.settings.fog ? `вкл, ${w.settings.visionCells} кл.` : 'выкл');
    setText(e.paused, w.settings.paused ? 'да' : 'нет');
    setText(e.log, game.log.last(8).map((ev) => `${(ev.timeMs / 1000).toFixed(1)} с | ${ev.text}`).join('\n'));
    // Экраны: меню и результат (показываем/прячем, текст — через textContent)
    e.menu.hidden = w.mode !== 'menu';
    setText(e.menuLevel, game.field.isDefault
      ? 'Файл уровня не загружен - используется уровень по умолчанию'
      : `Уровень: ${game.field.name}`);
    const over = game.result !== RESULT.PLAY;
    e.result.hidden = !over;
    if (over) {
      const win = game.result === RESULT.WIN;
      setText(e.resTitle, win ? 'ПАКМАН ПОЙМАН!' : 'ПОРАЖЕНИЕ');
      e.resTitle.className = win ? 'title win' : 'title lose';
      setText(e.resInfo, `${win ? 'Вы победили' : 'Пакман съел всю еду'}.  Время ${(game.timeMs / 1000).toFixed(1)} с,  съедено ${game.food.eaten} / ${game.food.total}`);
    }
  }
}
