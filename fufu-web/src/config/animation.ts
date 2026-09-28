/** 所有动效参数集中管理 — 单源调整入口 */

export const anim = {
  mouseGlow: {
    size: 260,
    stiffness: 42,
    damping: 24,
    mass: 0.35,
    opacity: 0.07,
    blur: 6,
  },
  tiltCard: {
    maxTilt: 2.5,
    perspective: 1200,
    stiffness: 280,
    damping: 28,
    mass: 0.5,
  },
  clickRipple: {
    duration: 0.45,
    maxOpacity: 0.35,
    sizeRatio: 0.7,
    removeAfter: 550,
  },
  floatingParticles: {
    count: 10,
    maxOpacity: 0.55,
    minDuration: 10,
    maxDuration: 26,
    repeatDelay: 3,
  },
  heartBurst: {
    count: 10,
    duration: 0.65,
    distMin: 40,
    distMax: 90,
    sizeMin: 10,
    sizeMax: 22,
  },
  mouseTrail: {
    dotCount: 8,
    dotSize: 6,
    gap: 18,
    stiffness: 80,
    damping: 18,
    maxOpacity: 0.35,
  },
  jellyCard: {
    scaleAmount: 1.02,
    stiffness: 200,
    damping: 15,
  },
  scrollRubberBand: {
    maxOverscroll: 24,
    stiffness: 150,
    damping: 18,
  },
  companion: {
    size: 80,
    floatAmplitude: 6,
    floatPeriod: 3,
  },
};

export type AnimConfig = typeof anim;

/**
 * 根据特效强度 (0–100) 线性缩放数值型参数。
 * intensity=0 时返回最小值（通常为原始值的 10%），intensity=100 时返回完整值。
 */
export function scaleByIntensity<T extends Record<string, number>>(
  cfg: T,
  intensity: number,
): T {
  const factor = intensity / 100;
  const scaled = {} as Record<string, number>;
  for (const key of Object.keys(cfg)) {
    scaled[key] = cfg[key] * (0.1 + 0.9 * factor);
  }
  return scaled as T;
}
