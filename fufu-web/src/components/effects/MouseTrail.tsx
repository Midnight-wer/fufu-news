import { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { motion, useMotionValue, useSpring, type MotionValue } from 'framer-motion';
import { anim } from '@/config/animation';
import { useSettingsStore } from '@/stores/settingsStore';
import { createAnimationLock } from '@/lib/animation-lock';

const COLORS = [
  'rgba(255,181,170,0.9)',
  'rgba(255,212,204,0.85)',
  'rgba(196,228,245,0.8)',
  'rgba(255,243,196,0.85)',
  'rgba(168,230,207,0.8)',
  'rgba(228,212,245,0.85)',
  'rgba(255,200,180,0.8)',
  'rgba(180,210,255,0.8)',
];
const MAX_DOTS = anim.mouseTrail.dotCount;

interface TrailDot {
  id: number;
  color: string;
  glowColor: string;
  size: number;
  springX: MotionValue<number>;
  springY: MotionValue<number>;
}

function TrailDotComp({
  dot,
  idx,
  total,
  opacity,
  scale,
}: {
  dot: TrailDot;
  idx: number;
  total: number;
  opacity: number;
  scale: number;
}) {
  const fade = opacity * (1 - idx / total) * 0.85;
  const s = dot.size * scale * (1 - idx * 0.04);
  return (
    <motion.div
      className="pointer-events-none fixed rounded-full"
      style={{
        width: s,
        height: s,
        x: dot.springX,
        y: dot.springY,
        translateX: '-50%',
        translateY: '-50%',
        background: dot.color,
        opacity: fade,
        boxShadow: `0 0 ${s * 3}px ${dot.glowColor}, 0 0 ${s * 8}px ${dot.glowColor}`,
        willChange: 'transform',
      }}
    />
  );
}

export default function MouseTrail() {
  const showTrail = useSettingsStore((s) => s.settings.showMouseTrail);
  const intensity = useSettingsStore((s) => s.settings.effectIntensity);
  const {
    dotCount: baseDotCount,
    dotSize: baseDotSize,
    stiffness,
    damping,
    maxOpacity,
  } = anim.mouseTrail;
  const factor = intensity / 100;

  const dotCount = Math.max(3, Math.round(baseDotCount * factor));
  const dotSize = baseDotSize * (0.5 + 0.5 * factor);
  const effectiveOpacity = maxOpacity * (0.3 + 0.7 * factor);

  const mx = useMotionValue(-100);
  const my = useMotionValue(-100);
  const [visible, setVisible] = useState(false);
  const positionsRef = useRef<{ x: number; y: number }[]>(
    Array.from({ length: MAX_DOTS }, () => ({ x: -100, y: -100 })),
  );

  // Refs for debounce, animation lock, and rAF
  const showTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lockRef = useRef(createAnimationLock(300));
  const rafRef = useRef(0);
  const visibleRef = useRef(false);

  const setVisibleAndRef = useCallback((v: boolean) => {
    visibleRef.current = v;
    setVisible(v);
  }, []);

  // ── Step 1: Create MAX_DOTS motion values at top level (unconditional hooks) ──
  // Hooks in fixed-length loops at component top level are valid React.
  // Previously these were inside useMemo(), which violates Rules of Hooks
  // and causes "Cannot read properties of undefined (reading 'length')"
  // when React's areHookInputsEqual tries to diff the dependency array.
  const springPairs: Array<{
    springX: MotionValue<number>;
    springY: MotionValue<number>;
  }> = [];
  for (let i = 0; i < MAX_DOTS; i++) {
    const sx = useMotionValue(-100);
    const sy = useMotionValue(-100);
    const baseStiffness = stiffness * (1 - i * 0.07);
    const baseDamping = damping * (1 - i * 0.04);
    springPairs.push({
      springX: useSpring(sx, { stiffness: baseStiffness, damping: baseDamping }),
      springY: useSpring(sy, { stiffness: baseStiffness, damping: baseDamping }),
    });
  }

  // ── Step 2: Memoize dot metadata (no hooks inside) ──
  const allDots: TrailDot[] = useMemo(
    () =>
      springPairs.map((pair, i) => ({
        id: i,
        color: COLORS[i % COLORS.length],
        glowColor: COLORS[i % COLORS.length].replace(/[\d.]+\)$/, '0.5)'),
        size: dotSize * (1 - i * 0.05),
        springX: pair.springX,
        springY: pair.springY,
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [dotSize, springPairs],
  );

  const activeDots = useMemo(
    () => (Array.isArray(allDots) ? allDots.slice(0, dotCount) : []),
    [allDots, dotCount],
  );

  // ── Mouse move tracking with rAF throttling and 300ms debounce ──
  useEffect(() => {
    if (!showTrail) return;

    let frame = 0;

    const handleMove = (e: MouseEvent) => {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        mx.set(e.clientX);
        my.set(e.clientY);
        positionsRef.current[0] = { x: e.clientX, y: e.clientY };
        frame = (frame + 1) % 2;
        if (frame === 0) {
          for (let i = dotCount - 1; i > 0; i--) {
            positionsRef.current[i] = {
              x: positionsRef.current[i - 1].x,
              y: positionsRef.current[i - 1].y,
            };
          }
        }
      });

      if (!visibleRef.current) {
        if (showTimerRef.current !== null) {
          clearTimeout(showTimerRef.current);
        }
        showTimerRef.current = setTimeout(() => {
          if (lockRef.current.tryAcquire('trail')) {
            lockRef.current.acquire('trail');
            setVisibleAndRef(true);
          }
          showTimerRef.current = null;
        }, 300);
      }
    };

    const handleLeave = () => {
      if (showTimerRef.current !== null) {
        clearTimeout(showTimerRef.current);
        showTimerRef.current = null;
      }
      setVisibleAndRef(false);
      lockRef.current.reset();
    };

    window.addEventListener('mousemove', handleMove, { passive: true });
    document.addEventListener('mouseleave', handleLeave);

    return () => {
      window.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseleave', handleLeave);
      cancelAnimationFrame(rafRef.current);
      if (showTimerRef.current !== null) {
        clearTimeout(showTimerRef.current);
      }
      lockRef.current.reset();
    };
  }, [showTrail, dotCount, setVisibleAndRef, mx, my]);

  // ── Tick loop to sync spring values with position buffer ──
  useEffect(() => {
    if (!showTrail) return;
    const tick = () => {
      for (let i = 0; i < dotCount; i++) {
        const dot = allDots[i];
        if (dot) {
          const p = positionsRef.current[i];
          if (p) {
            dot.springX.set(p.x);
            dot.springY.set(p.y);
          }
        }
      }
    };
    const id = setInterval(tick, 24);
    return () => clearInterval(id);
  }, [showTrail, dotCount, allDots]);

  if (!showTrail || !visible || effectiveOpacity <= 0.01) return null;

  return (
    <div className="pointer-events-none fixed inset-0 z-[99]">
      {activeDots.map((dot, i) => (
        <TrailDotComp
          key={dot.id}
          dot={dot}
          idx={i}
          total={dotCount}
          opacity={effectiveOpacity}
          scale={factor}
        />
      ))}
    </div>
  );
}
