import { useRef, useEffect, useCallback, useMemo } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { AnimatePresence } from 'framer-motion';

interface VirtualArticleListProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
  estimateSize?: number;
  scrollContainerId?: string;
}

export default function VirtualArticleList<T>({
  items,
  renderItem,
  estimateSize = 220,
  scrollContainerId = 'main-scroll',
}: VirtualArticleListProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null);

  const safeItems: T[] = useMemo(() => items ?? [], [items]);

  const getScrollElement = useCallback(() => {
    return document.getElementById(scrollContainerId);
  }, [scrollContainerId]);

  const virtualizer = useVirtualizer({
    count: safeItems.length,
    getScrollElement,
    estimateSize: () => estimateSize,
    overscan: 5,
  });

  useEffect(() => {
    virtualizer.measure();
  }, [safeItems, virtualizer]);

  if (safeItems.length === 0) {
    return <div ref={parentRef} />;
  }

  return (
    <div ref={parentRef}>
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        <AnimatePresence mode="popLayout">
          {virtualizer.getVirtualItems().map((virtualItem) => {
            const item = safeItems[virtualItem.index];
            if (!item) return null;
            return (
              <div
                key={virtualItem.key}
                data-index={virtualItem.index}
                ref={virtualizer.measureElement}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${virtualItem.start}px)`,
                }}
              >
                {renderItem(item, virtualItem.index)}
              </div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
