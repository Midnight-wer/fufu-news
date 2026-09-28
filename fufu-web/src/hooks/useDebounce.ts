import { useRef, useCallback, useState, useEffect } from 'react';

/** 防抖回调 — 用于"重新加载"等按钮，delayMs 内只执行一次 */
export function useDebouncedCallback<T extends (...args: any[]) => any>(
  callback: T,
  delayMs: number = 800,
): T {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lockedRef = useRef(false);

  return useCallback(
    (...args: any[]) => {
      if (lockedRef.current) return;
      lockedRef.current = true;
      callback(...args);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        lockedRef.current = false;
      }, delayMs);
    },
    [callback, delayMs],
  ) as unknown as T;
}

/** 通用防抖值 — 输入框使用 */
export function useDebounce<T>(value: T, delayMs: number = 500): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
