import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { CaretDown, CaretUp, Newspaper } from '@phosphor-icons/react';
import { useAggregation } from '../../hooks/useAggregation';
import type { RelatedSourceItem } from '../../api/aggregation';

// ===== 视角徽章配置 =====
const PERSPECTIVE_CONFIG: Record<string, { color: string; bg: string; border: string; icon: string }> = {
  '同一事件': {
    color: 'text-fufu-mint',
    bg: 'bg-fufu-soft-green/20',
    border: 'border-fufu-mint/30',
    icon: '🔄',
  },
  '相关报道': {
    color: 'text-fufu-lavender',
    bg: 'bg-fufu-soft-purple/20',
    border: 'border-fufu-lavender/30',
    icon: '📡',
  },
  '补充视角': {
    color: 'text-fufu-teal-deep',
    bg: 'bg-fufu-soft-blue/20',
    border: 'border-fufu-teal-deep/30',
    icon: '💡',
  },
};

function getPerspectiveConfig(perspective: string) {
  return PERSPECTIVE_CONFIG[perspective] || PERSPECTIVE_CONFIG['补充视角'];
}

// ===== Animation variants =====
const fadeInUp = {
  hidden: { opacity: 0, y: 28 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: 'easeOut' },
  },
};

const staggerContainer = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.08 },
  },
};

const cardVariant = {
  hidden: { opacity: 0, x: -20 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.4, ease: 'easeOut' },
  },
};

// ===== 单张相关文章卡片 =====
function RelatedCard({
  item,
  index,
  navigate,
}: {
  item: RelatedSourceItem;
  index: number;
  navigate: (path: string) => void;
}) {
  const cfg = getPerspectiveConfig(item.perspective);
  const pct = Math.round(item.similarity_score * 100);
  const { article } = item;

  return (
    <motion.div
      variants={cardVariant}
      className={`border rounded-fufu-card p-4 transition-all duration-200 hover:shadow-fufu-hover cursor-pointer group ${cfg.bg} ${cfg.border}`}
      onClick={() => navigate(`/article/${article.id}`)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          navigate(`/article/${article.id}`);
        }
      }}
    >
      {/* 顶部：来源 + 相似度 */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-white/60 flex items-center justify-center text-xs">
            <Newspaper size={14} className="text-fufu-text-light" />
          </span>
          <span className="font-cute text-sm text-fufu-text truncate">
            {article.source_name || '未知来源'}
          </span>
        </div>
        <span className="flex-shrink-0 font-body text-xs text-fufu-text-muted ml-2">
          相似度{' '}
          <span className="font-cute text-fufu-teal-deep">{pct}%</span>
        </span>
      </div>

      {/* 标题 */}
      <p className="font-body text-sm text-fufu-text leading-snug line-clamp-2 mb-2 group-hover:text-fufu-teal-deep transition-colors">
        {article.title}
      </p>

      {/* 摘要片段 */}
      {item.overlap_keywords && item.overlap_keywords.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {item.overlap_keywords.slice(0, 5).map((kw) => (
            <span
              key={kw}
              className="inline-block px-2 py-0.5 text-xs font-body rounded-full bg-white/50 text-fufu-text-light border border-white/60"
            >
              {kw}
            </span>
          ))}
        </div>
      )}

      {/* 视角徽章 */}
      <div className="flex items-center gap-1.5">
        <span>{cfg.icon}</span>
        <span
          className={`inline-flex items-center px-2.5 py-0.5 text-xs font-cute rounded-fufu-tag ${cfg.color} bg-white/60`}
        >
          {item.perspective}
        </span>
      </div>
    </motion.div>
  );
}

// ===== 加载骨架 =====
function AggregationSkeleton() {
  return (
    <div className="bg-white/70 backdrop-blur-sm rounded-fufu-card border border-fufu-highlight/30 p-5 md:p-6 shadow-fufu">
      <div className="skeleton h-5 w-48 rounded mb-4" />
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="border rounded-fufu p-4 bg-fufu-cream/40">
            <div className="flex items-center justify-between mb-2">
              <div className="skeleton h-4 w-24 rounded" />
              <div className="skeleton h-4 w-14 rounded" />
            </div>
            <div className="skeleton h-4 w-full rounded mb-2" />
            <div className="skeleton h-3 w-3/4 rounded mb-2" />
            <div className="skeleton h-4 w-16 rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}

// ===== 主组件 =====
export default function AggregatedView({ articleId }: { articleId: number }) {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useAggregation(articleId);
  const [showCompare, setShowCompare] = useState(false);

  // 加载中
  if (isLoading) {
    return <AggregationSkeleton />;
  }

  // 错误或无数据——不展示任何内容
  if (isError || !data || !data.related_sources || data.related_sources.length === 0) {
    return null;
  }

  const { related_sources, common_points, different_points } = data;
  const hasCompare = common_points.length > 0 || different_points.length > 0;

  return (
    <motion.div
      variants={fadeInUp}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: '-60px' }}
      className="mb-6"
    >
      <div className="bg-white/70 backdrop-blur-sm rounded-fufu-card border border-fufu-highlight/30 p-5 md:p-6 shadow-fufu">
        {/* 标题栏 */}
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xl">📰</span>
          <h3 className="font-cute text-fufu-text text-base">
            同一事件，不同视角
          </h3>
          <span className="font-body text-xs text-fufu-text-muted">
            ({related_sources.length} 个来源)
          </span>
        </div>

        {/* 相关文章卡片列表 */}
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          className="grid grid-cols-1 gap-3"
        >
          {related_sources.map((item, idx) => (
            <RelatedCard
              key={item.article.id}
              item={item}
              index={idx}
              navigate={navigate}
            />
          ))}
        </motion.div>

        {/* 对比查看（可展开） */}
        {hasCompare && (
          <div className="mt-4 pt-4 border-t border-fufu-highlight/40">
            <button
              onClick={() => setShowCompare(!showCompare)}
              className="flex items-center gap-1.5 font-cute text-sm text-fufu-teal-deep hover:text-fufu-teal transition-colors"
            >
              <span>👉 对比查看</span>
              {showCompare ? (
                <CaretUp size={16} />
              ) : (
                <CaretDown size={16} />
              )}
            </button>

            <AnimatePresence>
              {showCompare && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3, ease: 'easeOut' }}
                  className="overflow-hidden"
                >
                  <div className="mt-3 space-y-3">
                    {/* 相同点 */}
                    {common_points.length > 0 && (
                      <div className="bg-fufu-soft-green/10 border border-fufu-mint/15 rounded-fufu p-3">
                        <p className="font-cute text-xs text-fufu-mint mb-1.5">
                          ✅ 相同点
                        </p>
                        <ul className="space-y-1">
                          {common_points.map((point, i) => (
                            <li
                              key={i}
                              className="font-body text-xs text-fufu-text leading-relaxed flex items-start gap-1.5"
                            >
                              <span className="text-fufu-text-muted mt-0.5 flex-shrink-0">
                                •
                              </span>
                              <span>{point}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* 不同点 */}
                    {different_points.length > 0 && (
                      <div className="bg-fufu-soft-purple/10 border border-fufu-lavender/15 rounded-fufu p-3">
                        <p className="font-cute text-xs text-fufu-lavender mb-1.5">
                          🔀 不同点
                        </p>
                        <ul className="space-y-1">
                          {different_points.map((point, i) => (
                            <li
                              key={i}
                              className="font-body text-xs text-fufu-text leading-relaxed flex items-start gap-1.5"
                            >
                              <span className="text-fufu-text-muted mt-0.5 flex-shrink-0">
                                •
                              </span>
                              <span>{point}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </motion.div>
  );
}
