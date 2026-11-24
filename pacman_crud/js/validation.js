// js/validation.js
// Чистые функции без DOM и LocalStorage — их же проверяет selftest.js в Node.

/** Разрешённые типы бонуса. Если в форме пришло что-то другое — ошибка. */
export const TYPES = ['скорость', 'заморозка', 'очки', 'щит'];

/** Ключ, под которым в LocalStorage лежит JSON-массив бонусов. */
export const STORAGE_KEY = 'pacman_bonuses';

/**
 * Стартовый набор, если в хранилище ещё ничего нет.
 * id подставляется при первой загрузке через crypto.randomUUID().
 */
export const DEFAULT_BONUSES = [
  { name: 'Супервишня',     type: 'очки',       points: 500,  duration: 0,  spawnChance: 30 },
  { name: 'Ускорение',      type: 'скорость',   points: 200,  duration: 8,  spawnChance: 25 },
  { name: 'Ледяная ловушка', type: 'заморозка', points: 300,  duration: 5,  spawnChance: 15 },
  { name: 'Щит призрака',   type: 'щит',        points: 400,  duration: 10, spawnChance: 10 },
  { name: 'Золотая точка',  type: 'очки',       points: 1000, duration: 0,  spawnChance: 8  },
];

/**
 * Функция escapeHtml.
 * Экранирует опасные символы, чтобы имя из формы нельзя было вставить как HTML
 * (защита от XSS: строка «<script>» станет видимым текстом, а не кодом).
 */
export function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

/** Проверка числа: не пустое, конечное, в диапазоне [min, max]. */
function readNumber(raw, min, max, integerOnly) {
  const text = String(raw ?? '').trim();
  if (text === '') return { ok: false };
  const n = Number(text);
  if (!Number.isFinite(n) || n < min || n > max) return { ok: false };
  if (integerOnly && !Number.isInteger(n)) return { ok: false };
  return { ok: true, value: n };
}

/**
 * Функция validateBonus.
 * Проверяет поля сущности «Бонус». Возвращает { valid, errors, value }.
 * errors — объект вида { имяПоля: «текст ошибки» }.
 * Похоже на проверку данных в Python: собрали ошибки в dict и вернули его.
 */
export function validateBonus(formData) {
  const errors = {};

  const name = String(formData.name ?? '').trim();
  if (!name) errors.name = 'Название обязательно';
  else if (name.length > 40) errors.name = 'Не длиннее 40 символов';

  const type = String(formData.type ?? '').trim();
  if (!TYPES.includes(type)) errors.type = 'Выберите тип из списка';

  const points = readNumber(formData.points, 0, 5000, true);
  if (!points.ok) errors.points = 'Целое число от 0 до 5000';

  const duration = readNumber(formData.duration, 0, 60, false);
  if (!duration.ok) errors.duration = 'Число от 0 до 60';

  const spawnChance = readNumber(formData.spawnChance, 0, 100, false);
  if (!spawnChance.ok) errors.spawnChance = 'Число от 0 до 100';

  const valid = Object.keys(errors).length === 0;
  const value = valid
    ? {
        name,
        type,
        points: points.value,
        duration: duration.value,
        spawnChance: spawnChance.value,
      }
    : null;

  return { valid, errors, value };
}

/**
 * Функция filterBonuses.
 * Оставляет бонусы, у которых очки ≤ maxPoints, а имя содержит query
 * (регистр не важен). Пустой поиск ничего не отфильтровывает.
 */
export function filterBonuses(items, maxPoints, query) {
  const limit = Number(maxPoints);
  const q = String(query ?? '').trim().toLowerCase();
  return items.filter((item) => {
    const byPoints = Number.isFinite(limit) ? item.points <= limit : true;
    const byName = !q || String(item.name).toLowerCase().includes(q);
    return byPoints && byName;
  });
}
