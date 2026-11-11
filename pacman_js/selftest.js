// selftest.js — самопроверка ядра в Node.js без браузера. Запуск: npm test
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  STATE, RESULT, THREAT_0, THREAT_DECAY, FLEE_ENTER_THRESHOLD, FLEE_EXIT_THRESHOLD,
  BOO_COOLDOWN_MS, BOO_RADIUS, BOO_THRESHOLD, BOO_STUN_MS,
} from './js/constants.js';
import { Rect } from './js/rect.js';
import { Physics } from './js/physics.js';
import { Effect } from './js/effect.js';
import { Food } from './js/food.js';
import { LevelError } from './js/levelError.js';
import { GameField } from './js/gameField.js';
import { Ghost } from './js/ghost.js';
import { Pacman } from './js/pacman.js';
import { EventLog } from './js/eventLog.js';
import { Game } from './js/game.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const LEVEL_TEXT = readFileSync(join(HERE, '..', 'pacman_hunt', 'data', 'level.json'), 'utf8');
const PARITY = JSON.parse(readFileSync(join(HERE, 'tests', 'parity_cases.json'), 'utf8'));
const field = GameField.fromJSON(LEVEL_TEXT);

let passed = 0;
let failed = 0;
let section = '';
function check(name, ok, detail = '') {
  if (ok) passed += 1; else failed += 1;
  console.log(`${ok ? '✅' : '❌'} ${passed + failed}. ${name}${detail ? ` — ${detail}` : ''}`);
}
function title(t) { section = t; console.log(`\n=== ${section} ===`); }
const near = (a, b, eps = 1e-9) => Math.abs(a - b) < eps;
const same = (a, b) => a[0] === b[0] && a[1] === b[1];
// Пакман в клетке pos, призрак в ghost; один вызов updateState
function stateAfter(startState, pos, ghost, food = new Food([[1, 1]])) {
  const p = new Pacman(pos);
  p.state = startState;
  p.returnTarget = [1, 1];
  p.updateState(ghost, food);
  return p;
}

// ---------------------------------------------------------------
title('1. Геометрия: класс Rect');
const r = new Rect(10, 20, 40, 40);
check('центр прямоугольника считается верно', same(r.center, [30, 40]), `center = [${r.center}]`);
const moved = r.move(5, 0);
check('move() возвращает НОВЫЙ объект, оригинал не изменился', moved !== r && r.x === 10 && moved.x === 15);
check('colliderect: пересекающиеся прямоугольники', r.colliderect(new Rect(40, 50, 10, 10)));
check('colliderect: касание краями — не столкновение', !r.colliderect(new Rect(50, 20, 10, 10)));
check('collidepoint: точка внутри — да, на правом краю — нет', r.collidepoint(10, 20) && !r.collidepoint(50, 30));

// ---------------------------------------------------------------
title('2. Формулы: расстояние и угроза');
check('distance([0,0],[3,4]) = 5 (Пифагор)', Physics.distance([0, 0], [3, 4]) === 5);
check('threat(0) = THREAT_0 (угроза у самого призрака)', Physics.threat(0) === THREAT_0, `${Physics.threat(0)}`);
check('threat(10) = e^-3 ≈ 0.0498', near(Physics.threat(10), Math.exp(-3)), Physics.threat(10).toFixed(4));
const mono = [0, 1, 2, 5, 7, 10, 20].map((d) => Physics.threat(d));
check('угроза убывает с расстоянием (монотонность)', mono.every((v, i) => i === 0 || v < mono[i - 1]));
const dEnter = Physics.limitDistance(FLEE_ENTER_THRESHOLD);
const dExit = Physics.limitDistance(FLEE_EXIT_THRESHOLD);
check('из порога входа выводится граница ровно 5 клеток', near(dEnter, 5),
  `порог ${FLEE_ENTER_THRESHOLD.toFixed(4)} -> d = ${dEnter.toFixed(6)}`);
check('из порога выхода выводится граница ровно 7 клеток', near(dExit, 7),
  `порог ${FLEE_EXIT_THRESHOLD.toFixed(4)} -> d = ${dExit.toFixed(6)}`);
check('порог входа больше порога выхода (гистерезис)', FLEE_ENTER_THRESHOLD > FLEE_EXIT_THRESHOLD);
check('если удвоить коэффициент затухания, граница станет вдвое меньше (2.5)',
  near(Physics.limitDistance(FLEE_ENTER_THRESHOLD, THREAT_DECAY * 2), 2.5));
check('граница «Бу!»: ≈ 3.96 клетки, при модификаторе 1.5 — дальше',
  near(Physics.booLimit(1), Math.log(1 / BOO_THRESHOLD) / 0.35) && Physics.booLimit(1.5) > Physics.booLimit(1),
  `${Physics.booLimit(1).toFixed(2)} и ${Physics.booLimit(1.5).toFixed(2)}`);

// ---------------------------------------------------------------
title('3. Константы и эффекты');
let frozen = false;
try { STATE.CHASE = 'Опечатка'; } catch (e) { frozen = e instanceof TypeError; }
check('STATE заморожен (Object.freeze): изменить нельзя', frozen && STATE.CHASE === 'Chase');
const wave = new Effect(0, 0, 6);
wave.update(250);
const midAlpha = wave.alpha;
check('волна растёт: за 250 мс радиус 3 клетки', near(wave.radius, 3) && near(midAlpha, 0.5), `radius = ${wave.radius}`);
wave.update(1000);
check('жизненный цикл: волна дошла до края и стала неактивной', !wave.active && wave.alpha === 0);
check('статический метод Effect.decay(k, d) = e^(-k*d)', near(Effect.decay(0.5, 2), Math.exp(-1)));

// ---------------------------------------------------------------
title('4. Уровень из JSON и валидация');
check('level.json загружен: «Классический лабиринт», 22x15',
  field.name === 'Классический лабиринт' && field.maze.length === 15 && field.maze[0].length === 22);
check('еды на уровне 159 (все проходы минус 2 старта)', Food.fromField(field).total === PARITY.food, `${Food.fromField(field).total}`);
let parseErr = null;
try { GameField.fromJSON('{"maze": [1, 2,'); } catch (e) { parseErr = e; }
check('сломанный JSON -> LevelError «Ошибка парсинга JSON»',
  parseErr instanceof LevelError && parseErr.message.startsWith('Ошибка парсинга JSON'));
const fallback = GameField.load('это не json');
check('при ошибке load() даёт уровень по умолчанию и не падает',
  fallback.field.isDefault && fallback.error !== null, fallback.field.name);
const vBad = PARITY.validation.filter((v) => {
  let ok = true;
  try { GameField.validate(v.data); } catch (e) { if (e instanceof LevelError) ok = false; else throw e; }
  return ok !== v.ok;
});
check(`валидация совпадает с Python на ${PARITY.validation.length} уровнях`, vBad.length === 0,
  vBad.map((v) => v.name).join(', '));
check('cellAt: стена, проход и «за полем»',
  field.cellAt(0, 0) === 'wall' && field.cellAt(1, 1) === 'free' && field.cellAt(-1, 3) === 'out');
check('cellAtPoint: пиксель (45, 85) -> клетка [1, 1]', same(field.cellAtPoint(45, 85), [1, 1]));

// ---------------------------------------------------------------
title('5. Призрак: стены, «Бу!» и кулдаун');
const gh = new Ghost([1, 1]);
check('шаг в стену не делается, призрак стоит на месте', !gh.move(0, -1, field) && same(gh.pos, [1, 1]));
check('шаг в проход делается', gh.move(1, 0, field) && same(gh.pos, [2, 1]));
const e1 = gh.boo(0);
const e2 = gh.boo(1000);
const leftAt1s = gh.cooldownLeft(1000);
const e3 = gh.boo(BOO_COOLDOWN_MS);
check('кулдаун: «Бу!» -> через 1 с нельзя -> через 4 с снова можно', e1 && e2 === null && e3,
  `через 1 с осталось ${leftAt1s} мс`);
check('модификатор 1.5 увеличивает радиус волны', gh.boo(99999, 1.5).maxRadius === BOO_RADIUS * 1.5);

// ---------------------------------------------------------------
title('6. Конечный автомат Пакмана (CHASE / FLEE / RETURN)');
check('CHASE -> FLEE: призрак на расстоянии 4 (угроза выше порога)',
  stateAfter(STATE.CHASE, [10, 7], [14, 7]).state === STATE.FLEE);
check('ровно на границе 5 клеток Пакман ещё НЕ убегает',
  stateAfter(STATE.CHASE, [10, 7], [13, 11]).state === STATE.CHASE);
check('гистерезис: на расстоянии 6 продолжает убегать',
  stateAfter(STATE.FLEE, [10, 7], [16, 7]).state === STATE.FLEE);
check('FLEE -> RETURN на расстоянии 7: возвращается к прерванной цели',
  stateAfter(STATE.FLEE, [10, 7], [17, 7]).state === STATE.RETURN);
check('RETURN -> FLEE, если призрак снова подошёл',
  stateAfter(STATE.RETURN, [10, 7], [12, 7]).state === STATE.FLEE);
const pr = new Pacman([1, 3]);
pr.state = STATE.RETURN;
pr.returnTarget = [2, 3];
const foodR = new Food([[2, 3], [9, 13]]);
pr.step([20, 13], foodR, field);
check('RETURN -> CHASE, когда съел ту самую еду (точку возврата)',
  pr.state === STATE.CHASE && same(pr.pos, [2, 3]) && !foodR.has([2, 3]));
const pm = new Pacman([1, 3]);
pm.target = [5, 3];
pm.updateState([3, 3], new Food([[5, 3]]));
check('при начале бегства запоминается точка возврата', pm.returnTarget && same(pm.returnTarget, [5, 3]));

// ---------------------------------------------------------------
title('7. Паритет с Python (tests/parity_cases.json от настоящего кода ЛР 1-2)');
const modeBad = PARITY.modes.filter((m) => {
  const toPy = (s) => (s === STATE.FLEE ? 'flee' : 'chase');
  const a = stateAfter(STATE.CHASE, [10, 7], [10 + m.dx, 7 + m.dy]).state;
  const b = stateAfter(STATE.FLEE, [10, 7], [10 + m.dx, 7 + m.dy]).state;
  return toPy(a) !== m.chase || toPy(b) !== m.flee;
});
check(`смена режима через угрозу = Python d<5 / d>=7 на ${PARITY.modes.length} расстояниях`, modeBad.length === 0);
const bfsBad = PARITY.steps.filter((s) => {
  const { dist } = field.bfsMap(s.pac);
  return dist.size !== s.reach || [...dist.values()].reduce((a, b) => a + b, 0) !== s.distSum;
});
check(`BFS совпадает с Python на ${PARITY.steps.length} позициях`, bfsBad.length === 0);
const chaseBad = PARITY.steps.filter((s) => {
  const p = new Pacman(s.pac);
  return !same(p._chaseStep(s.ghost, new Food(s.food), field), s.chase);
});
check(`шаг за едой совпадает с Python в ${PARITY.steps.length} случаях`, chaseBad.length === 0, `расхождений ${chaseBad.length}`);
const fleeBad = PARITY.steps.filter((s) => !same(new Pacman(s.pac)._fleeStep(s.ghost, field), s.flee));
check(`шаг бегства совпадает с Python в ${PARITY.steps.length} случаях`, fleeBad.length === 0, `расхождений ${fleeBad.length}`);

// ---------------------------------------------------------------
title('8. Игра целиком: победа, поражение, застревание, «Бу!»');
const g1 = new Game(field);
check('новая игра: состояние play, 159 еды', g1.result === RESULT.PLAY && g1.food.count === 159);
g1.pacman.pos = [2, 1];
g1.moveGhost(1, 0);
check('победа: призрак шагнул на клетку Пакмана', g1.result === RESULT.WIN);
const g2 = new Game(field);
g2.food = new Food([[19, 13]]);
g2.food.total = 159;
g2.tick(50);
check('поражение: Пакман съел последнюю еду', g2.result === RESULT.LOSE);
const runIdle = (antiStuck) => {
  const g = new Game(field, { antiStuck });
  for (let i = 0; i < 20000 && g.result === RESULT.PLAY; i++) g.tick(50); // до 1000 с
  return g;
};
const stuck = runIdle(false);
const fixed = runIdle(true);
check('без защиты Пакман ходит по кругу возле призрака и не доедает (баг из Python)',
  stuck.result === RESULT.PLAY && stuck.food.count > 0, `еды осталось ${stuck.food.count} за 1000 с`);
check('с защитой от застревания доедает всё', fixed.result === RESULT.LOSE && fixed.log.count('stuck') > 0,
  `за ${(fixed.timeMs / 1000).toFixed(1)} с, срабатываний ${fixed.log.count('stuck')}`);
const g3 = new Game(field);
g3.ghost.pos = [20, 11];
g3.boo();
for (let i = 0; i < 10; i++) g3.tick(50);
const posScared = [...g3.pacman.pos];
for (let i = 0; i < 10; i++) g3.tick(50);
check('«Бу!» рядом: громкость выше порога, Пакман замер',
  g3.log.count('scared') === 1 && same(posScared, g3.pacman.pos) && g3.pacman.isStunned(g3.timeMs));
const g4 = new Game(field);
g4.ghost.pos = [15, 13];
g4.pacman.delay = 100; // Пакман стоит, чтобы проверить только волну
g4.boo();
for (let i = 0; i < 20; i++) g4.tick(50);
check('«Бу!» издалека: волна дошла (5 клеток), но тихо — не испугался',
  g4.log.count('quiet') === 1 && g4.log.count('scared') === 0);
check('повторное «Бу!» во время кулдауна не создаёт волну', g4.boo() === null && g4.log.count('cooldown') === 1);
check('после испуга Пакман снова ходит (через BOO_STUN_MS)', (() => {
  for (let i = 0; i < BOO_STUN_MS / 50 + 5; i++) g3.tick(50);
  return !g3.pacman.isStunned(g3.timeMs);
})());
const log = new EventLog();
log.add(0, 'eat', 'a'); log.add(10, 'eat', 'b'); log.add(20, 'boo', 'c');
check('журнал событий считает статистику', log.stats.eaten === 2 && log.stats.boos === 1 && log.last(1)[0].text === 'c');
check('ядро работает без браузера (нет window и document)',
  typeof globalThis.window === 'undefined' && typeof globalThis.document === 'undefined');

console.log(`\nИтого: ${passed} ✅, ${failed} ❌ из ${passed + failed} проверок`);
if (failed > 0) process.exit(1);
