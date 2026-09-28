import { useState, useMemo, useCallback, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import { Star, BookmarkSimple, Eye, Shuffle } from '@phosphor-icons/react';
import { motion } from 'framer-motion';
import { useArticles, useToggleFavorite, useToggleLater } from '../hooks/useArticles';
import { useDebouncedCallback } from '../hooks/useDebounce';
import TiltCard from '../components/effects/TiltCard';
import HeartBurst from '../components/effects/HeartBurst';
import { useClickRipple, RippleOverlay } from '../components/effects/ClickRipple';
import ScrollParallax from '../components/effects/ScrollParallax';
import { useCompanionStore } from '../stores/companionStore';
import { useCheckAchievement } from '../hooks/useAchievements';
import { useRecordHit } from '../hooks/useRanking';
import VirtualArticleList from '../components/common/VirtualArticleList';
import HotListWidget from '../components/common/HotListWidget';
import RecommendationWidget from '../components/common/RecommendationWidget';

const SORT_OPTIONS = [
  { value: 'random', label: '🎲 随机推荐' },
  { value: 'latest', label: '🕐 最新发布' },
] as const;

const SINCE_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: '24h', label: '一天内' },
  { value: '3d', label: '三天内' },
  { value: '7d', label: '一周内' },
] as const;

const CATEGORY_OPTIONS = [
  { value: 'all', label: '🌸 全部', emoji: '🌸' },
  { value: '动漫', label: '动漫', emoji: '🎬' },
  { value: '游戏', label: '游戏', emoji: '🎮' },
  { value: '科技', label: '科技', emoji: '💻' },
  { value: '设计', label: '设计', emoji: '🎨' },
  { value: '科普', label: '科普', emoji: '🌿' },
  { value: '综合', label: '综合', emoji: '📰' },
] as const;

/** Fisher-Yates 洗牌算法 */
function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function getSaved(k: string, d: string): string {
  try { return localStorage.getItem(k) || d; } catch { return d; }
}

export default function HomePage() {
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<string>(getSaved('fufu-sort', 'random'));
  const [since, setSince] = useState<string>(getSaved('fufu-since', 'all'));
  const [category, setCategory] = useState<string>(getSaved('fufu-cat', 'all'));
  const [reshuffle, setReshuffle] = useState(0);
  const { data, isLoading, isPlaceholderData, error, refetch } = useArticles(page, 20, sort as 'latest' | 'random', since);
  const showLoading = isLoading || isPlaceholderData;
  const debouncedRefetch = useDebouncedCallback(refetch, 1000);
  const toggleFav = useToggleFavorite();
  const toggleLater = useToggleLater();
  const companion = useCompanionStore();
  const checkAchievement = useCheckAchievement();
  const recordHit = useRecordHit();

  const articles = data?.articles ?? [];
  const total = data?.total ?? 0;
  const pageSize = data?.page_size ?? 20;

  // 前端洗牌——当 sort=random 时对已有结果再次随机化
  const shuffledArticles = useMemo(() => {
    if (sort === 'random' && articles.length > 1) {
      return shuffle(articles);
    }
    return articles;
    // reshuffle 作为依赖，点击洗牌按钮触发重新计算
  }, [articles, sort, reshuffle]);

  const doReshuffle = useCallback(() => {
    setReshuffle((n) => n + 1);
    companion.setMood('happy');
    companion.showMessage('换了一批新闻给你看～🎲');
  }, [companion]);

  const [heartState, setHeartState] = useState<{ active: boolean; x: number; y: number }>({
    active: false, x: 0, y: 0,
  });

  const triggerHeart = (e: MouseEvent, id: number, currentVal: boolean) => {
    if (!currentVal) {
      setHeartState({ active: true, x: e.clientX, y: e.clientY });
      setTimeout(() => setHeartState((s) => ({ ...s, active: false })), 800);
      companion.setMood('happy');
      companion.showMessage('又收藏了一篇心爱的文章呢～🎵');
    }
    toggleFav.mutate({ id, value: !currentVal });
  };

  const { ripples, trigger } = useClickRipple();

  // 按分类筛选 — source_folder + tags
  const filteredArticles = useMemo(() => {
    if (shuffledArticles.length === 0) return [];
    if (category === 'all') return shuffledArticles;
    return shuffledArticles.filter((a) => {
      const folder = a.source_folder || '';
      const tags: string[] = (a.tags ?? []).map((t: string) => t.trim());
      const signals = new Set([folder, ...tags]);
      if (category === '动漫') return signals.has('动漫');
      if (category === '游戏') return signals.has('游戏');
      if (category === '科技') return signals.has('科技');
      if (category === '设计') return signals.has('设计');
      if (category === '综合') return signals.has('综合') || signals.has('文化') || signals.has('趣味') || signals.has('娱乐') || signals.has('科普');
      return false;
    });
  }, [shuffledArticles, category]);

  // 每个分类的文章数量
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: articles.length };
    for (const c of CATEGORY_OPTIONS) {
      if (c.value === 'all') continue;
      counts[c.value] = articles.filter((a) => {
        const folder = a.source_folder || '';
        const tags: string[] = (a.tags ?? []).map((t: string) => t.trim());
        const signals = new Set([folder, ...tags]);
        if (c.value === '动漫') return signals.has('动漫');
        if (c.value === '游戏') return signals.has('游戏');
        if (c.value === '科技') return signals.has('科技');
        if (c.value === '设计') return signals.has('设计');
        if (c.value === '综合') return signals.has('综合') || signals.has('文化') || signals.has('趣味') || signals.has('娱乐') || signals.has('科普');
        return false;
      }).length;
    }
    return counts;
  }, [articles]);

  return (
    <div>
      {/* Hot List Widget */}
      <div className="mb-6">
        <HotListWidget />
      </div>

      {/* Recommendation Widget */}
      <RecommendationWidget />

      {/* Filter Bar */}
      <div className="mb-6">
        {/* 移动端：水平滚动分类栏 */}
        <div className="md:hidden filter-scroll mb-2">
          <div className="flex gap-1.5 px-1 py-2">
            {CATEGORY_OPTIONS.map((c) => (
              <button
                key={c.value}
                onClick={() => { setCategory(c.value); localStorage.setItem('fufu-cat', c.value); setPage(1); }}
                className={`flex-shrink-0 px-3 py-1.5 rounded-fufu-tag font-cute text-xs transition-all duration-200 flex items-center gap-1.5 touch-target ${
                  category === c.value
                    ? 'bg-fufu-teal text-white shadow-sm'
                    : 'bg-white/80 text-fufu-text-light border border-fufu-teal-soft/20'
                }`}
              >
                <span>{c.emoji}</span>
                <span>{c.label}</span>
                {c.value !== 'all' && categoryCounts[c.value] > 0 && (
                  <span className={`ml-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-body leading-none ${
                    category === c.value
                      ? 'bg-white/25 text-white'
                      : 'bg-fufu-teal-soft/30 text-fufu-text-muted'
                  }`}>
                    {categoryCounts[c.value]}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* 桌面端：完整筛选项 */}
        <div className="hidden md:flex flex-wrap items-center gap-2 p-3 rounded-fufu-card bg-white/60 border border-fufu-teal-soft/20">
        {/* 分类筛选 */}
        <div className="flex flex-wrap gap-1.5">
          {CATEGORY_OPTIONS.map((c) => (
            <button
              key={c.value}
              onClick={() => { setCategory(c.value); localStorage.setItem('fufu-cat', c.value); setPage(1); }}
              className={`px-3 py-1.5 rounded-fufu-tag font-cute text-xs transition-all duration-200 flex items-center gap-1.5 ${
                category === c.value
                  ? 'bg-fufu-teal text-white shadow-sm'
                  : 'bg-white text-fufu-text-light hover:bg-fufu-teal-soft/30'
              }`}
            >
              <span>{c.emoji}</span>
              <span>{c.label}</span>
              {c.value !== 'all' && categoryCounts[c.value] > 0 && (
                <span className={`ml-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-body leading-none ${
                  category === c.value
                    ? 'bg-white/25 text-white'
                    : 'bg-fufu-teal-soft/30 text-fufu-text-muted'
                }`}>
                  {categoryCounts[c.value]}
                </span>
              )}
            </button>
          ))}
        </div>

          <div className="flex-1" />

          {/* 时间范围 */}
          <div className="flex gap-1">
            {SINCE_OPTIONS.map((s) => (
              <button
                key={s.value}
                onClick={() => { setSince(s.value); localStorage.setItem('fufu-since', s.value); setPage(1); }}
                className={`px-3 py-1.5 rounded-fufu-tag font-cute text-xs transition-all duration-200 ${
                  since === s.value
                    ? 'bg-fufu-lavender/30 text-fufu-text font-medium'
                    : 'bg-white text-fufu-text-muted hover:bg-fufu-pink-soft/20'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* 排序 */}
          <select
            className="appearance-none fufu-input rounded-fufu-btn py-1.5 pl-3 pr-8 font-cute text-xs cursor-pointer
                       bg-white border-2 border-fufu-teal-soft/30 text-fufu-text-light
                       hover:border-fufu-teal/40 focus:border-fufu-teal transition-all"
            value={sort}
            onChange={(e) => { setSort(e.target.value); localStorage.setItem('fufu-sort', e.target.value); setPage(1); }}
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          {/* 洗牌按钮 */}
          {sort === 'random' && (
            <button
              onClick={doReshuffle}
              className="fufu-btn bg-white text-fufu-text-light hover:text-fufu-teal border-2 border-fufu-teal-soft/20 hover:border-fufu-teal/40 rounded-fufu-btn py-1.5 px-3 font-cute text-xs flex items-center gap-1.5 transition-all"
              title="换一批"
            >
              <Shuffle size={14} /> 换一批
            </button>
          )}
        </div>

        {/* 移动端时间/排序快捷栏 */}
        <div className="md:hidden flex items-center gap-2 filter-scroll py-1">
          {SINCE_OPTIONS.map((s) => (
            <button
              key={s.value}
              onClick={() => { setSince(s.value); localStorage.setItem('fufu-since', s.value); setPage(1); }}
              className={`flex-shrink-0 px-3 py-1.5 rounded-fufu-tag font-cute text-xs transition-all duration-200 touch-target ${
                since === s.value
                  ? 'bg-fufu-lavender/30 text-fufu-text font-medium'
                  : 'bg-white/80 text-fufu-text-muted border border-fufu-teal-soft/20'
              }`}
            >
              {s.label}
            </button>
          ))}
          <select
            className="appearance-none bg-white/80 rounded-fufu-tag py-1.5 pl-3 pr-7 font-cute text-xs cursor-pointer
                       border border-fufu-teal-soft/30 text-fufu-text-light touch-target"
            value={sort}
            onChange={(e) => { setSort(e.target.value); localStorage.setItem('fufu-sort', e.target.value); setPage(1); }}
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          {sort === 'random' && (
            <button
              onClick={doReshuffle}
              className="flex-shrink-0 px-3 py-1.5 rounded-fufu-tag font-cute text-xs flex items-center gap-1.5 transition-all
                         bg-white/80 text-fufu-text-light border border-fufu-teal-soft/20 touch-target"
              title="换一批"
            >
              <Shuffle size={14} /> 换一批
            </button>
          )}
        </div>
      </div>

      <HeartBurst active={heartState.active} x={heartState.x} y={heartState.y} />

      {/* Article list */}
      {error ? (
        <div className="text-center py-20">
          <p className="text-6xl mb-4 animate-float">😿</p>
          <p className="font-cute text-xl text-fufu-text">加载文章失败啦～</p>
          <p className="font-body text-sm text-fufu-text-light mt-2">
            检查一下后端服务是不是还在运行？
          </p>
          <button className="fufu-btn-primary mt-4" onClick={() => debouncedRefetch()}>
            重新加载
          </button>
        </div>
      ) : showLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="fufu-card p-4 sm:p-6 rounded-fufu-card">
              <div className="skeleton h-5 w-3/4 rounded mb-3" />
              <div className="skeleton h-4 w-full rounded mb-2" />
              <div className="skeleton h-4 w-2/3 rounded" />
            </div>
          ))}
        </div>
      ) : filteredArticles.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-6xl mb-4 animate-float">
            {category === '动漫' ? '🎬' : category === '游戏' ? '🎮' : category === '科技' ? '💻' : category === '设计' ? '🎨' : category === '综合' ? '📰' : '🍃'}
          </p>
          <p className="font-cute text-xl text-fufu-text">
            {category === '动漫' ? '动漫区暂时还没有新闻呢～' :
             category === '游戏' ? '游戏区暂时空空的～' :
             category === '科技' ? '科技区等待第一篇投稿～' :
             category === '设计' ? '设计区还在收集灵感～' :
             category === '综合' ? '综合区还没有新动态～' :
             '还没有新闻哦～'}
          </p>
          <p className="font-body text-sm text-fufu-text-light mt-2 max-w-md mx-auto whitespace-pre-line leading-relaxed">
            {category !== 'all'
              ? `"${CATEGORY_OPTIONS.find(c => c.value === category)?.label || category}" 分类下暂无文章。试试：\n• 切换到「🌸 全部」查看所有新闻\n• 点击「订阅源」添加更多${category}类RSS源\n• 等待后台自动抓取（每3分钟一次）`
              : '去「订阅源」页面添加几个感兴趣的RSS源吧！'}
          </p>
          {category !== 'all' && (
            <button
              className="fufu-btn bg-white text-fufu-text-light shadow-fufu rounded-fufu-btn mt-4 text-sm"
              onClick={() => { setCategory('all'); localStorage.setItem('fufu-cat', 'all'); }}
            >
              返回全部新闻 🌸
            </button>
          )}
        </div>
      ) : (
        <VirtualArticleList
          items={filteredArticles}
          estimateSize={220}
          renderItem={(a, idx) => (
            <motion.div
              className="pb-4"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.03, duration: 0.35 }}
            >
              <TiltCard maxTilt={4}>
                <Link
                  to={`/articles/${a.id}`}
                  onClick={() => recordHit.mutate(a.id)}
                  className={`fufu-card p-4 sm:p-6 block group relative overflow-hidden rounded-fufu-card news-card-hover ${
                    a.is_read ? 'opacity-70' : ''
                  }`}
                >
                  <ScrollParallax speed={0.2} className="absolute top-0 left-0 right-0 h-1 rounded-t-fufu-card z-10">
                    <motion.div
                      className="absolute inset-0 rounded-t-fufu-card"
                      style={{
                        background: 'linear-gradient(90deg, #00e5ff, #39c5bb, #ffb6c1)',
                      }}
                      whileHover={{ scaleX: 1.05, x: -2 }}
                      transition={{ type: 'spring', stiffness: 200, damping: 20 }}
                    />
                  </ScrollParallax>

                  <div className="flex items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="fufu-tag bg-fufu-teal/10 text-fufu-teal-deep font-cute">
                          {a.source_name || '🎵 未分类'}
                        </span>
                        {(a.tags ?? []).slice(0, 2).map((tag) => (
                          <span key={tag} className="fufu-tag bg-fufu-lavender/20 text-fufu-text-light font-body">
                            {tag}
                          </span>
                        ))}
                      </div>
                      <h3 className={`font-cute text-lg text-fufu-text group-hover:text-fufu-pink transition-colors line-clamp-2 ${a.is_read ? '' : 'font-bold'}`}>
                        {!a.is_read && <span className="text-fufu-teal mr-1.5 text-xs">💿</span>}
                        {a.title}
                      </h3>
                      {a.summary && (() => {
                        const s = a.summary.replace(/<[^>]+>/g, '').replace(/&[^;]+;/g, ' ').replace(/\s+/g, ' ').trim();
                        return s ? <p className="font-body text-sm text-fufu-text-light mt-2 line-clamp-2">{s}</p> : null;
                      })()}
                      <div className="flex items-center gap-4 mt-3 text-xs text-fufu-text-muted font-body">
                        {a.author && <span>{a.author}</span>}
                        <span>{a.published_at ? new Date(a.published_at).toLocaleDateString('zh-CN') : ''}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 mt-4 pt-3 border-t border-fufu-teal-soft/20 relative">
                    <button
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); triggerHeart(e, a.id, a.is_favorite); }}
                      className={`p-2 rounded-full transition-all duration-200 ${
                        a.is_favorite
                          ? 'text-fufu-teal bg-fufu-teal-soft/30'
                          : 'text-fufu-text-muted hover:text-fufu-teal hover:bg-fufu-teal-soft/20'
                      }`}
                    >
                      <Star size={20} weight={a.is_favorite ? 'fill' : 'regular'} />
                    </button>
                    <button
                      onClick={(e) => {
                        e.preventDefault(); e.stopPropagation();
                        toggleLater.mutate({ id: a.id, value: !a.is_later });
                        if (!a.is_later) checkAchievement.mutate({ key: 'later_10' });
                      }}
                      className={`p-2 rounded-full transition-all duration-200 ${
                        a.is_later
                          ? 'text-fufu-mint bg-fufu-mint-light/30'
                          : 'text-fufu-text-muted hover:text-fufu-lavender hover:bg-fufu-lavender/10'
                      }`}
                    >
                      <BookmarkSimple size={20} weight={a.is_later ? 'fill' : 'regular'} />
                    </button>
                    {a.is_read && (
                      <span className="ml-auto fufu-tag bg-fufu-mint-light/50 text-fufu-mint font-cute text-xs">
                        <Eye size={14} className="mr-1" /> 已读
                      </span>
                    )}
                  </div>
                  <RippleOverlay ripples={ripples} />
                </Link>
              </TiltCard>
            </motion.div>
          )}
        />
      )}

      {/* Pagination */}
      {total > 0 && (
        <div className="flex items-center justify-center gap-4 mt-8">
          <button
            className="fufu-btn bg-white text-fufu-text-light disabled:opacity-30 rounded-fufu-btn shadow-fufu"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            ← 上一页
          </button>
          <span className="font-cute text-sm text-fufu-text-light">
            {page} / {Math.ceil(total / pageSize)}
          </span>
          <button
            className="fufu-btn bg-white text-fufu-text-light disabled:opacity-30 rounded-fufu-btn shadow-fufu"
            disabled={page >= Math.ceil(total / pageSize)}
            onClick={() => setPage((p) => p + 1)}
          >
            下一页 →
          </button>
        </div>
      )}
    </div>
  );
}
