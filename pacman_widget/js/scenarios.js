// js/scenarios.js — реестр вызываемых сценариев: имя -> функция, меняющая состояние игры
// Сценарии НЕ рисуют и не знают про Canvas — только про игру и настройки виджета.
// Вызов: кнопки data-scenario, консоль (PacmanHunt.scenarios.boo()), клавиши и другие сценарии
import { STATE } from '../../pacman_js/js/constants.js';
import { Food } from '../../pacman_js/js/food.js';
import { GameField } from '../../pacman_js/js/gameField.js';

export const SCENARIO_INFO = {
  boo: '«Бу!» призрака (с кулдауном 4 с)',
  megaBoo: 'громкое «Бу!» без кулдауна, modifier = 1.5',
  scarePacman: 'Пакман замирает на ms миллисекунд',
  forceFlee: 'Пакман сразу убегает (FLEE)',
  calm: 'Пакман успокаивается (CHASE)',
  teleportGhost: 'призрак в клетку [x, y]',
  ghostNearPacman: 'призрак рядом с Пакманом (видно реакцию «!»)',
  lastFood: 'оставить одну еду — проверить антизастревание',
  toggleFog: 'включить/выключить туман',
  setVision: 'радиус видимости в клетках',
  slowMotion: 'скорость времени: 0.25 — замедление, 1 — норма',
  pacmanSpeed: 'пауза между шагами Пакмана (сек)',
  pause: 'пауза / продолжить',
  restart: 'новая партия',
  demo: 'цепочка: призрак рядом -> «Бу!» -> туман выкл',
  list: 'показать все сценарии в консоли',
};

export function createScenarios(widget) {
  const log = (text) => widget.game.log.add(widget.game.timeMs, 'scenario', `Сценарий: ${text}`);

  const scenarios = {
    boo() {
      const wave = widget.game.boo();
      log(wave ? '«Бу!»' : '«Бу!» ещё перезаряжается');
      return Boolean(wave);
    },
    megaBoo(modifier = 1.5) {
      widget.game.ghost.lastBooTime = -Infinity; // сбрасываем кулдаун
      const wave = widget.game.ghost.boo(widget.game.timeMs, modifier);
      widget.game.effects.push(wave);
      log(`громкое «Бу!» x${modifier}`);
      return wave;
    },
    scarePacman(ms = 2000) {
      widget.game.pacman.stunnedUntil = widget.game.timeMs + ms;
      log(`Пакман испуган на ${ms} мс`);
    },
    forceFlee() {
      const p = widget.game.pacman;
      p.returnTarget = p.target;               // как в ядре: запомнить, куда шёл
      p._transitionTo(STATE.FLEE, 'сценарий forceFlee');
    },
    calm() {
      widget.game.pacman._transitionTo(STATE.CHASE, 'сценарий calm');
    },
    teleportGhost(x, y) {
      const { game } = widget;
      if (!game.field.isFree(x, y)) { log(`клетка [${x}, ${y}] занята стеной`); return false; }
      game.ghost.pos = [x, y];
      game.ghost.vis = [x, y];
      game.ghost.rect = GameField.rectOf(x, y); // прямоугольник тоже переносим
      log(`призрак в [${x}, ${y}]`);
      game.checkEnd();
      return true;
    },
    ghostNearPacman() {
      const { game } = widget;
      const [px, py] = game.pacman.pos;
      // ищем свободную клетку в 3 шагах от Пакмана
      const { dist, cells } = game.field.bfsMap([px, py]);
      for (const [k, d] of dist) {
        if (d === 3) return scenarios.teleportGhost(...cells.get(k));
      }
      return false;
    },
    lastFood() {
      const { game } = widget;
      const keep = game.food.list().slice(-1);  // оставляем последнюю точку
      const total = game.food.total;
      game.food = new Food(keep);
      game.food.total = total;                  // для счётчика «съедено»
      log('осталась одна еда');
    },
    toggleFog() {
      widget.settings.fog = !widget.settings.fog;
      log(`туман ${widget.settings.fog ? 'включён' : 'выключен'}`);
      return widget.settings.fog;
    },
    setVision(cells = 6) {
      widget.settings.visionCells = Math.max(1, Number(cells));
      log(`радиус видимости ${widget.settings.visionCells} клеток`);
    },
    slowMotion(scale = 0.25) {
      widget.loop.timeScale = scale;
      log(`скорость времени x${scale}`);
    },
    pacmanSpeed(delaySec = 0.2) {
      widget.game.pacman.delay = delaySec;
      log(`Пакман шагает раз в ${delaySec} с`);
    },
    pause() {
      widget.settings.paused = !widget.settings.paused;
      return widget.settings.paused;
    },
    restart() {
      widget.restart();
    },
    demo() {                     // способ 3: сценарий вызывает другие сценарии
      scenarios.ghostNearPacman();
      scenarios.megaBoo();
      if (widget.settings.fog) scenarios.toggleFog();
    },
    list() {
      const rows = Object.entries(SCENARIO_INFO).map(([name, what]) => ({ name, what }));
      if (typeof window !== 'undefined') console.table(rows); // таблица в консоли браузера
      return rows.map((r) => r.name);
    },
  };
  return scenarios;
}
