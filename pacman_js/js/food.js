// js/food.js — еда на поле (в Python это было множество self.food)
import { cellKey } from './constants.js';

export class Food {
  constructor(cells = []) {
    this.cells = new Map(); // ключ "x,y" -> [x, y]; Map помнит порядок добавления
    for (const [x, y] of cells) this.cells.set(cellKey(x, y), [x, y]);
    this.total = this.cells.size; // сколько было еды в начале
  }

  // Еда на всех свободных клетках, кроме стартов призрака и Пакмана
  static fromField(field) {
    const skip = [cellKey(...field.ghostStart), cellKey(...field.pacStart)];
    return new Food(field.freeCells().filter(([x, y]) => !skip.includes(cellKey(x, y))));
  }

  has([x, y]) { return this.cells.has(cellKey(x, y)); }

  // Съесть еду в клетке: true, если она там была
  eat([x, y]) { return this.cells.delete(cellKey(x, y)); }

  get count() { return this.cells.size; }          // сколько осталось
  get eaten() { return this.total - this.count; }  // сколько съедено

  list() { return [...this.cells.values()]; }     // массив клеток [[x, y], ...]
}
