// js/rect.js — свой прямоугольник вместо pygame.Rect
export class Rect {
  constructor(x, y, w, h) {
    this.x = x; // левый край
    this.y = y; // верхний край
    this.w = w; // ширина
    this.h = h; // высота
  }

  get centerx() { return this.x + this.w / 2; } // геттер = @property
  get centery() { return this.y + this.h / 2; }
  get center() { return [this.centerx, this.centery]; }

  // Сдвиг КОПИЕЙ: старый прямоугольник не меняется (как pygame.Rect.move)
  move(dx, dy) {
    return new Rect(this.x + dx, this.y + dy, this.w, this.h);
  }

  // Пересекаются ли два прямоугольника (касание краями — не пересечение)
  colliderect(other) {
    return this.x < other.x + other.w && this.x + this.w > other.x &&
           this.y < other.y + other.h && this.y + this.h > other.y;
  }

  // Попадает ли точка внутрь прямоугольника
  collidepoint(px, py) {
    return px >= this.x && px < this.x + this.w &&
           py >= this.y && py < this.y + this.h;
  }
}
