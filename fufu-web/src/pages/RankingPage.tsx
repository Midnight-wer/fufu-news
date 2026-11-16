import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Fire,
  Calendar,
  Trophy,
  ArrowUp,
  ArrowDown,
  ArrowRight,
  Sparkle,
  CaretRight,
} from '@phosphor-icons/react';
import { motion, AnimatePresence } from 'framer-motion';
import { useDailyRanking, useWeeklyRanking, useMonthlyRanking } from '../hooks/useRanking';
import type { RankingItem } from '../api/ranking';

const TABS = [
  { key: 'daily' as const, icon: Fire, label: '今日', emoji: '🔥', limit: 10 },
  { key: 'weekly' as const, icon: Calendar, label: '本周', emoji: '📅', limit: 15 },
  { key: 'monthly' as const, icon: Trophy, label: '本月', emoji: '🏆', limit: 20 },
] as const;

type TabKey = (typeof TABS)[number]['key'];
const TAB_INDEX: Record<TabKey, number> = { daily: 0, weekly: 1, monthly: 2 };

function formatHotScore(score: number): string {
  if (score >= 10000) {
    const v = score / 10000;
    return v % 1 === 0 ? `${v}万` : `${v.toFixed(1).replace(/\.0$/, '')}万`;
  }
  if (score >= 1000) return score.toLocaleString('zh-CN');
  return String(score);
}

// ── 奖牌 ──
function MedalBadge({ rank }: { rank: number }) {
  const gradients: Record<number, string> = {
    1: 'linear-gradient(135deg, #FFD700, #FFA500)',
    2: 'linear-gradient(135deg, #C0C0C0, #A0A0A0)',
    3: 'linear-gradient(135deg, #CD7F32, #A0522D)',
  };
  const glow: Record<number, string> = {
    1: '0 4px 16px rgba(255,165,0,0.35)',
    2: '0 4px 16px rgba(160,160,160,0.3)',
    3: '0 4px 16px rgba(205,127,50,0.3)',
  };
  if (rank <= 3) {
    return (
      <div
        className="flex-shrink-0 w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center"
        style={{ background: gradients[rank], boxShadow: glow[rank] }}
      >
        <span className="font-cute text-base sm:text-lg text-white drop-shadow-sm">{rank}</span>
      </div>
    );
  }
  return (
    <span className="flex-shrink-0 w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center font-cute text-base sm:text-lg text-fufu-text-muted bg-fufu-teal-soft/15">
      {rank}
    </span>
  );
}

function TrendBadge({ trend }: { trend?: string }) {
  if (trend === 'up') return <ArrowUp size={12} weight="bold" className="text-fufu-mint" />;
  if (trend === 'down') return <ArrowDown size={12} weight="bold" className="text-fufu-error" />;
  if (trend === 'new') return <Sparkle size={12} weight="fill" className="text-fufu-teal" />;
  return <ArrowRight size={12} className="text-fufu-text-muted/40" />;
}

function HotLabel({ label }: { label?: string }) {
  if (!label) return null;
  const colors: Record<string, string> = {
    爆: 'linear-gradient(135deg, #FF4444, #FF6B6B)',
    热: 'linear-gradient(135deg, #FF8C00, #FFA500)',
    新: 'linear-gradient(135deg, #00BFFF, #1E90FF)',
  };
  const icons: Record<string, string> = { 爆: '🔥', 热: '⭐', 新: '🆕' };
  return (
    <span
      className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full font-cute text-[10px] text-white shrink-0"
      style={{ background: colors[label] || colors['新'] }}
    >
      {icons[label] || '🆕'}
      {label}
    </span>
  );
}

function RankingRow({ item, rank }: { item: RankingItem; rank: number }) {
  const isTop3 = rank <= 3;
  return (
    <Link to={`/articles/${item.article_id}`}>
      <motion.div
        className={`group flex items-center gap-2 sm:gap-4 px-3 sm:px-5 py-2.5 sm:py-4 transition-all duration-200 cursor-pointer
          ${
            isTop3
              ? 'rounded-fufu-card border border-transparent hover:border-fufu-teal/15'
              : 'rounded-fufu border-b border-fufu-teal-soft/8 last:border-b-0'
          }`}
        style={
          isTop3
            ? {
                background:
                  rank === 1
                    ? 'linear-gradient(135deg, rgba(255,215,0,0.06), rgba(255,255,255,0.4))'
                    : rank === 2
                      ? 'linear-gradient(135deg, rgba(192,192,192,0.06), rgba(255,255,255,0.4))'
                      : 'linear-gradient(135deg, rgba(205,127,50,0.06), rgba(255,255,255,0.4))',
              }
            : undefined
        }
        whileHover={isTop3 ? { scale: 1.01, y: -1 } : { x: 4 }}
        transition={{ type: 'spring', stiffness: 300, damping: 25 }}
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
      >
        <MedalBadge rank={rank} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
            {item.hot_label && <HotLabel label={item.hot_label} />}
            <span className="font-body text-[10px] sm:text-[11px] text-fufu-text-muted truncate max-w-[140px]">
              {item.source_name}
            </span>
          </div>
          <h3
            className={`font-cute text-xs sm:text-sm ${isTop3 ? 'sm:text-base' : ''} text-fufu-text group-hover:text-fufu-pink transition-colors line-clamp-1`}
          >
            {item.title}
          </h3>
          {isTop3 && (
            <div className="flex items-center gap-2 sm:gap-3 mt-1">
              <span className="font-body text-[10px] sm:text-[11px] text-fufu-text-muted">
                👁 {formatHotScore(item.view_count)}
              </span>
              <span className="font-body text-[10px] sm:text-[11px] text-fufu-text-muted">
                💬 {formatHotScore(item.comment_count)}
              </span>
              <span className="font-body text-[10px] sm:text-[11px] text-fufu-text-muted">
                ⭐ {formatHotScore(item.collect_count)}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
          <span
            className={`font-cute ${isTop3 ? 'text-base sm:text-lg font-bold' : 'text-xs sm:text-sm'} ${
              isTop3 ? 'text-fufu-pink' : 'text-fufu-text-light'
            }`}
          >
            {formatHotScore(item.hot_score)}
          </span>
          <div className="w-5 sm:w-6 flex justify-center">
            <TrendBadge trend={item.trend} />
          </div>
        </div>

        {!isTop3 && (
          <CaretRight
            size={12}
            className="text-fufu-text-muted/20 group-hover:text-fufu-teal transition-colors shrink-0"
          />
        )}
      </motion.div>
    </Link>
  );
}

function SkeletonRow({ isTop3 }: { isTop3: boolean }) {
  return (
    <div
      className={`flex items-center gap-3 sm:gap-4 px-3 sm:px-5 ${isTop3 ? 'py-4 sm:py-5' : 'py-3 sm:py-4'}`}
    >
      <div className="skeleton w-9 h-9 sm:w-10 sm:h-10 rounded-xl shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="skeleton h-3 w-16 sm:w-20 rounded" />
        <div className="skeleton h-3.5 sm:h-4 w-3/4 rounded" />
        {isTop3 && <div className="skeleton h-3 w-32 sm:w-40 rounded" />}
      </div>
      <div className="skeleton h-4 sm:h-5 w-10 sm:w-14 rounded shrink-0" />
    </div>
  );
}

export default function RankingPage() {
  const [tab, setTab] = useState<TabKey>('daily');

  const dailyQuery = useDailyRanking(TABS[0].limit);
  const weeklyQuery = useWeeklyRanking(TABS[1].limit);
  const monthlyQuery = useMonthlyRanking(TABS[2].limit);

  const activeQuery = tab === 'daily' ? dailyQuery : tab === 'weekly' ? weeklyQuery : monthlyQuery;
  const items = activeQuery.data?.items ?? [];
  const isLoading = activeQuery.isLoading || activeQuery.isPlaceholderData;
  const isError = activeQuery.isError;
  const updatedAt = activeQuery.data?.updated_at;

  const activeIndex = TAB_INDEX[tab];

  return (
    <div>
      {/* Page header */}
      <div className="mb-4 sm:mb-6">
        <h2 className="font-cute text-2xl sm:text-3xl text-fufu-text flex items-center gap-2">
          <Fire size={24} weight="fill" className="text-fufu-pink animate-pulse-soft" />
          排行榜
        </h2>
        <p className="font-body text-xs sm:text-sm text-fufu-text-light mt-1">
          看看大家都在看什么～ 🔥
        </p>
      </div>

      {/* ──── Tab 切换器：绝对定位白色浮层 + 层级隔离 ──── */}
      <div className="relative w-full rounded-fufu-card border border-fufu-teal-soft/20 bg-white/40 p-1 overflow-hidden mb-4 sm:mb-6">
        {/* 选中滑块 — z-0 底层，白色卡片样式 */}
        <div
          className="absolute top-1 bottom-1 rounded-fufu bg-white shadow-fufu-sm transition-all duration-300 ease-out z-0"
          style={{
            width: `calc((100% - 8px) / 3)`,
            left: `calc((100% - 8px) / 3 * ${activeIndex} + 4px)`,
          }}
        />

        {/* 按钮组 — z-10 上层，文字永不消失 */}
        <div className="relative z-10 flex">
          {TABS.map(({ key, icon: Icon, label }, idx) => {
            const isActive = activeIndex === idx;
            return (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={[
                  'flex-1',
                  'flex items-center justify-center',
                  'gap-1.5 sm:gap-2',
                  'py-2.5 sm:py-3',
                  'font-cute text-xs sm:text-sm',
                  'transition-colors duration-200',
                  'touch-target shrink-0',
                  isActive
                    ? 'text-fufu-teal-deep font-medium'
                    : 'text-fufu-text-light hover:text-fufu-text',
                ].join(' ')}
              >
                <Icon size={16} weight={isActive ? 'fill' : 'regular'} className="shrink-0" />
                <span className="shrink-0">{label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Update time */}
      {updatedAt && !isLoading && items.length > 0 && (
        <p className="font-body text-[11px] text-fufu-text-muted mb-3 text-right">
          更新于{' '}
          {new Date(updatedAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
        </p>
      )}

      {/* ──── 内容区 ──── */}
      <div className="fufu-card rounded-fufu-card overflow-hidden">
        {isError ? (
          /* 错误状态 */
          <div className="text-center py-16 sm:py-20">
            <p className="text-5xl sm:text-6xl mb-4 animate-float">😿</p>
            <p className="font-cute text-lg sm:text-xl text-fufu-text">加载榜单失败啦～</p>
            <p className="font-body text-xs sm:text-sm text-fufu-text-light mt-2">
              检查一下后端服务是不是还在运行呢？
            </p>
            <button className="fufu-btn-primary mt-4 text-sm" onClick={() => activeQuery.refetch()}>
              重新加载
            </button>
          </div>
        ) : isLoading ? (
          /* 骨架屏 */
          <div>
            <div className="space-y-1 p-3 sm:p-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <SkeletonRow key={i} isTop3 />
              ))}
            </div>
            <div className="px-4 sm:px-5 py-2 border-t border-fufu-teal-soft/8">
              <div className="skeleton h-3 w-16 rounded" />
            </div>
            <div className="divide-y divide-fufu-teal-soft/5">
              {Array.from({ length: 7 }).map((_, i) => (
                <SkeletonRow key={i} isTop3={false} />
              ))}
            </div>
          </div>
        ) : items.length === 0 ? (
          /* 空状态 — 带引导 */
          <div className="text-center py-16 sm:py-20 px-4">
            <p className="text-5xl sm:text-6xl mb-4 animate-float">{TABS[activeIndex].emoji}</p>
            <h3 className="font-cute text-lg sm:text-xl text-fufu-text">
              {TABS[activeIndex].label}还没有热榜数据～
            </h3>
            <p className="font-body text-xs sm:text-sm text-fufu-text-light mt-2 max-w-sm mx-auto leading-relaxed">
              多浏览一些文章，热度数据就会自动生成啦 🎵
            </p>
            <div className="mt-4 flex items-center justify-center gap-2">
              <Link to="/articles" className="fufu-btn-primary text-xs sm:text-sm">
                去逛逛首页
              </Link>
            </div>
          </div>
        ) : (
          /* 榜单列表 */
          <AnimatePresence mode="wait">
            <motion.div
              key={tab}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.2 }}
            >
              {/* Top 3 */}
              <div className="p-3 sm:p-4 space-y-1">
                {items.slice(0, 3).map((item, i) => (
                  <motion.div
                    key={item.article_id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.06, duration: 0.25 }}
                  >
                    <RankingRow item={item} rank={item.rank} />
                  </motion.div>
                ))}
              </div>

              {/* 分隔 */}
              {items.length > 3 && (
                <div className="px-5 sm:px-7 py-2 border-t border-fufu-teal-soft/8">
                  <span className="font-cute text-[10px] sm:text-[11px] text-fufu-text-muted tracking-wider">
                    ── 更多热门 ──
                  </span>
                </div>
              )}

              {/* 4+ 列表 */}
              <div className="pb-2">
                {items.slice(3).map((item, i) => (
                  <motion.div
                    key={item.article_id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: (i + 3) * 0.03, duration: 0.2 }}
                  >
                    <RankingRow item={item} rank={item.rank} />
                  </motion.div>
                ))}
              </div>
            </motion.div>
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
