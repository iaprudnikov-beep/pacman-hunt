// js/renderer.js — всё рисование на Canvas. Логики игры здесь нет: только читаем состояние ядра
import { CELL, COLS, ROWS, HUD_H, STATE } from '../../pacman_js/js/constants.js';
import { COLORS, rgba } from './palette.js';
import { Indicators } from './indicators.js';

const W = COLS * CELL;  // 880
const H = ROWS * CELL;  // 600 (верхняя панель — отдельный HTML-блок над холстом)

// Мягкое свечение, как glow_circle в Pygame. Рисуем один раз в маленький холст и потом копируем
const glowCache = new Map();
function glowSprite(color, radius, strength) {
  const key = `${color}|${radius}|${strength}`;
  if (glowCache.has(key)) return glowCache.get(key);
  const size = Math.ceil(radius * 6);
  const c = document.createElement('canvas');
  c.width = size; c.height = size;
  const g = c.getContext('2d');
  const outer = radius * 2.6;
  const grad = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, outer);
  for (let i = 0; i <= 10; i++) {            // яркость падает к краю: (1 - k)^2
    const dist = (outer * i) / 10;
    const k = Math.min(1, Math.max(0.1, (dist / radius - 1) / 1.6));
    const f = (strength / 255) * (1 - k) ** 2 * 0.5;
    grad.addColorStop(i / 10, `rgb(${color[0] * f}, ${color[1] * f}, ${color[2] * f})`);
  }
  g.fillStyle = grad;
  g.fillRect(0, 0, size, size);
  glowCache.set(key, c);
  return c;
}

export class Renderer {
  constructor(canvas, field) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.setField(field);
  }

  setField(field) {
    this.field = field;
    this.background = this._buildBackground(); // фон со стенами рисуем один раз
  }

  // Как build_background в Pygame: градиент + стены + неоновая кромка там, где рядом проход
  _buildBackground() {
    const c = document.createElement('canvas');
    c.width = W; c.height = H;
    const g = c.getContext('2d');
    const full = H + HUD_H; // в Pygame градиент шёл на всё окно, вместе с панелью
    const grad = g.createLinearGradient(0, -HUD_H, 0, full - HUD_H);
    grad.addColorStop(0, rgba(COLORS.BG_TOP));
    grad.addColorStop(1, rgba(COLORS.BG_BOTTOM));
    g.fillStyle = grad;
    g.fillRect(0, 0, W, H);
    const f = this.field;
    const m = 3; // отступ кромки внутрь стены
    const lines = [];
    for (let y = 0; y < ROWS; y++) {
      for (let x = 0; x < COLS; x++) {
        if (f.maze[y][x] !== 1) continue;
        const rx = x * CELL; const ry = y * CELL;
        g.fillStyle = rgba(COLORS.WALL_FILL);
        g.fillRect(rx, ry, CELL, CELL);
        if (f.isFree(x, y - 1)) lines.push([rx, ry + m, rx + CELL, ry + m]);
        if (f.isFree(x, y + 1)) lines.push([rx, ry + CELL - m, rx + CELL, ry + CELL - m]);
        if (f.isFree(x - 1, y)) lines.push([rx + m, ry, rx + m, ry + CELL]);
        if (f.isFree(x + 1, y)) lines.push([rx + CELL - m, ry, rx + CELL - m, ry + CELL]);
      }
    }
    const strokeAll = () => {
      g.beginPath();
      for (const [x1, y1, x2, y2] of lines) { g.moveTo(x1, y1); g.lineTo(x2, y2); }
      g.stroke();
    };
    g.lineWidth = 3;
    g.lineCap = 'square';
    g.strokeStyle = rgba(COLORS.WALL_EDGE);
    g.globalCompositeOperation = 'lighter'; // сложение цветов = BLEND_RGB_ADD в Pygame
    for (const blur of [16, 8, 4]) {         // три слоя размытия = неоновое свечение
      g.shadowColor = rgba(COLORS.WALL_EDGE, 1);
      g.shadowBlur = blur;
      strokeAll();
    }
    g.shadowBlur = 0;
    g.globalCompositeOperation = 'source-over';
    strokeAll();                              // чёткая линия сверху
    return c;
  }

  // ---------- Кадр целиком ----------
  // view = { fog: true/false, visionPx: радиус видимости, pops: [...], indicators }
  draw(game, view, nowMs) {
    const ctx = this.ctx;
    const t = nowMs / 1000;
    const ghostC = this._center(game.ghost.vis);
    const visible = (px, py) => !view.fog || Math.hypot(px - ghostC[0], py - ghostC[1]) <= view.visionPx;

    // 1. Заливаем весь экран: Canvas не помнит прошлый кадр
    ctx.globalCompositeOperation = 'source-over';
    if (view.fog) {
      ctx.fillStyle = rgba(COLORS.FOG);
      ctx.fillRect(0, 0, W, H);
      // 2. Туман: копируем с фона только клетки рядом с призраком (отбор по расстоянию)
      for (let y = 0; y < ROWS; y++) {
        for (let x = 0; x < COLS; x++) {
          const cx = x * CELL + CELL / 2; const cy = y * CELL + CELL / 2;
          // вне радиуса — не рисуем (запас в одну клетку, чтобы край круга был ровным)
          if (Math.hypot(cx - ghostC[0], cy - ghostC[1]) > view.visionPx + CELL) continue;
          ctx.drawImage(this.background, x * CELL, y * CELL, CELL, CELL, x * CELL, y * CELL, CELL, CELL);
        }
      }
    } else {
      ctx.drawImage(this.background, 0, 0);  // без тумана — весь лабиринт, как в Pygame
    }

    // 3. Еда: пульсирующие точки со свечением (draw_food в Pygame)
    for (const [fx, fy] of game.food.list()) {
      const cx = fx * CELL + CELL / 2; const cy = fy * CELL + CELL / 2;
      if (!visible(cx, cy)) continue;
      const r = 3.6 + 0.9 * Math.sin(t * 4 + fx * 0.7 + fy * 0.5);
      this._glow(COLORS.FOOD, cx, cy, 4, 110);
      this._circle(cx, cy, Math.max(3, Math.round(r)), rgba(COLORS.FOOD));
    }

    // 4. Эффекты: волны «Бу!» из ядра и «вспышки» съеденной еды
    this._drawWaves(game.effects, COLORS.GHOST, 3);
    this._drawWaves(view.pops.filter((e) => visible(e.x * CELL + CELL / 2, e.y * CELL + CELL / 2)), COLORS.FOOD, 2);

    // 5. Персонажи
    const pacC = this._center(game.pacman.vis);
    if (visible(...pacC)) this._drawPacman(game.pacman, pacC, t, nowMs, game.timeMs);
    this._drawGhost(ghostC, pacC, t);

    // 6. Мягкий край видимости: к краю круга темнеет, снаружи — сплошная тьма
    if (view.fog) {
      const R = view.visionPx;
      const grad = ctx.createRadialGradient(ghostC[0], ghostC[1], R * 0.65, ghostC[0], ghostC[1], R);
      grad.addColorStop(0, rgba(COLORS.FOG, 0));
      grad.addColorStop(1, rgba(COLORS.FOG, 1)); // за радиусом — полностью тёмно
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, W, H);
    }

    // 7. Значки реакций рисуем поверх тумана — это подсказка игроку
    this._drawIndicators(view.indicators, pacC);
  }

  // ---------- Помощники ----------
  _center([vx, vy]) { return [vx * CELL + CELL / 2, vy * CELL + CELL / 2]; }

  _circle(x, y, r, color) {
    const ctx = this.ctx;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  }

  _glow(color, x, y, radius, strength) {
    const s = glowSprite(color, radius, strength);
    this.ctx.globalCompositeOperation = 'lighter';
    this.ctx.drawImage(s, x - s.width / 2, y - s.height / 2);
    this.ctx.globalCompositeOperation = 'source-over';
  }

  // Волна: радиус и alpha считает ЯДРО (Effect.radius, Effect.alpha), здесь только рисуем
  _drawWaves(list, color, width) {
    const ctx = this.ctx;
    for (const e of list) {
      if (!e.active) continue;
      const x = e.x * CELL + CELL / 2; const y = e.y * CELL + CELL / 2;
      const a = e.alpha.toFixed(3);
      ctx.strokeStyle = rgba(color, a);       // прозрачность прямо в цвете контура
      ctx.lineWidth = width;
      ctx.shadowColor = rgba(color, a);
      ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.arc(x, y, e.radius * CELL, 0, Math.PI * 2);
      ctx.stroke();
      ctx.shadowBlur = 0;
      ctx.fillStyle = rgba(color, (e.alpha * 0.08).toFixed(3)); // лёгкая заливка внутри
      ctx.fill();
    }
  }

  // Пакман с анимированным ртом — как Pacman.draw в Pygame
  _drawPacman(pac, [pcx, pcy], t, nowMs, gameMs) {
    const ctx = this.ctx;
    const pr = CELL / 2 - 4;
    const color = pac.state === STATE.FLEE ? COLORS.PAC_FLEE : COLORS.PAC;
    this._glow(color, pcx, pcy, pr, 110);
    const mouth = ((4 + 38 * Math.abs(Math.sin(t * 9))) * Math.PI) / 180; // раскрытие рта
    const base = Math.atan2(pac.direction[1], pac.direction[0]);
    const steps = 28;
    ctx.fillStyle = rgba(color);
    ctx.beginPath();
    ctx.moveTo(pcx, pcy);
    for (let i = 0; i <= steps; i++) {      // сектор круга без «рта»
      const a = base + mouth + ((2 * Math.PI - 2 * mouth) * i) / steps;
      ctx.lineTo(pcx + pr * Math.cos(a), pcy + pr * Math.sin(a));
    }
    ctx.closePath();
    ctx.fill();
    const eyeA = base - (Math.PI / 2) * (pac.direction[0] >= 0 ? 1 : -1); // глаз всегда сверху
    const ex = pcx + pr * 0.45 * Math.cos(eyeA) + pr * 0.15 * Math.cos(base);
    const ey = pcy + pr * 0.45 * Math.sin(eyeA) + pr * 0.15 * Math.sin(base);
    this._circle(ex, ey, 2, rgba(COLORS.PAC_EYE));
    if (pac.isStunned(gameMs)) {             // испуг от «Бу!»: вокруг кружат звёздочки
      for (let i = 0; i < 3; i++) {
        const a = nowMs / 250 + (i * 2 * Math.PI) / 3;
        this._star(pcx + 20 * Math.cos(a), pcy - 22 + 6 * Math.sin(a), 5, rgba(COLORS.PAC));
      }
    }
  }

  _star(x, y, r, color) {
    const ctx = this.ctx;
    ctx.fillStyle = color;
    ctx.beginPath();
    for (let i = 0; i < 10; i++) {          // 5 лучей: внешняя и внутренняя точки по очереди
      const rr = i % 2 === 0 ? r : r * 0.45;
      const a = -Math.PI / 2 + (i * Math.PI) / 5;
      ctx.lineTo(x + rr * Math.cos(a), y + rr * Math.sin(a));
    }
    ctx.closePath();
    ctx.fill();
  }

  // Призрак: купол, волнистый подол, блик и глаза, которые следят за Пакманом (Ghost.draw)
  _drawGhost([gx, gy], lookAt, t) {
    const ctx = this.ctx;
    const cx = gx;
    const cy = gy + 2 * Math.sin(t * 3);   // покачивание
    const r = CELL / 2 - 4;
    this._glow(COLORS.GHOST, cx, cy, r, 120);
    ctx.fillStyle = rgba(COLORS.GHOST);
    ctx.beginPath();
    for (let i = 0; i <= 18; i++) {         // купол — верхняя полуокружность
      const a = Math.PI + (Math.PI * i) / 18;
      ctx.lineTo(cx + r * Math.cos(a), cy - 2 + r * Math.sin(a));
    }
    const waves = 4;
    const bottom = cy + r;
    for (let i = 0; i <= waves * 4; i++) {  // подол-волна справа налево
      const px = cx + r - (2 * r * i) / (waves * 4);
      const py = bottom - 3 + 3 * Math.sin((i * Math.PI) / 2 + t * 10);
      ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fill();
    this._circle(cx - r * 0.4, cy - r * 0.45, 3, rgba(COLORS.GHOST_SHINE)); // блик
    let lx = lookAt[0] - cx; let ly = lookAt[1] - cy;
    const ln = Math.hypot(lx, ly) || 1;
    lx = (lx / ln) * 2.5; ly = (ly / ln) * 2.5;   // зрачки смещены в сторону Пакмана
    for (const side of [-1, 1]) {
      const exx = cx + side * r * 0.4; const eyy = cy - r * 0.2;
      ctx.fillStyle = rgba(COLORS.WHITE);
      ctx.beginPath();
      ctx.ellipse(exx, eyy, 4, 5, 0, 0, Math.PI * 2);
      ctx.fill();
      this._circle(exx + lx, eyy + ly, 2, rgba(COLORS.EYE));
    }
  }

  // Значок взлетает вверх, сначала «выпрыгивает» (размер), потом тает (alpha)
  _drawIndicators(ind, [px, py]) {
    const ctx = this.ctx;
    ind.items.forEach((it, i) => {
      const p = Indicators.progress(it);
      const alpha = p < 0.7 ? 1 : 1 - (p - 0.7) / 0.3;
      const scale = p < 0.15 ? 0.5 + (p / 0.15) * 0.7 : 1.2 - Math.min(0.2, p);
      const y = py - 30 - p * 26 - i * 4;
      ctx.font = `bold ${Math.round(26 * scale)}px Arial`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.lineWidth = 4;
      ctx.strokeStyle = rgba(COLORS.FOG, alpha.toFixed(3));
      ctx.strokeText(it.text, px, y);
      ctx.fillStyle = rgba(it.color, alpha.toFixed(3));
      ctx.shadowColor = rgba(it.color, alpha.toFixed(3));
      ctx.shadowBlur = 10;
      ctx.fillText(it.text, px, y);
      ctx.shadowBlur = 0;
    });
  }
}
