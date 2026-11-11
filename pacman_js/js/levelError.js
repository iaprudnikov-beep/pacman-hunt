// js/levelError.js — своя ошибка «файл уровня неправильный» (как LevelError в Python)
export class LevelError extends Error {
  constructor(message) {
    super(message);          // вызываем конструктор родителя (как super().__init__)
    this.name = 'LevelError';
  }
}
