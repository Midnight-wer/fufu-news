import { useRef, useEffect, type ReactNode } from 'react';
import { motion, useSpring, useMotionValue } from 'framer-motion';
import { anim } from '@/config/animation';
import { useSettingsStore } from '@/stores/settingsStore';
import { createAnimationLock } from '@/lib/animation-lock';

interface ScrollRubberBandProps {
  children: ReactNode;
  scrollContainerRef: React.RefObject<HTMLElement | null>;
}

/**
 * Overscroll rubber-band effect.
 *
 * When the user scrolls past the top/bottom boundary of the container,
 * the content is temporarily displaced (rubber-band stretch) and springs back.
 *
 * Fixes applied:
 * - Animation lock: prevents re-triggering while the spring is still settling.
 * - rAF-throttled wheel handling: each wheel event cancels the previous rAF,
 *   ensuring at most one queued reset per frame.
 * - Proper cleanup: all listeners, rAFs, and the lock are reset on unmount.
 */
export default function ScrollRubberBand({
  children,
  scrollContainerRef,
}: ScrollRubberBandProps) {
  const intensity = useSettingsStore((s) => s.settings.effectIntensity);
  const factor = intensity / 100;
  const maxOverscroll = anim.scrollRubberBand.maxOverscroll * factor;
  const { stiffness, damping } = anim.scrollRubberBand;

  const y = useMotionValue(0);
  const springY = useSpring(y, { stiffness, damping });

  // Track boundary state and animation lock
  const stateRef = useRef({ atTop: true, atBottom: false });
  const lockRef = useRef(createAnimationLock(300));

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el || maxOverscroll < 1) return;

    let wheelRaf = 0;

    const onWheel = (e: WheelEvent) => {
      const { scrollTop, scrollHeight, clientHeight } = el;

      // Content fits entirely — no overscroll possible
      if (scrollHeight <= clientHeight) return;

      const atTop = scrollTop <= 0;
      const atBottom = scrollTop + clientHeight >= scrollHeight - 1;

      const isOverscrolling =
        (atTop && e.deltaY < 0) || (atBottom && e.deltaY > 0);

      if (!isOverscrolling) return;

      // Animation lock: ignore wheel events while the spring is settling back
      if (!lockRef.current.tryAcquire('rubber')) return;

      e.preventDefault();
      cancelAnimationFrame(wheelRaf);

      lockRef.current.acquire('rubber');

      const overscroll = Math.max(
        -maxOverscroll,
        Math.min(maxOverscroll, -e.deltaY * 0.3),
      );
      y.set(overscroll);

      // Schedule spring-back via rAF, then release lock after spring settles
      wheelRaf = requestAnimationFrame(() => {
        y.set(0);
        lockRef.current.release();
      });
    };

    const onScroll = () => {
      stateRef.current.atTop = el.scrollTop <= 0;
      stateRef.current.atBottom =
        el.scrollTop + el.clientHeight >= el.scrollHeight - 1;
    };

    // passive: false on wheel so we can call preventDefault()
    el.addEventListener('wheel', onWheel, { passive: false });
    el.addEventListener('scroll', onScroll, { passive: true });

    return () => {
      el.removeEventListener('wheel', onWheel);
      el.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(wheelRaf);
      lockRef.current.reset();
    };
  }, [maxOverscroll, scrollContainerRef, y]);

  if (maxOverscroll < 1) return <>{children}</>;

  return (
    <motion.div
      style={{
        y: springY,
        willChange: 'transform',
      }}
    >
      {children}
    </motion.div>
  );
}
