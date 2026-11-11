// js/eventLog.js — «чёрный ящик»: журнал событий и статистика партии
export class EventLog {
  constructor({ print = false, limit = 500 } = {}) {
    this.events = [];   // список { timeMs, type, text }
    this.print = print; // печатать ли события сразу в консоль
    this.limit = limit; // храним не больше limit последних событий
    this.counts = {};   // сколько событий каждого типа: { state: 3, eat: 10, ... }
  }

  add(timeMs, type, text) {
    const ev = { timeMs, type, text };
    this.events.push(ev);
    if (this.events.length > this.limit) this.events.shift();
    this.counts[type] = (this.counts[type] ?? 0) + 1;
    if (this.print) console.log(`${(timeMs / 1000).toFixed(1)} с | ${type} | ${text}`);
    return ev;
  }

  count(type) { return this.counts[type] ?? 0; }

  last(n = 5) { return this.events.slice(-n); }

  // Статистика по механике игры
  get stats() {
    return {
      ghostMoves: this.count('ghost'),
      eaten: this.count('eat'),
      stateChanges: this.count('state'),
      boos: this.count('boo'),
      scared: this.count('scared'),
      stuckFixes: this.count('stuck'),
    };
  }
}
