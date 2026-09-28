import { useState, useRef, useCallback, useEffect, type MouseEvent, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { anim } from '@/config/animation';
import { createAnimationLock } from '@/lib/animation-lock';

interface Ripple {
  id: number;
  x: number;
  y: number;
  size: number;
}

let globalRippleId = 0;

export function useClickRipple() {
  const [ripples, setRipples] = useState<Ripple[]>([]);

  // Per-instance animation lock and timer tracking
  const lockRef = useRef(createAnimationLock(300));
  const timerIdsRef = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());

  // Cleanup all pending timers on unmount
  useEffect(() => {
    return () => {
      const timers = timerIdsRef.current;
      timers.forEach((id) => clearTimeout(id));
      timers.clear();
      lockRef.current.reset();
    };
  }, []);

  const trigger = useCallback((e: MouseEvent<HTMLElement>) => {
    // Animation lock: ignore clicks while a ripple animation is settling (300ms)
    if (!lockRef.current.tryAcquire(`ripple-${globalRippleId}`)) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const maxDim = Math.max(rect.width, rect.height);
    const id = ++globalRippleId;

    lockRef.current.acquire(`ripple-${id}`);

    setRipples((prev) => [
      ...prev,
      { id, x: e.clientX - rect.left, y: e.clientY - rect.top, size: maxDim },
    ]);

    // Schedule cleanup of this ripple
    const timer = setTimeout(() => {
      setRipples((prev) => prev.filter((r) => r.id !== id));
      lockRef.current.release();
      timerIdsRef.current.delete(timer);
    }, anim.clickRipple.removeAfter);
    timerIdsRef.current.add(timer);
  }, []);

  return { ripples, trigger };
}

export function RippleOverlay({ ripples }: { ripples: Ripple[] }) {
  return (
    <AnimatePresence>
      {ripples.map((r) => (
        <motion.div
          key={r.id}
          initial={{
            width: 0,
            height: 0,
            opacity: anim.clickRipple.maxOpacity,
            x: r.x,
            y: r.y,
          }}
          animate={{
            width: r.size * anim.clickRipple.sizeRatio,
            height: r.size * anim.clickRipple.sizeRatio,
            opacity: 0,
            x: r.x - (r.size * anim.clickRipple.sizeRatio) / 2,
            y: r.y - (r.size * anim.clickRipple.sizeRatio) / 2,
          }}
          exit={{ opacity: 0 }}
          transition={{ duration: anim.clickRipple.duration, ease: 'easeOut' }}
          className="absolute rounded-full pointer-events-none"
          style={{
            willChange: 'transform, opacity',
            background:
              'radial-gradient(circle, rgba(255,143,180,0.4) 0%, rgba(255,192,217,0.15) 45%, transparent 70%)',
          }}
        />
      ))}
    </AnimatePresence>
  );
}

export function ClickRippleWrapper({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  const { ripples, trigger } = useClickRipple();
  return (
    <div className={`relative overflow-hidden ${className}`} onClick={trigger}>
      {children}
      <RippleOverlay ripples={ripples} />
    </div>
  );
}
