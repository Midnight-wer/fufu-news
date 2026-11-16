import { useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Heart,
  Fire,
  TagSimple,
  Newspaper,
  Sparkle,
  CaretRight,
  CaretLeft,
} from '@phosphor-icons/react';
import { motion } from 'framer-motion';
import { usePersonalizedRecommendations } from '../../hooks/useRecommendations';

/** 格式化热度分 */
function formatHotScore(score: number): string {
  if (score >= 10000) {
    const v = score / 10000;
    return v % 1 === 0 ? `${v}万` : `${v.toFixed(1).replace(/\.0$/, '')}万`;
  }
  if (score >= 1000) return score.toLocaleString('zh-CN');
  return String(score);
}

/** 推荐理由 → 图标 + 配色 */
function getReasonMeta(reason: string): { icon: React.ReactNode; bg: string; textColor: string } {
  if (reason.includes('喜欢') || reason.includes('阅读')) {
    return {
      icon: <Heart size={12} weight="fill" />,
      bg: 'bg-fufu-pink-soft/30',
      textColor: 'text-fufu-pink',
    };
  }
  if (reason.includes('热门') || reason.includes('趋势')) {
    return {
      icon: <Fire size={12} weight="fill" />,
      bg: 'bg-orange-100',
      textColor: 'text-orange-500',
    };
  }
  if (reason.includes('标签') || reason.includes('相似')) {
    return {
      icon: <TagSimple size={12} weight="fill" />,
      bg: 'bg-fufu-teal-soft/30',
      textColor: 'text-fufu-teal-deep',
    };
  }
  if (reason.includes('常读') || reason.includes('来源') || reason.includes('同源')) {
    return {
      icon: <Newspaper size={12} weight="fill" />,
      bg: 'bg-fufu-lavender/20',
      textColor: 'text-fufu-lavender',
    };
  }
  return {
    icon: <Sparkle size={12} weight="fill" />,
    bg: 'bg-fufu-highlight/60',
    textColor: 'text-fufu-text-light',
  };
}

/** 单张推荐卡片 */
function RecommendationCard({
  item,
}: {
  item: {
    article_id: number;
    title: string;
    source_name: string;
    image_url?: string;
    hot_score: number;
    reason: string;
  };
}) {
  const reasonMeta = getReasonMeta(item.reason);

  return (
    <Link
      to={`/articles/${item.article_id}`}
      className={[
        // 固定宽度 + 禁止收缩 → 核心防挤压
        'shrink-0',
        'min-w-[180px] w-[180px]',
        'sm:min-w-[200px] sm:w-[200px]',
        // 卡片样式
        'flex flex-col gap-2',
        'p-3 sm:p-4',
        'rounded-fufu-card',
        'bg-white/80 backdrop-blur-sm',
        'border border-fufu-highlight/30',
        'hover:border-fufu-teal/30 hover:shadow-fufu-hover',
        'transition-all duration-200 group',
      ].join(' ')}
    >
      {/* 标题：双行截断 + 固定高度 */}
      <h3
        className={[
          'font-cute text-xs sm:text-sm text-fufu-text leading-snug',
          'line-clamp-2',
          'group-hover:text-fufu-teal-deep transition-colors',
          // 固定高度防止无标题时塌陷
          'min-h-[2rem] sm:min-h-[2.5rem]',
        ].join(' ')}
      >
        {item.title}
      </h3>

      {/* 来源：单行截断 */}
      <span className="font-body text-[10px] sm:text-xs text-fufu-text-muted truncate">
        {item.source_name || '未知来源'}
      </span>

      {/* 理由标签 + 热度 */}
      <div className="flex items-center gap-1.5 flex-wrap mt-auto">
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-cute text-[10px] ${reasonMeta.bg} ${reasonMeta.textColor}`}
        >
          {reasonMeta.icon}
          <span className="truncate max-w-[100px]">{item.reason}</span>
        </span>
        {item.hot_score > 0 && (
          <span className="inline-flex items-center gap-0.5 text-[10px] font-body text-fufu-text-muted">
            <Fire size={10} weight="fill" className="text-orange-400" />
            {formatHotScore(item.hot_score)}
          </span>
        )}
      </div>
    </Link>
  );
}

/** 骨架卡片 */
function SkeletonCard() {
  return (
    <div
      className={[
        'shrink-0 min-w-[180px] w-[180px] sm:min-w-[200px] sm:w-[200px]',
        'p-3 sm:p-4 rounded-fufu-card bg-white/50 border border-fufu-highlight/20 animate-pulse',
        'flex flex-col gap-2',
      ].join(' ')}
    >
      <div className="skeleton h-4 w-full rounded" />
      <div className="skeleton h-4 w-3/4 rounded" />
      <div className="skeleton h-3 w-16 rounded mt-1" />
      <div className="skeleton h-5 w-20 rounded-full mt-1" />
    </div>
  );
}

export default function RecommendationWidget() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const scrollAmount = 216; // card + gap

  const { data, isLoading } = usePersonalizedRecommendations(10, [], true);
  const items = data?.items ?? [];
  const showLoading = isLoading;

  const handleScrollLeft = useCallback(() => {
    scrollRef.current?.scrollBy({ left: -scrollAmount * 2, behavior: 'smooth' });
  }, []);

  const handleScrollRight = useCallback(() => {
    scrollRef.current?.scrollBy({ left: scrollAmount * 2, behavior: 'smooth' });
  }, []);

  if (!showLoading && items.length === 0) return null;

  return (
    <motion.div
      className="mb-8"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.15 }}
    >
      {/* ===== 外层 relative 包裹（箭头绝对定位锚点） ===== */}
      <div className="relative w-full">
        {/* 标题 */}
        <div className="flex items-center gap-2 mb-4 pl-1">
          <span className="text-lg">💝</span>
          <h3 className="font-cute text-base text-fufu-text">猜你喜欢</h3>
          <span className="font-body text-[11px] text-fufu-text-muted ml-1 hidden sm:inline">
            为你精心挑选
          </span>

          {/* 左右箭头（绝对定位，不占用滚动空间） */}
          {!showLoading && items.length > 4 && (
            <div className="ml-auto flex items-center gap-1.5 pr-1">
              <button
                onClick={handleScrollLeft}
                className="w-7 h-7 rounded-full bg-white/80 border border-fufu-highlight/30 flex items-center justify-center text-fufu-text-muted hover:text-fufu-teal hover:border-fufu-teal/30 transition-all"
                aria-label="向左滚动"
              >
                <CaretLeft size={14} weight="bold" />
              </button>
              <button
                onClick={handleScrollRight}
                className="w-7 h-7 rounded-full bg-white/80 border border-fufu-highlight/30 flex items-center justify-center text-fufu-text-muted hover:text-fufu-teal hover:border-fufu-teal/30 transition-all"
                aria-label="向右滚动"
              >
                <CaretRight size={14} weight="bold" />
              </button>
            </div>
          )}
        </div>

        {/* ===== 横向滚动容器 ===== */}
        <div
          ref={scrollRef}
          className={[
            'w-full',
            'overflow-x-auto overflow-y-hidden',
            'scrollbar-fufu',
            'flex gap-3 sm:gap-4',
            'py-3 px-1', // 内边距撑开，防阴影被切
          ].join(' ')}
        >
          {showLoading
            ? Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)
            : items.map((item, idx) => (
                <motion.div
                  key={item.article_id}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05, duration: 0.3 }}
                  className="shrink-0"
                >
                  <RecommendationCard item={item} />
                </motion.div>
              ))}

          {/* 右侧渐变遮罩 */}
          {!showLoading && items.length > 4 && (
            <div className="shrink-0 w-8 bg-gradient-to-l from-fufu-cream to-transparent pointer-events-none" />
          )}
        </div>
      </div>

      {/* 空状态 */}
      {!showLoading && items.length === 0 && (
        <div className="py-8 text-center bg-white/40 rounded-fufu-card border border-fufu-highlight/20">
          <p className="font-cute text-sm text-fufu-text-muted">
            🌸 多读几篇文章，fufu 就能更好地了解你的喜好啦～
          </p>
        </div>
      )}
    </motion.div>
  );
}
