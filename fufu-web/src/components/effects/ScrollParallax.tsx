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
 * Bug fix (P0 — 崩溃):
 * 之前的实现在 `useScroll` / `useTransform` **之前**就做了条件 return：
 *
 *     if (factor < 0.05) return <div>{children}</div>;   // ← 早期 return
 *     const { scrollYProgress } = useScroll(...);
 *     const y = useTransform(...);
 *
 * 这违反 React Hooks 规则：当特效强度从高调到 0 时，同一次渲染里 Hook 数量
 * 从 3 个变成 1 个，React 会抛出
 *   "Rendered fewer hooks than expected. This may be caused by an accidental
 *    early return statement."
 * 整个页面直接崩掉 —— 用户在设置里拖一下「特效强度」滑块就会白屏。
 *
 * 修复方式：所有 Hook 无条件调用（顺序恒定），把 factor 乘进 useTransform 的输出，
 * 特效关闭时位移恒为 0；早期 return 挪到 Hook 之后，只影响最终渲染的标签类型。
 */
export default function ScrollParallax({ children, speed = 0.25, className }: ScrollParallaxProps) {
  const ref = useRef<HTMLDivElement>(null);
  const intensity = useSettingsStore((s) => s.settings.effectIntensity);
  const factor = intensity / 100;

  // 所有 Hook 无条件调用，保证调用顺序不随 intensity 变化
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  });

  const effectiveSpeed = speed * factor;
  const y = useTransform(scrollYProgress, [0, 1], [effectiveSpeed * 32, -effectiveSpeed * 32]);

  // 特效关闭时渲染普通 div（此时 y 恒为 0，视觉与静态一致）
  if (factor < 0.05) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div ref={ref} className={className} style={{ y, willChange: 'transform' }}>
      {children}
    </motion.div>
  );
}
