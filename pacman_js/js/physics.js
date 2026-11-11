// js/physics.js — все формулы игры: расстояние, угроза, громкость «Бу!»
import {
  THREAT_0, THREAT_DECAY, BOO_POWER_0, BOO_DECAY, BOO_THRESHOLD,
} from './constants.js';

export class Physics {
  // Расстояние по Пифагору между клетками a=[x,y] и b=[x,y]: √(dx² + dy²)
  static distance(a, b) {
    return Math.hypot(b[0] - a[0], b[1] - a[1]);
  }

  // Угроза от призрака на расстоянии d: threat(d) = THREAT_0 * e^(-k*d)
  static threat(d, k = THREAT_DECAY, v0 = THREAT_0) {
    return v0 * Math.exp(-k * d);
  }

  // Обратная задача: на каком расстоянии угроза равна порогу
  // из v0 * e^(-k*d) = threshold  ->  d = ln(v0 / threshold) / k
  static limitDistance(threshold, k = THREAT_DECAY, v0 = THREAT_0) {
    return Math.log(v0 / threshold) / k;
  }

  // Громкость «Бу!» на расстоянии d (модификатор делает «Бу!» громче)
  static booLoudness(d, modifier = 1) {
    return BOO_POWER_0 * modifier * Math.exp(-BOO_DECAY * d);
  }

  // Докуда «Бу!» ещё пугает: d = ln(BOO_POWER_0 * modifier / BOO_THRESHOLD) / BOO_DECAY
  static booLimit(modifier = 1) {
    return Math.log((BOO_POWER_0 * modifier) / BOO_THRESHOLD) / BOO_DECAY;
  }
}
