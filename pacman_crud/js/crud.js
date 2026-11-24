// js/crud.js
// Логика страницы: LocalStorage, таблица, форма, делегирование кликов.
// Чистые проверки импортируются из validation.js.

import {
  TYPES,
  STORAGE_KEY,
  DEFAULT_BONUSES,
  escapeHtml,
  validateBonus,
  filterBonuses,
} from './validation.js';

const form = document.querySelector('#create-form');
const tbody = document.querySelector('#bonuses tbody');
const emptyHint = document.querySelector('#empty-hint');
const counter = document.querySelector('#counter');
const filterPoints = document.querySelector('#filter-points');
const filterVal = document.querySelector('#filter-val');
const filterName = document.querySelector('#filter-name');

let items = [];          // текущий массив бонусов (как список словарей в Python)
let editingId = null;    // id строки, которая сейчас редактируется, или null

// ---------- LocalStorage: загрузка и сохранение ----------

/** Функция load. Читает JSON из LocalStorage. Если ключа нет — кладёт заготовки. */
function load() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    items = DEFAULT_BONUSES.map((bonus) => ({
      id: crypto.randomUUID(),
      ...bonus,
    }));
    save(items);
    return items;
  }
  try {
    const parsed = JSON.parse(raw);
    items = Array.isArray(parsed) ? parsed : [];
  } catch {
    items = [];
  }
  return items;
}

/** Функция save. Сразу пишет весь массив в LocalStorage. Вызываем после Create/Update/Delete. */
function save(list) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}

// ---------- Ошибки под полями ----------

/** Функция showErrors. Пишет тексты в соседние <span class="error">. */
function showErrors(rootEl, errors) {
  rootEl.querySelectorAll('span.error').forEach((span) => {
    span.textContent = '';
  });
  for (const [field, message] of Object.entries(errors)) {
    const span = rootEl.querySelector(`[data-error="${field}"]`);
    if (span) span.textContent = message;
  }
}

/** Функция readFields. Собирает значения из input/select внутри элемента (форма или строка). */
function readFields(rootEl) {
  const data = {};
  rootEl.querySelectorAll('input[name], select[name]').forEach((el) => {
    data[el.name] = el.value;
  });
  return data;
}

// ---------- Рендер таблицы ----------

/** Функция typeOptions. Список <option> для выпадающего типа. */
function typeOptions(selected) {
  return TYPES.map((type) => {
    const sel = type === selected ? ' selected' : '';
    return `<option value="${escapeHtml(type)}"${sel}>${escapeHtml(type)}</option>`;
  }).join('');
}

/** Функция makeViewRow. Обычная строка таблицы с кнопками «изменить» и «удалить». */
function makeViewRow(item) {
  return `
    <tr data-id="${escapeHtml(item.id)}">
      <td>${escapeHtml(item.name)}</td>
      <td><span class="tag tag-${escapeHtml(item.type)}">${escapeHtml(item.type)}</span></td>
      <td class="num">${escapeHtml(item.points)}</td>
      <td class="num">${escapeHtml(item.duration)}</td>
      <td class="num">${escapeHtml(item.spawnChance)}</td>
      <td class="actions">
        <button type="button" class="btn-edit" data-id="${escapeHtml(item.id)}" title="Изменить">✎</button>
        <button type="button" class="btn-delete" data-id="${escapeHtml(item.id)}" title="Удалить">✕</button>
      </td>
    </tr>`;
}

/** Функция makeEditRow. Та же строка, но с полями ввода, «сохранить» и «отмена». */
function makeEditRow(item) {
  return `
    <tr data-id="${escapeHtml(item.id)}" class="editing">
      <td>
        <input name="name" value="${escapeHtml(item.name)}" maxlength="40" required>
        <span class="error" data-error="name"></span>
      </td>
      <td>
        <select name="type" required>${typeOptions(item.type)}</select>
        <span class="error" data-error="type"></span>
      </td>
      <td>
        <input name="points" type="number" value="${escapeHtml(item.points)}" min="0" max="5000" step="1" required>
        <span class="error" data-error="points"></span>
      </td>
      <td>
        <input name="duration" type="number" value="${escapeHtml(item.duration)}" min="0" max="60" step="any" required>
        <span class="error" data-error="duration"></span>
      </td>
      <td>
        <input name="spawnChance" type="number" value="${escapeHtml(item.spawnChance)}" min="0" max="100" step="any" required>
        <span class="error" data-error="spawnChance"></span>
      </td>
      <td class="actions">
        <button type="button" class="btn-save" data-id="${escapeHtml(item.id)}" title="Сохранить">✓</button>
        <button type="button" class="btn-cancel" data-id="${escapeHtml(item.id)}" title="Отмена">✕</button>
      </td>
    </tr>`;
}

/** Функция visibleItems. Текущий массив после фильтра по очкам и поиска по имени. */
function visibleItems() {
  return filterBonuses(items, filterPoints.value, filterName.value);
}

/** Функция render. Перерисовывает <tbody> целиком (для небольшого списка так проще). */
function render() {
  const visible = visibleItems();
  tbody.innerHTML = visible.map((item) => (
    item.id === editingId ? makeEditRow(item) : makeViewRow(item)
  )).join('');
  emptyHint.hidden = visible.length !== 0;
  counter.textContent = `Показано ${visible.length} из ${items.length}`;
}

// ---------- Create / Update / Delete ----------

/** Функция createBonus. Валидация формы → новый id → push → save → перерисовка. */
function createBonus(event) {
  event.preventDefault();
  const result = validateBonus(readFields(form));
  showErrors(form, result.errors);
  if (!result.valid) return;

  items.push({ id: crypto.randomUUID(), ...result.value });
  save(items);
  form.reset();
  showErrors(form, {});
  render();
}

/** Функция startEdit. Запоминаем id и перерисовываем строку как форму. */
function startEdit(id) {
  editingId = id;
  render();
}

/** Функция saveEdit. Читает поля строки, проверяет, заменяет элемент в массиве, save(). */
function saveEdit(id, row) {
  const result = validateBonus(readFields(row));
  showErrors(row, result.errors);
  if (!result.valid) return;

  const index = items.findIndex((item) => item.id === id);
  if (index === -1) return;
  items[index] = { id, ...result.value };
  save(items);
  editingId = null;
  render();
}

/** Функция cancelEdit. Выходим из режима правки без сохранения. */
function cancelEdit() {
  editingId = null;
  render();
}

/** Функция confirmDelete. confirm() → фильтруем массив без этой записи → save(). */
function confirmDelete(id) {
  const item = items.find((entry) => entry.id === id);
  const label = item ? item.name : id;
  if (!confirm(`Удалить бонус «${label}»?`)) return;
  items = items.filter((entry) => entry.id !== id);
  save(items);
  if (editingId === id) editingId = null;
  render();
}

// ---------- События ----------

form.addEventListener('submit', createBonus);

filterPoints.addEventListener('input', () => {
  filterVal.textContent = filterPoints.value;
  render();
});
filterName.addEventListener('input', render);

// Один обработчик на всю таблицу (делегирование событий).
// Не вешаем click на каждую кнопку: кнопки появляются и исчезают при перерисовке,
// а tbody всегда на месте. closest('button') находит кнопку, по которой кликнули.
tbody.addEventListener('click', (event) => {
  const btn = event.target.closest('button');
  if (!btn) return;
  const id = btn.dataset.id;
  if (btn.classList.contains('btn-edit')) startEdit(id);
  else if (btn.classList.contains('btn-delete')) confirmDelete(id);
  else if (btn.classList.contains('btn-save')) saveEdit(id, btn.closest('tr'));
  else if (btn.classList.contains('btn-cancel')) cancelEdit();
});

// Старт: загрузка из LocalStorage и первый рендер.
load();
filterVal.textContent = filterPoints.value;
render();
