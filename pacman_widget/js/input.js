// js/input.js — клавиатура через объект-флаги: события только ставят флаги, цикл их опрашивает
// Используем e.code (физическая клавиша), поэтому WASD работает и на русской раскладке (ЦФЫВ)
const CONTROL_KEYS = [
  'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
  'KeyW', 'KeyA', 'KeyS', 'KeyD', 'Space', 'KeyR', 'KeyF', 'KeyP', 'Enter',
];

export class Input {
  constructor(target = window) {
    this.keys = {};          // { KeyW: true, ArrowLeft: false, ... } — что зажато сейчас
    this.pressed = new Set(); // клавиши, нажатые с прошлого шага (для одиночных действий)
    target.addEventListener('keydown', (e) => {
      if (CONTROL_KEYS.includes(e.code)) e.preventDefault(); // страница не скроллится
      if (!this.keys[e.code]) this.pressed.add(e.code);      // повтор ОС не считаем новым нажатием
      this.keys[e.code] = true;
    });
    target.addEventListener('keyup', (e) => { this.keys[e.code] = false; });
    // ушли с вкладки — отпускаем всё, иначе призрак «залипнет»
    target.addEventListener('blur', () => { this.keys = {}; });
  }

  // Опрос направления в начале каждого шага
  readInput() {
    const k = this.keys;
    return {
      up: k.KeyW === true || k.ArrowUp === true,
      down: k.KeyS === true || k.ArrowDown === true,
      left: k.KeyA === true || k.ArrowLeft === true,
      right: k.KeyD === true || k.ArrowRight === true,
    };
  }

  // Было ли одиночное нажатие (пробел, R, F, P). Сбрасывает флаг — сработает один раз
  consume(code) {
    const was = this.pressed.has(code);
    this.pressed.delete(code);
    return was;
  }
}
