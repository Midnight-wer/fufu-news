import { useEffect, useRef, useCallback } from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';
import { anim } from '@/config/animation';
import { useSettingsStore } from '@/stores/settingsStore';

interface ParticleData {
  id: number;
  baseX: number;
  baseY: number;
  size: number;
  duration: number;
  delay: number;
  drift: number;
  color: string;
  glowColor: string;
}

const PARTICLE_COUNT = anim.floatingParticles.count;
const COLORS = [
  'rgba(0,229,255,0.13)',
  'rgba(57,197,187,0.12)',
  'rgba(0,229,255,0.10)',
  'rgba(255,182,193,0.10)',
  'rgba(197,168,225,0.10)',
  'rgba(0,229,255,0.08)',
];

const REPULSION_RADIUS = 160;
const MAX_REPULSION = 65;

function randomParticle(id: number, factor: number): ParticleData {
  const alpha = 0.12 + 0.08 * factor;
  const idx = id % COLORS.length;
  return {
    id,
    baseX: 5 + Math.random() * 90,
    baseY: 60 + Math.random() * 40,
    size: 3 + Math.random() * 8 * factor,
    duration:
      anim.floatingParticles.minDuration +
      Math.random() * (anim.floatingParticles.maxDuration - anim.floatingParticles.minDuration),
    delay: Math.random() * 12,
    drift: (Math.random() - 0.5) * 60 * factor,
    color: COLORS[idx].replace(/[\d.]+\)$/, `${alpha})`),
    glowColor: COLORS[idx].replace(/[\d.]+\)$/, `${alpha * 0.6})`),
  };
}

function Particle({
  data,
  mouseRef,
}: {
  data: ParticleData;
  mouseRef: React.MutableRefObject<{ x: number; y: number }>;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const tx = useMotionValue(0);
  const ty = useMotionValue(0);
  const springTX = useSpring(tx, { stiffness: 20, damping: 18 });
  const springTY = useSpring(ty, { stiffness: 20, damping: 18 });

  useEffect(() => {
    const startTime = performance.now();
    let raf = 0;

    const tick = (now: number) => {
      const elapsed = (now - startTime) / 1000 - data.delay;
      const cycleDuration = data.duration + anim.floatingParticles.repeatDelay;

      if (elapsed < 0) {
        raf = requestAnimationFrame(tick);
        return;
      }

      const cycleElapsed = elapsed % cycleDuration;
      const animProgress = Math.min(1, Math.max(0, cycleElapsed / data.duration));

      const floatY = -animProgress * window.innerHeight * 0.5;
      const floatX = Math.sin(elapsed * 0.22 + data.id * 0.7) * data.drift * 0.6;

      let rx = 0,
        ry = 0;
      const mouse = mouseRef.current;
      const el = elRef.current;
      if (el && mouse.x > 0) {
        const rect = el.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const dx = cx - mouse.x;
        const dy = cy - mouse.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < REPULSION_RADIUS && dist > 1) {
          const strength = Math.pow(1 - dist / REPULSION_RADIUS, 2.5);
          rx = (dx / dist) * MAX_REPULSION * strength;
          ry = (dy / dist) * MAX_REPULSION * strength;
        }
      }

      tx.set(floatX + rx);
      ty.set(floatY + ry);
      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <motion.div
      ref={elRef}
      className="absolute rounded-full pointer-events-none"
      style={{
        left: `${data.baseX}%`,
        top: `${data.baseY}%`,
        width: data.size,
        height: data.size,
        x: springTX,
        y: springTY,
        background: data.color,
        boxShadow: `0 0 ${data.size * 4}px ${data.glowColor}`,
        willChange: 'transform',
      }}
    />
  );
}

export default function FloatingParticles() {
  const mouseRef = useRef({ x: -999, y: -999 });
  const particlesRef = useRef<ParticleData[]>([]);
  const intensity = useSettingsStore((s) => s.settings.effectIntensity);
  const factor = intensity / 100;

  const handleMouse = useCallback((e: MouseEvent) => {
    mouseRef.current = { x: e.clientX, y: e.clientY };
  }, []);

  if (particlesRef.current.length === 0) {
    particlesRef.current = Array.from({ length: PARTICLE_COUNT }, (_, i) =>
      randomParticle(i, factor),
    );
  }

  useEffect(() => {
    if (factor < 0.05) return;
    window.addEventListener('mousemove', handleMouse, { passive: true });
    return () => window.removeEventListener('mousemove', handleMouse);
  }, [factor]);

  if (factor < 0.05) return null;

  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden" style={{ zIndex: 0 }}>
      {particlesRef.current.map((p) => (
        <Particle key={p.id} data={p} mouseRef={mouseRef} />
      ))}
    </div>
  );
}
