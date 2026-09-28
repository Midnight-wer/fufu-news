import { useRef, useState, useEffect, useCallback, type ReactNode } from 'react';
import { motion } from 'framer-motion';
import { anim } from '@/config/animation';
import { useSettingsStore } from '@/stores/settingsStore';
import { createAnimationLock } from '@/lib/animation-lock';

interface JellyCardProps {
  children: ReactNode;
  className?: string;
}

export default function JellyCard({ children, className = '' }: JellyCardProps) {
  const intensity = useSettingsStore((s) => s.settings.effectIntensity);
  const factor = intensity / 100;

  // Track whether hover has been active long enough (300ms debounce)
  const [isHovered, setIsHovered] = useState(false);
  const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lockRef = useRef(createAnimationLock(300));

  if (factor < 0.15) {
    return <div className={className}>{children}</div>;
  }

  const s = anim.jellyCard.scaleAmount;
  const scaleAmount = 1 + (s - 1) * factor;

  /**
   * Debounced hover enter: wait 300ms before triggering the spring scale animation.
   * The animation lock prevents re-triggering while the spring is still settling.
   */
  const handleMouseEnter = useCallback(() => {
    if (hoverTimerRef.current !== null) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }

    if (lockRef.current.tryAcquire('jelly')) {
      hoverTimerRef.current = setTimeout(() => {
        lockRef.current.acquire('jelly');
        setIsHovered(true);
        hoverTimerRef.current = null;
      }, 300);
    }
  }, []);

  const handleMouseLeave = useCallback(() => {
    // Cleanup: cancel debounce timer, reset hover state, release lock
    if (hoverTimerRef.current !== null) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
    setIsHovered(false);
    lockRef.current.reset();
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (hoverTimerRef.current !== null) {
        clearTimeout(hoverTimerRef.current);
      }
      lockRef.current.reset();
    };
  }, []);

  return (
    <motion.div
      className={className}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      animate={
        isHovered
          ? { scaleX: scaleAmount, scaleY: 2 - scaleAmount }
          : { scaleX: 1, scaleY: 1 }
      }
      whileTap={{ scaleX: 0.97, scaleY: 1.03 }}
      transition={{
        type: 'spring',
        stiffness: anim.jellyCard.stiffness,
        damping: anim.jellyCard.damping,
      }}
      style={{
        willChange: 'transform',
        backfaceVisibility: 'hidden',
      }}
    >
      {children}
    </motion.div>
  );
}
