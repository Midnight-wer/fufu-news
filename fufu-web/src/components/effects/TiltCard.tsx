import { useRef, useState, useEffect, useCallback, type ReactNode, type MouseEvent } from 'react';
import { motion } from 'framer-motion';
import { anim } from '@/config/animation';
import { useSettingsStore } from '@/stores/settingsStore';
import { createAnimationLock } from '@/lib/animation-lock';

interface TiltCardProps {
  children: ReactNode;
  className?: string;
  maxTilt?: number;
}

export default function TiltCard({ children, className = '', maxTilt }: TiltCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [hoverReady, setHoverReady] = useState(false);
  const intensity = useSettingsStore((s) => s.settings.effectIntensity);
  const factor = intensity / 100;

  // Refs for debounce timer, animation lock, and rAF
  const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lockRef = useRef(createAnimationLock(300));
  const rafRef = useRef(0);
  const pendingTiltRef = useRef({ x: 0, y: 0 });

  const effectiveMaxTilt = maxTilt ?? anim.tiltCard.maxTilt * factor;
  const stiffness = anim.tiltCard.stiffness * (0.5 + 0.5 * factor);
  const damping = anim.tiltCard.damping;

  /**
   * Throttled update via requestAnimationFrame to avoid flooding React state
   * on every mousemove pixel. Only updates when hoverReady is true (300ms debounce passed).
   */
  const handleMouseEnter = useCallback(() => {
    // Clear any pending leave timer
    if (hoverTimerRef.current !== null) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }

    // Debounce: wait 300ms before enabling tilt tracking
    // While lock is active (animation settling), new enters are ignored
    if (lockRef.current.tryAcquire('tilt')) {
      hoverTimerRef.current = setTimeout(() => {
        lockRef.current.acquire('tilt');
        setHoverReady(true);
        hoverTimerRef.current = null;
      }, 300);
    }
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent<HTMLDivElement>) => {
      if (!ref.current || factor < 0.1 || !hoverReady) return;

      // Use rAF to throttle state updates — at most one per frame
      cancelAnimationFrame(rafRef.current);
      const rect = ref.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const cx = rect.width / 2;
      const cy = rect.height / 2;
      pendingTiltRef.current = {
        x: ((y - cy) / cy) * -effectiveMaxTilt,
        y: ((x - cx) / cx) * effectiveMaxTilt,
      };
      rafRef.current = requestAnimationFrame(() => {
        setTilt(pendingTiltRef.current);
      });
    },
    [effectiveMaxTilt, factor, hoverReady],
  );

  const handleMouseLeave = useCallback(() => {
    // Cleanup: cancel debounce timer, stop rAF, reset tilt and lock
    if (hoverTimerRef.current !== null) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
    cancelAnimationFrame(rafRef.current);
    rafRef.current = 0;
    setHoverReady(false);
    setTilt({ x: 0, y: 0 });
    lockRef.current.reset();
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (hoverTimerRef.current !== null) {
        clearTimeout(hoverTimerRef.current);
      }
      cancelAnimationFrame(rafRef.current);
      lockRef.current.reset();
    };
  }, []);

  const hoverScale = 1 + 0.01 * factor;

  return (
    <motion.div
      ref={ref}
      className={className}
      onMouseEnter={handleMouseEnter}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      animate={{ rotateX: tilt.x, rotateY: tilt.y, scale: hoverReady ? hoverScale : 1 }}
      transition={{
        type: 'spring',
        stiffness,
        damping,
        mass: anim.tiltCard.mass,
      }}
      style={{
        perspective: anim.tiltCard.perspective,
        transformStyle: 'preserve-3d',
        backfaceVisibility: 'hidden',
        WebkitBackfaceVisibility: 'hidden',
        willChange: 'transform',
      }}
    >
      {children}
    </motion.div>
  );
}
