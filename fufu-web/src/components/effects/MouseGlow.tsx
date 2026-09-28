import { useEffect, useState, useRef, useCallback } from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';
import { anim } from '@/config/animation';
import { createAnimationLock } from '@/lib/animation-lock';

export default function MouseGlow() {
  const { size, stiffness, damping, mass, opacity, blur } = anim.mouseGlow;
  const [visible, setVisible] = useState(false);
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const springX = useSpring(mx, { stiffness, damping, mass });
  const springY = useSpring(my, { stiffness, damping, mass });

  // Refs for debounce and animation lock (used in effect, stable across renders)
  const showTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lockRef = useRef(createAnimationLock(300));
  const rafRef = useRef(0);
  // Keep a ref to visible so the effect doesn't need to depend on it,
  // avoiding listener re-registration on every visibility change.
  const visibleRef = useRef(false);

  // Keep visibleRef in sync with state
  const setVisibleAndRef = useCallback((v: boolean) => {
    visibleRef.current = v;
    setVisible(v);
  }, []);

  useEffect(() => {
    const handleMove = (e: MouseEvent) => {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        mx.set(e.clientX);
        my.set(e.clientY);
      });

      // Debounce: wait 300ms before showing the glow to avoid flicker on quick passes.
      // Use ref to avoid depending on `visible` in the effect dependency array.
      if (!visibleRef.current) {
        if (showTimerRef.current !== null) {
          clearTimeout(showTimerRef.current);
        }
        showTimerRef.current = setTimeout(() => {
          if (lockRef.current.tryAcquire('glow')) {
            lockRef.current.acquire('glow');
            setVisibleAndRef(true);
          }
          showTimerRef.current = null;
        }, 300);
      }
    };

    const handleLeave = () => {
      // Immediately hide on mouse leave, and reset lock
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
  }, [setVisibleAndRef]); // stable dependency — no re-registration on visibility change

  return (
    <motion.div
      className="pointer-events-none fixed inset-0 z-[100]"
      style={{ opacity: visible ? 1 : 0, willChange: 'transform' }}
      transition={{ duration: 0.3 }}
    >
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size,
          height: size,
          x: springX,
          y: springY,
          translateX: '-50%',
          translateY: '-50%',
          willChange: 'transform',
          background: `radial-gradient(circle at center, rgba(255,185,145,${opacity}) 0%, rgba(255,170,135,${opacity * 0.4}) 30%, rgba(255,155,125,${opacity * 0.1}) 55%, transparent 75%)`,
          filter: `blur(${blur}px)`,
        }}
      />
    </motion.div>
  );
}
