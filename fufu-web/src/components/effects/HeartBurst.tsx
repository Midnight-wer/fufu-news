import { useMemo, useRef, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { anim } from '@/config/animation';
import { createAnimationLock } from '@/lib/animation-lock';

interface HeartBurstProps {
  active: boolean;
  x: number;
  y: number;
  count?: number;
}

const HEART_CHARS = ['\u{1F338}', '\u{1F495}', '\u{1F497}', '\u{1F496}', '✨', '\u{1F380}'];

export default function HeartBurst({
  active,
  x,
  y,
  count = anim.heartBurst.count,
}: HeartBurstProps) {
  // Track whether this specific burst invocation should render.
  // We gate on active AND a lock check to prevent rapid re-triggering.
  const [shouldRender, setShouldRender] = useState(false);
  const lockRef = useRef(createAnimationLock(anim.heartBurst.duration * 1000));
  const burstIdRef = useRef(0);

  // When active becomes true, try to acquire the lock.
  // If acquired, generate a new burst ID and render.
  useEffect(() => {
    if (active) {
      if (lockRef.current.tryAcquire(`burst-${burstIdRef.current}`)) {
        burstIdRef.current += 1;
        lockRef.current.acquire(`burst-${burstIdRef.current}`);
        setShouldRender(true);
      }
    } else {
      setShouldRender(false);
    }
  }, [active]);

  // Release lock and stop rendering after animation duration
  useEffect(() => {
    if (!shouldRender) return;
    const timer = setTimeout(() => {
      setShouldRender(false);
      lockRef.current.release();
    }, anim.heartBurst.duration * 1000 + 100); // small buffer after animation ends
    return () => clearTimeout(timer);
  }, [shouldRender]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      lockRef.current.reset();
    };
  }, []);

  // Each burst gets a unique key prefix so AnimatePresence re-animates
  // even when the heart indices are the same across bursts.
  const burstKey = burstIdRef.current;

  const hearts = useMemo(() => {
    if (!shouldRender) return [];
    return Array.from({ length: count }, (_, i) => {
      const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.6;
      return {
        id: `${burstKey}-${i}`,
        angle,
        dist:
          anim.heartBurst.distMin +
          Math.random() * (anim.heartBurst.distMax - anim.heartBurst.distMin),
        size:
          anim.heartBurst.sizeMin +
          Math.random() * (anim.heartBurst.sizeMax - anim.heartBurst.sizeMin),
        rot: (Math.random() - 0.5) * 80,
        char: HEART_CHARS[i % HEART_CHARS.length],
      };
    });
  }, [shouldRender, count, burstKey]);

  if (!shouldRender) return null;

  return (
    <AnimatePresence>
      {hearts.map((h) => (
        <motion.span
          key={h.id}
          className="fixed pointer-events-none select-none z-[200]"
          style={{ left: x, top: y, fontSize: h.size, willChange: 'transform' }}
          initial={{ opacity: 1, scale: 0, x: '-50%', y: '-50%' }}
          animate={{
            opacity: 0,
            scale: [0, 1.2, 0.3],
            x: `calc(-50% + ${Math.cos(h.angle) * h.dist}px)`,
            y: `calc(-50% + ${Math.sin(h.angle) * h.dist}px)`,
            rotate: h.rot,
          }}
          transition={{ duration: anim.heartBurst.duration, ease: 'easeOut' }}
        >
          {h.char}
        </motion.span>
      ))}
    </AnimatePresence>
  );
}
