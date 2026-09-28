import { useRef, type ReactNode } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import { useSettingsStore } from '@/stores/settingsStore';

interface ScrollParallaxProps {
  children: ReactNode;
  speed?: number;
  className?: string;
}

/**
 * Wraps a decoration element and applies a subtle vertical parallax
 * shift based on the element's scroll position in the viewport.
 * Positive speed = moves slower than scroll (background feel).
 *
 * Optimization notes:
 * - framer-motion's useScroll internally uses rAF-throttled passive scroll listeners
 *   and cleans up automatically on unmount.
 * - When effect intensity is 0, the component renders a plain div to avoid
 *   unnecessary motion value subscriptions.
 */
export default function ScrollParallax({
  children,
  speed = 0.25,
  className,
}: ScrollParallaxProps) {
  const ref = useRef<HTMLDivElement>(null);
  const intensity = useSettingsStore((s) => s.settings.effectIntensity);
  const factor = intensity / 100;

  // Skip parallax entirely when effects are disabled
  if (factor < 0.05) {
    return <div className={className}>{children}</div>;
  }

  const effectiveSpeed = speed * factor;
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  });

  // Transform the scroll progress (0-1) to a y-offset range.
  // Uses useTransform for GPU-accelerated, rAF-throttled updates.
  const y = useTransform(
    scrollYProgress,
    [0, 1],
    [effectiveSpeed * 32, -effectiveSpeed * 32],
  );

  return (
    <motion.div ref={ref} className={className} style={{ y, willChange: 'transform' }}>
      {children}
    </motion.div>
  );
}
