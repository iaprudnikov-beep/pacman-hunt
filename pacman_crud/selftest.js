// selftest.js — проверки чистых функций без браузера.
// Запуск: node selftest.js   или   npm test

import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  TYPES,
  STORAGE_KEY,
  escapeHtml,
  validateBonus,
  filterBonuses,
} from './js/validation.js';

const dir = dirname(fileURLToPath(import.meta.url));
let passed = 0;
let failed = 0;

function check(name, condition) {
  if (condition) {
    passed += 1;
    console.log(`  ok  ${name}`);
  } else {
    failed += 1;
    console.log(`  FAIL  ${name}`);
  }
}

function validSample(overrides = {}) {
  return {
    name: 'Ускорение',
    type: 'скорость',
    points: 200,
    duration: 8,
    spawnChance: 25,
    ...overrides,
  };
}

console.log('validation + escapeHtml');

const good = validateBonus(validSample());
check('корректный бонус проходит проверку', good.valid === true && good.value.name === 'Ускорение');
check('корректный бонус: points — целое 200', good.value.points === 200);

const emptyName = validateBonus(validSample({ name: '   ' }));
check('пустое имя — ошибка', emptyName.valid === false && Boolean(emptyName.errors.name));

const longName = validateBonus(validSample({ name: 'я'.repeat(41) }));
check('имя длиннее 40 символов — ошибка', longName.valid === false && Boolean(longName.errors.name));

const trimmed = validateBonus(validSample({ name: '  Вишня  ' }));
check('пробелы по краям имени обрезаются', trimmed.valid && trimmed.value.name === 'Вишня');

const badPoints = validateBonus(validSample({ points: 1.5 }));
check('дробные очки — ошибка', !badPoints.valid && Boolean(badPoints.errors.points));

const emptyPoints = validateBonus(validSample({ points: '' }));
check('пустые очки — ошибка (не превращаются в 0)', !emptyPoints.valid && Boolean(emptyPoints.errors.points));

const overPoints = validateBonus(validSample({ points: 5001 }));
check('очки > 5000 — ошибка', !overPoints.valid && Boolean(overPoints.errors.points));

check('очки = 0 допустимы', validateBonus(validSample({ points: 0 })).valid === true);
check('очки = 5000 допустимы', validateBonus(validSample({ points: 5000 })).valid === true);

const overDuration = validateBonus(validSample({ duration: 61 }));
check('длительность > 60 — ошибка', !overDuration.valid && Boolean(overDuration.errors.duration));

const overChance = validateBonus(validSample({ spawnChance: 101 }));
check('шанс > 100 — ошибка', !overChance.valid && Boolean(overChance.errors.spawnChance));

const badType = validateBonus(validSample({ type: 'телепорт' }));
check('тип не из списка — ошибка', !badType.valid && Boolean(badType.errors.type));

for (const type of TYPES) {
  check(`тип «${type}» разрешён`, validateBonus(validSample({ type })).valid === true);
}

check('ключ хранилища фиксированный', STORAGE_KEY === 'pacman_bonuses');

const xss = escapeHtml(`<img src=x onerror="alert('xss')">`);
check('escapeHtml экранирует < и >', xss.includes('&lt;img') && xss.includes('&gt;') && !xss.includes('<img'));
check('escapeHtml экранирует кавычки', escapeHtml('a"b\'c').includes('&quot;') && escapeHtml("a'b").includes('&#39;'));
check('escapeHtml экранирует & первым', escapeHtml('a&b').includes('&amp;') && !escapeHtml('a&b').includes('a&b'));
check('escapeHtml не трогает обычный текст', escapeHtml('Супервишня') === 'Супервишня');

const list = [
  { name: 'Супервишня', points: 500 },
  { name: 'Ускорение', points: 200 },
  { name: 'Золотая точка', points: 1000 },
];
check('фильтр по очкам ≤ 500 оставляет две записи', filterBonuses(list, 500, '').length === 2);
check('поиск «золот» находит одну запись', filterBonuses(list, 5000, 'золот').length === 1
  && filterBonuses(list, 5000, 'золот')[0].name === 'Золотая точка');
check('поиск не зависит от регистра', filterBonuses(list, 5000, 'СУПЕР').length === 1);
check('фильтр и поиск вместе', filterBonuses(list, 300, 'вишня').length === 0);

console.log('\nсинтаксис файлов страницы');

for (const rel of ['js/validation.js', 'js/crud.js', 'selftest.js', 'server.js']) {
  const src = readFileSync(join(dir, rel), 'utf8');
  const result = spawnSync(process.execPath, ['--check', join(dir, rel)], { encoding: 'utf8' });
  check(`${rel} проходит node --check`, result.status === 0 && src.length > 100);
  if (result.status !== 0) console.log(result.stderr.trim());
}

const html = readFileSync(join(dir, 'index.html'), 'utf8');
check('в index.html подключены style.css и crud.js', html.includes('css/style.css') && html.includes('js/crud.js'));
check('в форме есть span.error под полями', (html.match(/class="error"/g) || []).length >= 5);
check('у таблицы есть id="bonuses" и tbody', html.includes('id="bonuses"') && html.includes('<tbody>'));
check('есть ползунок фильтра и поиск по имени', html.includes('id="filter-points"') && html.includes('id="filter-name"'));

console.log(`\nИтого: ${passed} ок, ${failed} ошибок`);
if (failed > 0) process.exit(1);
