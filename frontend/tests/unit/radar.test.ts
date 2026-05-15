import { describe, expect, it } from 'vitest';

// Geometry helpers mirror RadarChart.svelte for testable parity.
function pointFor(idx: number, value: number, n: number, radius: number, center: number) {
  const angle = (Math.PI * 2 * idx) / n - Math.PI / 2;
  const r = Math.max(0, Math.min(1, value)) * radius;
  return { x: center + Math.cos(angle) * r, y: center + Math.sin(angle) * r };
}

describe('RadarChart geometry', () => {
  it('first vertex с value=1 lands at top of circle', () => {
    const p = pointFor(0, 1, 8, 100, 200);
    expect(p.x).toBeCloseTo(200, 5);
    expect(p.y).toBeCloseTo(100, 5);
  });

  it('clamps value > 1 to 1', () => {
    const p1 = pointFor(0, 1, 8, 100, 200);
    const p2 = pointFor(0, 5, 8, 100, 200);
    expect(p1).toEqual(p2);
  });

  it('clamps value < 0 to 0 (center)', () => {
    const p = pointFor(0, -1, 8, 100, 200);
    expect(p.x).toBeCloseTo(200, 5);
    expect(p.y).toBeCloseTo(200, 5);
  });

  it('places n vertices evenly around the circle', () => {
    const points = Array.from({ length: 8 }, (_, i) => pointFor(i, 1, 8, 100, 200));
    // Vertex 0 на top, vertex 4 на bottom (180° apart)
    const p4 = points[4];
    expect(p4?.x).toBeCloseTo(200, 5);
    expect(p4?.y).toBeCloseTo(300, 5);
  });
});
