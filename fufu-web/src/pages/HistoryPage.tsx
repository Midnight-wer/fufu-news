import { useNavigate } from 'react-router-dom';
import { Clock, Trash, ArrowUpRight, Warning, X } from '@phosphor-icons/react';
import { motion, AnimatePresence } from 'framer-motion';
import { useState } from 'react';
import { useHistory, useDeleteHistoryItem, useClearHistory } from '../hooks/useHistory';
import type { HistoryItem } from '../api/history';

// ===== Date grouping helpers =====
function isToday(dateStr: string): boolean {
  const d = new Date(dateStr);
  const now = new Date();
  return d.toDateString() === now.toDateString();
}

function isYesterday(dateStr: string): boolean {
  const d = new Date(dateStr);
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  return d.toDateString() === yesterday.toDateString();
}

function isThisWeek(dateStr: string): boolean {
  const d = new Date(dateStr);
  const now = new Date();
  const startOfWeek = new Date(now);
  startOfWeek.setDate(now.getDate() - now.getDay());
  startOfWeek.setHours(0, 0, 0, 0);
  return d >= startOfWeek && !isToday(dateStr) && !isYesterday(dateStr);
}

function getDateGroup(dateStr: string): string {
  if (isToday(dateStr)) return '今天';
  if (isYesterday(dateStr)) return '昨天';
  if (isThisWeek(dateStr)) return '本周';
  return '更早';
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  const hours = d.getHours().toString().padStart(2, '0');
  const minutes = d.getMinutes().toString().padStart(2, '0');
  return `${hours}:${minutes}`;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return '';
  if (seconds < 60) return `${seconds}秒`;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (secs === 0) return `${minutes}分钟`;
  return `${minutes}分${secs}秒`;
}

// ===== Animation variants =====
const itemVariants = {
  hidden: { opacity: 0, x: -12 },
  visible: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 60, transition: { duration: 0.2 } },
};

// ===== History item component =====
function HistoryCard({
  item,
  onDelete,
}: {
  item: HistoryItem;
  onDelete: (id: number) => void;
}) {
  const navigate = useNavigate();

  return (
    <motion.div
      layout
      variants={itemVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className="group flex items-start gap-4 p-4 rounded-fufu-card bg-white/70 backdrop-blur-sm border border-fufu-highlight/20 hover:border-fufu-teal/25 hover:shadow-fufu-hover transition-all duration-200"
    >
      {/* Timeline dot */}
      <div className="relative flex-shrink-0 mt-1.5">
        <div className="w-2.5 h-2.5 rounded-full bg-fufu-teal/60 group-hover:bg-fufu-teal transition-colors" />
        <div className="absolute top-3 left-1/2 -translate-x-1/2 w-px h-[calc(100%+1rem)] bg-fufu-teal/10 group-last:hidden" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <button
            onClick={() => navigate(`/articles/${item.article_id}`)}
            className="text-left flex-1 min-w-0"
          >
            <h3 className="font-body text-sm md:text-base text-fufu-text leading-snug line-clamp-2 hover:text-fufu-teal-deep transition-colors">
              {item.title}
            </h3>
          </button>

          {/* Delete button */}
          <button
            onClick={() => onDelete(item.article_id)}
            className="flex-shrink-0 p-1.5 rounded-fufu text-fufu-text-muted hover:text-fufu-error hover:bg-fufu-error-light/20 opacity-0 group-hover:opacity-100 transition-all"
            title="删除此记录"
          >
            <X size={16} />
          </button>
        </div>

        {/* Meta info */}
        <div className="flex flex-wrap items-center gap-2 mt-1.5 text-xs font-body text-fufu-text-muted">
          {item.source_name && (
            <span className="fufu-tag bg-fufu-teal/8 text-fufu-teal-deep">
              {item.source_name}
            </span>
          )}
          <span className="flex items-center gap-1">
            <Clock size={12} />
            {formatTime(item.read_at)}
          </span>
          {item.read_duration > 0 && (
            <span className="text-fufu-text-light">
              {formatDuration(item.read_duration)}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}

// ===== Main page =====
export default function HistoryPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useHistory(page, 20);
  const deleteItem = useDeleteHistoryItem();
  const clearAll = useClearHistory();
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());

  const items = data?.items || [];
  const total = data?.total || 0;
  const hasMore = page * 20 < total;

  // Group items by date
  const grouped: Record<string, HistoryItem[]> = {};
  for (const item of items) {
    const group = getDateGroup(item.read_at);
    if (!grouped[group]) grouped[group] = [];
    grouped[group].push(item);
  }

  const groupOrder = ['今天', '昨天', '本周', '更早'];

  const handleDelete = async (articleId: number) => {
    setDeletingIds((prev) => new Set(prev).add(articleId));
    try {
      deleteItem.mutate(articleId);
    } finally {
      setTimeout(() => {
        setDeletingIds((prev) => {
          const next = new Set(prev);
          next.delete(articleId);
          return next;
        });
      }, 300);
    }
  };

  const handleClearAll = () => {
    clearAll.mutate();
    setShowClearConfirm(false);
  };

  // ===== Loading skeleton =====
  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="skeleton h-8 w-40 rounded" />
          <div className="skeleton h-8 w-24 rounded" />
        </div>
        <div className="space-y-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton h-20 w-full rounded-fufu-card" />
          ))}
        </div>
      </div>
    );
  }

  // ===== Empty state =====
  if (!items.length) {
    return (
      <div className="max-w-2xl mx-auto text-center py-20">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <p className="text-6xl mb-4 animate-float">📖</p>
          <p className="font-cute text-xl text-fufu-text mb-2">还没有阅读记录哦～</p>
          <p className="font-body text-sm text-fufu-text-muted mb-6">
            去首页逛逛，读几篇文章就来啦～
          </p>
          <button
            onClick={() => navigate('/articles')}
            className="fufu-btn-primary px-6 py-2.5 rounded-fufu-btn font-cute text-sm"
          >
            去首页看看
          </button>
        </motion.div>
      </div>
    );
  }

  // ===== Main =====
  return (
    <div className="max-w-2xl mx-auto pb-16">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between mb-6"
      >
        <div className="flex items-center gap-2">
          <Clock size={24} className="text-fufu-teal-deep" weight="duotone" />
          <h1 className="font-cute text-xl text-fufu-text">阅读历史</h1>
          {total > 0 && (
            <span className="font-body text-xs text-fufu-text-muted bg-fufu-cream px-2 py-0.5 rounded-full">
              {total}
            </span>
          )}
        </div>

        {/* Clear all button */}
        <button
          onClick={() => setShowClearConfirm(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-fufu-btn font-cute text-xs text-fufu-text-muted hover:text-fufu-error hover:bg-fufu-error-light/15 transition-all"
        >
          <Trash size={14} />
          清空全部
        </button>
      </motion.div>

      {/* Grouped timeline */}
      <div className="space-y-6">
        {groupOrder.map((group) => {
          const groupItems = grouped[group];
          if (!groupItems || groupItems.length === 0) return null;

          return (
            <div key={group}>
              <h2 className="font-cute text-sm text-fufu-text-muted mb-3 ml-1">
                {group === '今天' && '☀️ '}
                {group === '昨天' && '🌙 '}
                {group === '本周' && '📅 '}
                {group === '更早' && '🗓️ '}
                {group}
              </h2>

              <AnimatePresence mode="popLayout">
                <div className="space-y-2">
                  {groupItems.map((item) => (
                    <HistoryCard
                      key={item.article_id}
                      item={item}
                      onDelete={handleDelete}
                    />
                  ))}
                </div>
              </AnimatePresence>
            </div>
          );
        })}
      </div>

      {/* Load more */}
      {hasMore && (
        <div className="text-center mt-8">
          <button
            onClick={() => setPage((p) => p + 1)}
            className="fufu-btn-secondary px-6 py-2 rounded-fufu-btn font-cute text-sm"
          >
            加载更多
          </button>
        </div>
      )}

      {/* Clear confirmation modal */}
      <AnimatePresence>
        {showClearConfirm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm"
            onClick={() => setShowClearConfirm(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-white rounded-fufu-card p-6 shadow-fufu max-w-sm w-full mx-4 border border-fufu-highlight/30"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-2 mb-3">
                <Warning size={22} className="text-fufu-pink" weight="duotone" />
                <h3 className="font-cute text-fufu-text">确认清空</h3>
              </div>
              <p className="font-body text-sm text-fufu-text-light mb-5">
                确定要清空全部阅读历史吗？这个操作无法撤销哦～
              </p>
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowClearConfirm(false)}
                  className="px-4 py-2 rounded-fufu-btn font-cute text-sm bg-fufu-cream text-fufu-text-light hover:text-fufu-text transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleClearAll}
                  disabled={clearAll.isPending}
                  className="px-4 py-2 rounded-fufu-btn font-cute text-sm bg-fufu-error-light/30 text-fufu-error hover:bg-fufu-error-light/50 transition-colors disabled:opacity-50"
                >
                  {clearAll.isPending ? '清空中...' : '确认清空'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
