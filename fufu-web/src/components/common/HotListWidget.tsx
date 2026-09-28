import { Link } from 'react-router-dom';
import { Fire, CaretRight } from '@phosphor-icons/react';
import { motion } from 'framer-motion';
import { useDailyRanking } from '../../hooks/useRanking';

function formatHotScore(score: number): string {
  if (score >= 10000) {
    const v = score / 10000;
    return v % 1 === 0 ? `${v}万` : `${v.toFixed(1).replace(/\.0$/, '')}万`;
  }
  if (score >= 1000) {
    return score.toLocaleString('zh-CN');
  }
  return String(score);
}

function MedalBadge({ rank }: { rank: number }) {
  if (rank === 1) {
    return (
      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white"
        style={{ background: 'linear-gradient(135deg, #FFD700, #FFA500)' }}>
        1
      </span>
    );
  }
  if (rank === 2) {
    return (
      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white"
        style={{ background: 'linear-gradient(135deg, #C0C0C0, #A8A8A8)' }}>
        2
      </span>
    );
  }
  if (rank === 3) {
    return (
      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white"
        style={{ background: 'linear-gradient(135deg, #CD7F32, #B87333)' }}>
        3
      </span>
    );
  }
  return (
    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-fufu-text-muted bg-fufu-teal-soft/30">
      {rank}
    </span>
  );
}

export default function HotListWidget() {
  const { data, isLoading } = useDailyRanking(5);
  const items = data?.items ?? [];
  const showLoading = isLoading;

  return (
    <motion.div
      className="fufu-card rounded-fufu-card overflow-hidden"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-5 py-3.5 border-b border-fufu-teal-soft/20 bg-gradient-to-r from-fufu-pink-soft/30 to-fufu-cream">
        <Fire size={20} weight="fill" className="text-fufu-pink" />
        <h3 className="font-cute text-sm text-fufu-text">今日热榜</h3>
        {data?.updated_at && (
          <span className="ml-auto font-body text-[10px] text-fufu-text-muted">
            {new Date(data.updated_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })} 更新
          </span>
        )}
      </div>

      {/* List */}
      <div className="px-2 py-1">
        {showLoading ? (
          <div className="space-y-2 p-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="skeleton w-6 h-6 rounded-full flex-shrink-0" />
                <div className="skeleton h-4 flex-1 rounded" />
                <div className="skeleton h-4 w-12 rounded flex-shrink-0" />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="py-6 text-center">
            <p className="font-cute text-xs text-fufu-text-muted">暂无热度数据～</p>
          </div>
        ) : (
          <div className="py-1">
            {items.map((item, i) => (
              <Link
                key={item.article_id}
                to={`/articles/${item.article_id}`}
                className="flex items-center gap-3 px-3 py-2 rounded-fufu hover:bg-fufu-teal-soft/10 transition-colors group"
              >
                <MedalBadge rank={item.rank} />
                <span className="flex-1 min-w-0 font-body text-xs text-fufu-text group-hover:text-fufu-pink transition-colors truncate">
                  {item.title}
                </span>
                <span className="flex-shrink-0 font-cute text-[11px] text-fufu-text-muted group-hover:text-fufu-teal-deep transition-colors">
                  {formatHotScore(item.hot_score)}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Footer link */}
      <Link
        to="/ranking"
        className="flex items-center justify-center gap-1 px-5 py-2.5 border-t border-fufu-teal-soft/20 font-cute text-xs text-fufu-text-light hover:text-fufu-teal-deep hover:bg-fufu-teal-soft/5 transition-all"
      >
        查看完整榜单
        <CaretRight size={14} weight="bold" />
      </Link>
    </motion.div>
  );
}
