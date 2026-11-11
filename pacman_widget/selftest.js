// selftest.js — проверка частей виджета без браузера: цикл, сценарии, индикаторы. Запуск: npm test
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { STATE, RESULT, BOO_COOLDOWN_MS } from '../pacman_js/js/constants.js';
import { GameField } from '../pacman_js/js/gameField.js';
import { Game } from '../pacman_js/js/game.js';
import { FixedStepLoop, STEP_MS, MAX_DELTA_MS } from './js/loop.js';
import { createScenarios, SCENARIO_INFO } from './js/scenarios.js';
import { Indicators } from './js/indicators.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const field = GameField.fromJSON(readFileSync(join(HERE, '..', 'pacman_hunt', 'data', 'level.json'), 'utf8'));

let passed = 0; let failed = 0;
function check(name, ok, detail = '') {
  if (ok) passed += 1; else failed += 1;
  console.log(`${ok ? '✅' : '❌'} ${passed + failed}. ${name}${detail ? ` — ${detail}` : ''}`);
}
const same = (a, b) => a[0] === b[0] && a[1] === b[1];

// «Виджет без экрана»: то же, что нужно сценариям, но без Canvas и DOM
function fakeWidget() {
  const w = {
    game: new Game(field),
    settings: { fog: true, visionCells: 6, paused: false },
    loop: new FixedStepLoop(() => {}, () => {}),
    restarted: 0,
    restart() { this.game.reset(); this.restarted += 1; },
  };
  w.scenarios = createScenarios(w);
  return w;
}

console.log('\n=== 1. Фиксированный шаг и накопитель ===');
let n = 0;
const loop = new FixedStepLoop(() => { n += 1; }, () => {});
check('шаг логики = 1000/60 ≈ 16.67 мс', Math.abs(STEP_MS - 16.6667) < 0.001);
loop.advance(1000);
check('кадр в 1000 мс (вкладка была свёрнута) режется до 100 мс: 5–6 шагов, а не 60', n >= 5 && n <= 6, `шагов ${n}`);
n = 0; loop.accumulator = 0;
for (let i = 0; i < 60; i++) loop.advance(1000 / 60);
const at60 = n;
n = 0; loop.accumulator = 0;
for (let i = 0; i < 144; i++) loop.advance(1000 / 144);
check('1 секунда: 60 Гц и 144 Гц дают одинаково ~60 шагов', Math.abs(at60 - 60) <= 1 && Math.abs(n - 60) <= 1, `${at60} и ${n}`);
n = 0; loop.accumulator = 0;
loop.advance(10);
check('кадр короче шага: шага нет, время копится в накопителе', n === 0 && Math.abs(loop.accumulator - 10) < 1e-9);
loop.advance(10);
check('следующий кадр «добирает» шаг', n === 1, `остаток ${loop.accumulator.toFixed(2)} мс`);
n = 0; loop.accumulator = 0; loop.timeScale = 0.25;
for (let i = 0; i < 60; i++) loop.advance(1000 / 60);
check('slowMotion 0.25: за секунду ~15 шагов', Math.abs(n - 15) <= 1, `${n}`);
check('MAX_DELTA_MS = 100', MAX_DELTA_MS === 100);

console.log('\n=== 2. Реестр сценариев ===');
const w = fakeWidget();
const s = w.scenarios;
check('все сценарии из таблицы — функции', Object.keys(SCENARIO_INFO).every((k) => typeof s[k] === 'function'),
  `${Object.keys(SCENARIO_INFO).length} шт.`);
check('list() возвращает имена всех сценариев', s.list().length === Object.keys(SCENARIO_INFO).length);
check('boo(): первая волна есть, вторая — кулдаун', s.boo() === true && s.boo() === false && w.game.effects.length === 1);
s.megaBoo(1.5);
check('megaBoo(): волна без кулдауна, радиус x1.5', w.game.effects.length === 2 && w.game.effects[1].maxRadius === 9);
s.scarePacman(3000);
check('scarePacman(3000): Пакман испуган', w.game.pacman.isStunned(w.game.timeMs + 2999));
s.forceFlee();
check('forceFlee(): состояние FLEE', w.game.pacman.state === STATE.FLEE);
s.calm();
check('calm(): снова CHASE', w.game.pacman.state === STATE.CHASE);
check('teleportGhost в стену не работает', s.teleportGhost(0, 0) === false && same(w.game.ghost.pos, [1, 1]));
s.teleportGhost(5, 3);
check('teleportGhost(5, 3): призрак и его прямоугольник перенесены',
  same(w.game.ghost.pos, [5, 3]) && w.game.ghost.rect.x === 200);
s.ghostNearPacman();
check('ghostNearPacman(): призрак в 3 шагах от Пакмана', w.game.field.bfsMap(w.game.pacman.pos).dist.get(w.game.ghost.pos.join(',')) === 3);
const fog = w.settings.fog;
s.toggleFog();
check('toggleFog() переключает туман', w.settings.fog === !fog);
s.setVision(10);
check('setVision(10)', w.settings.visionCells === 10);
s.slowMotion(0.5);
check('slowMotion(0.5) меняет скорость времени цикла', w.loop.timeScale === 0.5);
s.pacmanSpeed(0.1);
check('pacmanSpeed(0.1)', w.game.pacman.delay === 0.1);
check('pause() включает и выключает паузу', s.pause() === true && s.pause() === false);
s.lastFood();
check('lastFood(): осталась одна еда, всего по-прежнему 159', w.game.food.count === 1 && w.game.food.total === 159);
s.restart();
check('restart(): новая партия, 159 еды', w.restarted === 1 && w.game.food.count === 159 && w.game.result === RESULT.PLAY);
check('сценарии пишут в журнал игры', w.game.log.count('scenario') >= 8, `${w.game.log.count('scenario')} записей`);
const w2 = fakeWidget();
w2.scenarios.demo();
check('demo() вызывает другие сценарии (призрак рядом + волна + туман выкл)',
  w2.game.effects.length === 1 && w2.settings.fog === false);
const w3 = fakeWidget();
w3.scenarios.teleportGhost(...w3.game.pacman.pos);
check('призрак телепортировался на Пакмана — победа', w3.game.result === RESULT.WIN);

console.log('\n=== 3. Индикаторы реакций ===');
const ind = new Indicators();
const g = new Game(field);
ind.update(g, STEP_MS);
g.pacman._transitionTo(STATE.FLEE, 'тест');
ind.update(g, STEP_MS);
check('переход в FLEE -> значок «!»', ind.items.length === 1 && ind.items[0].text === '!');
g.pacman._transitionTo(STATE.RETURN, 'тест');
ind.update(g, STEP_MS);
check('переход в RETURN -> значок «?»', ind.items.at(-1).text === '?');
for (let i = 0; i < 100; i++) ind.update(g, STEP_MS);
check('значки живут 1.4 с и исчезают', ind.items.length === 0);
check('кулдаун «Бу!» из ядра = 4000 мс', BOO_COOLDOWN_MS === 4000);

console.log(`\nИтого: ${passed} ✅, ${failed} ❌ из ${passed + failed} проверок`);
if (failed > 0) process.exit(1);
