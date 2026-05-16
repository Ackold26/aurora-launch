// Aurora Launch — trajectory pattern utilities for Step 4 wizard anchors.
//
// SO-1 simplification: instead of 12 manual sliders, customer picks a
// named pattern (rampup/sustain/decline) + intensity 1-10.  Custom mode
// exposes the raw sliders only when explicitly requested.
//
// Pure functions — no side effects, no imports from app code.  Safe to
// import in tests without jsdom or Tauri stubs.

export type TrajectoryPattern = 'rampup' | 'sustain' | 'decline' | 'custom';

export interface TrajectoryDescriptor {
  id: TrajectoryPattern;
  label_ru: string;
  description_ru: string;
  /** Business scenario where this pattern is most appropriate. */
  use_case_ru: string;
}

export const TRAJECTORY_PATTERNS: readonly TrajectoryDescriptor[] = [
  {
    id: 'rampup',
    label_ru: 'Нарастание',
    description_ru: 'Awareness постепенно растёт',
    use_case_ru: 'Запуск нового бренда / расширение каналов',
  },
  {
    id: 'sustain',
    label_ru: 'Устойчивый рост',
    description_ru: 'Awareness стабильно поддерживается',
    use_case_ru: 'Зрелый бренд / линейная поддержка',
  },
  {
    id: 'decline',
    label_ru: 'Снижение',
    description_ru: 'Сезонность / конец кампании / постлончевый спад',
    use_case_ru: 'Постсезонные категории (например, противопростудные летом)',
  },
  {
    id: 'custom',
    label_ru: 'Свой график',
    description_ru: 'Указать значения вручную (только для опытных)',
    use_case_ru: 'Если у вас есть прогноз от исследования',
  },
];

/**
 * Generates normalised trajectory values (0.05..1.0) for preview/visualisation.
 *
 * - rampup:  exponential growth from 0.1 → target
 * - sustain: stable plateau ≈ target with gentle sine wave (±0.05)
 * - decline: peak at target → exponential decay to 0.1
 * - custom:  returns null (caller uses custom_trajectory instead)
 *
 * @param pattern   Trajectory shape identifier.
 * @param intensity Strength multiplier 1-10; maps target = intensity / 10.
 * @param horizon_periods Number of discrete time periods to generate.
 * @returns Array of `horizon_periods` values in [0.05, 1], or null for custom.
 */
export function generateTrajectory(
  pattern: TrajectoryPattern,
  intensity: number,
  horizon_periods: number,
): number[] | null {
  if (pattern === 'custom') return null;

  const target = Math.max(0.1, Math.min(1, intensity / 10));
  const count = Math.max(1, Math.floor(horizon_periods));
  const points: number[] = [];

  for (let i = 0; i < count; i++) {
    const t = count === 1 ? 0 : i / (count - 1); // normalised position 0..1
    let v: number;

    if (pattern === 'rampup') {
      // Smooth exponential approach: starts near 0.1, reaches target at t=1.
      v = 0.1 + (target - 0.1) * (1 - Math.exp(-3 * t));
    } else if (pattern === 'sustain') {
      // Gentle sine wave centred on target.
      v = target + Math.sin(t * Math.PI * 2) * 0.05;
    } else {
      // decline: starts at target, quadratic decay toward 0.1.
      v = target - (target - 0.1) * t * t;
    }

    points.push(Math.max(0.05, Math.min(1, v)));
  }

  return points;
}

/**
 * Validates that an intensity value is a whole integer in [1, 10].
 * Rejects floats, strings coerced to numbers that are not integers,
 * and values outside the valid range.
 */
export function validIntensity(value: unknown): boolean {
  if (typeof value !== 'number') return false;
  return Number.isInteger(value) && value >= 1 && value <= 10;
}
