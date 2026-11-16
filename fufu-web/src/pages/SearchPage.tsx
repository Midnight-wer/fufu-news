import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Globe,
  Newspaper,
  Heart,
  BookmarkSimple,
  FadersHorizontal,
  ArrowDown,
  CaretUp,
} from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { searchArticles, searchWeb, type WebSearchEnvelope } from '../api/search';
import { useCheckAchievement } from '../hooks/useAchievements';
import { useToggleFavorite, useToggleLater } from '../hooks/useArticles';
import { ClickRippleWrapper } from '../components/effects/ClickRipple';
import TiltCard from '../components/effects/TiltCard';
import HotSearchTerms from '../components/search/HotSearchTerms';
import SearchAutocomplete from '../components/search/SearchAutocomplete';

// ===== Types =====

interface LocalArticle {
  id: number;
  source_id: number;
  title: string;
  summary?: string;
  source_name?: string;
  published_at?: string;
}

interface WebResult {
  title: string;
  url: string;
  snippet: string;
  source: string;
  published_at?: string | null;
  local_id?: number;
}

// 全网搜索响应信封统一由 api/search 的 WebSearchEnvelope 提供

// ===== Constants =====

const HISTORY_KEY = 'fufu-search-history';

type TimeFilter = 'all' | '24h' | 'week' | 'month';
type SourceFilter = 'all' | '科技' | '游戏' | '动漫' | '设计' | '综合';
type SortOrder = 'relevance' | 'latest' | 'hottest';

const TIME_FILTERS: { key: TimeFilter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: '24h', label: '24小时内' },
  { key: 'week', label: '本周' },
  { key: 'month', label: '本月' },
];

const SOURCE_FILTERS: { key: SourceFilter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: '科技', label: '科技' },
  { key: '游戏', label: '游戏' },
  { key: '动漫', label: '动漫' },
  { key: '设计', label: '设计' },
  { key: '综合', label: '综合' },
];

const SORT_OPTIONS: { key: SortOrder; label: string; icon: React.ReactNode }[] = [
  { key: 'relevance', label: '相关性', icon: <FadersHorizontal size={13} /> },
  { key: 'latest', label: '最新', icon: <ArrowDown size={13} /> },
  { key: 'hottest', label: '最热', icon: <CaretUp size={13} /> },
];

// ===== Helpers =====

function getHistory(): string[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveHistory(term: string) {
  const h = getHistory().filter((t) => t !== term);
  h.unshift(term);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(h.slice(0, 10)));
}

function clearHistory() {
  localStorage.removeItem(HISTORY_KEY);
}

function fmtDate(s?: string | null): string {
  if (!s) return '';
  try {
    const d = new Date(s);
    if (isNaN(d.getTime())) return s;
    const diff = Date.now() - d.getTime();
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    const weeks = Math.floor(days / 7);
    const months = Math.floor(days / 30);

    if (seconds < 60) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    if (days === 1) return '昨天';
    if (days < 7) return `${days}天前`;
    if (weeks < 4) return `${weeks}周前`;
    if (months < 12) return `${months}个月前`;
    return d.toLocaleDateString('zh-CN');
  } catch {
    return s;
  }
}

/** Highlight matching text by wrapping matches in a <mark> tag */
function highlightMatch(text: string, query: string): React.ReactNode {
  if (!query.trim() || !text) return text;
  try {
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escaped})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark
          key={i}
          className="search-highlight bg-fufu-teal/20 text-fufu-teal-deep rounded px-0.5 font-medium"
        >
          {part}
        </mark>
      ) : (
        part
      ),
    );
  } catch {
    // Fallback: simple includes-based highlighting
    if (!text.toLowerCase().includes(query.toLowerCase())) return text;
    const idx = text.toLowerCase().indexOf(query.toLowerCase());
    if (idx < 0) return text;
    const before = text.slice(0, idx);
    const match = text.slice(idx, idx + query.length);
    const after = text.slice(idx + query.length);
    return (
      <>
        {before}
        <mark className="search-highlight bg-fufu-teal/20 text-fufu-teal-deep rounded px-0.5 font-medium">
          {match}
        </mark>
        {after}
      </>
    );
  }
}

// ===== Filtering Helpers =====

function applyTimeFilter<T extends { published_at?: string | null }>(
  items: T[],
  filter: TimeFilter,
): T[] {
  if (filter === 'all') return items;
  const now = Date.now();
  const cutoff =
    filter === '24h'
      ? now - 24 * 3600000
      : filter === 'week'
        ? now - 7 * 24 * 3600000
        : now - 30 * 24 * 3600000;

  return items.filter((item) => {
    if (!item.published_at) return true; // keep items without date
    const t = new Date(item.published_at).getTime();
    return !isNaN(t) && t >= cutoff;
  });
}

/**
 * 本地结果的「热度」打分。
 * 后端搜索结果目前不带热度字段，这里用可得的信号做一个稳定的近似排序：
 * 收藏/稍后读权重最高，其次是浏览与评论数（若存在），最后用时间新鲜度兜底。
 */
function hotnessOf(item: any): number {
  let score = 0;
  if (item?.is_favorite) score += 30;
  if (item?.is_later) score += 20;
  score += Number(item?.view_count || 0) * 3;
  score += Number(item?.comment_count || 0) * 5;
  score += Number(item?.collect_count || 0) * 2;
  score += Number(item?.hot_score || 0);
  const t = item?.published_at || item?.fetched_at;
  if (t) {
    const hours = (Date.now() - new Date(t).getTime()) / 36e5;
    if (Number.isFinite(hours) && hours >= 0) {
      // 越新分越高，最多贡献 10 分（24h 内约 10 分，逐日衰减）
      score += Math.max(0, 10 - hours / 24);
    }
  }
  return score;
}

function applySort<T extends { published_at?: string | null }>(
  items: T[],
  sort: SortOrder,
  _query: string,
): T[] {
  const sorted = [...items];
  if (sort === 'latest') {
    sorted.sort((a, b) => {
      const ta = a.published_at ? new Date(a.published_at).getTime() : 0;
      const tb = b.published_at ? new Date(b.published_at).getTime() : 0;
      return tb - ta;
    });
  } else if (sort === 'relevance') {
    // Keep original order from search engine (already relevance-sorted)
    // For local results, sort by title match quality as a heuristic
    if (_query.trim()) {
      sorted.sort((a, b) => {
        const aTitle = ((a as any).title || '').toLowerCase();
        const bTitle = ((b as any).title || '').toLowerCase();
        const q = _query.toLowerCase();
        const aExact = aTitle === q ? 2 : aTitle.startsWith(q) ? 1 : aTitle.includes(q) ? 0 : -1;
        const bExact = bTitle === q ? 2 : bTitle.startsWith(q) ? 1 : bTitle.includes(q) ? 0 : -1;
        return bExact - aExact;
      });
    }
  } else if (sort === 'hottest') {
    // 修复：原先这里根本没有 hottest 分支（注释说"用 fetched_at"但没实现），
    // 点「最热」按钮结果顺序纹丝不动，等于一个假按钮。
    // 全网结果由服务端返回、缺少热度字段，保持原序；本地结果按热度近似值排序。
    const looksLocal = sorted.some(
      (i: any) => 'is_favorite' in i || 'is_later' in i || 'view_count' in i,
    );
    if (looksLocal) {
      sorted.sort((a, b) => hotnessOf(b) - hotnessOf(a));
    }
  }
  return sorted;
}

// ===== Component =====

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState<'local' | 'web'>('local');
  const [history, setHistory] = useState<string[]>(getHistory());
  const [showFilters, setShowFilters] = useState(false);
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('all');
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all');
  const [sortOrder, setSortOrder] = useState<SortOrder>('relevance');
  const [hoveredItemId, setHoveredItemId] = useState<string | null>(null);

  const checkAchievement = useCheckAchievement();
  const toggleFavorite = useToggleFavorite();
  const toggleLater = useToggleLater();
  const searchedRef = useRef(false);

  // Reset filters when tab changes
  const handleTabChange = useCallback((t: 'local' | 'web') => {
    setTab(t);
    setTimeFilter('all');
    setSourceFilter('all');
    setSortOrder('relevance');
  }, []);

  // Handle search from autocomplete
  const handleSearchWithTerm = useCallback((term: string) => {
    if (!term.trim()) return;
    setQuery(term);
    setSearch(term);
    saveHistory(term);
    setHistory(getHistory());
  }, []);

  // Handle query change from autocomplete
  const handleQueryChange = useCallback((q: string) => {
    setQuery(q);
  }, []);

  // Local search
  const localQuery = useQuery<LocalArticle[]>({
    queryKey: ['search', search],
    queryFn: async () => {
      if (!search.trim()) return [];
      return searchArticles<LocalArticle>(search);
    },
    enabled: search.length > 0 && tab === 'local',
    placeholderData: (prev) => prev ?? [],
  });

  // Web search
  const webQuery = useQuery<WebSearchEnvelope<WebResult>>({
    queryKey: ['web-search', search],
    queryFn: async ({ signal }) => {
      if (!search.trim()) return { code: 200, data: [], total: 0, message: '' };
      try {
        const data = await searchWeb<WebResult>(search, 20, signal);
        if (data?.data?.length > 0) return data;
      } catch {
        /* timeout or failure -> backend already degraded to local */
      }
      return { code: 200, data: [], total: 0, message: 'timeout' };
    },
    enabled: search.length > 0 && tab === 'web',
    staleTime: 10_000,
  });

  // Achievement check
  useEffect(() => {
    if (
      Array.isArray(webQuery.data?.data) &&
      (webQuery.data?.data ?? []).length > 0 &&
      !searchedRef.current
    ) {
      searchedRef.current = true;
      checkAchievement.mutate({ key: 'first_search' });
    }
  }, [webQuery.data]);

  // ===== Data processing =====

  const localData = (localQuery.data ?? []) as LocalArticle[];
  const webData = (webQuery.data?.data ?? []) as WebResult[];

  // Apply filters to local data (web data is pre-filtered by the server)
  const filteredLocalData = useMemo(() => {
    let data = localData;
    data = applyTimeFilter(data, timeFilter);
    // Source filter for local: match source_name
    if (sourceFilter !== 'all') {
      data = data.filter((item) => {
        const sn = (item.source_name || '').toLowerCase();
        const sf = sourceFilter.toLowerCase();
        return sn.includes(sf);
      });
    }
    data = applySort(data as any[], sortOrder, search) as LocalArticle[];
    return data;
  }, [localData, timeFilter, sourceFilter, sortOrder, search]);

  const dataArr = tab === 'local' ? filteredLocalData : webData;
  const isLoading =
    tab === 'local'
      ? localQuery.isLoading || localQuery.isPlaceholderData
      : webQuery.isLoading || webQuery.isFetching;
  const isError = tab === 'local' ? localQuery.isError : webQuery.isError;

  // ===== Quick actions =====

  const handleToggleFav = useCallback(
    (e: React.MouseEvent, itemId: number) => {
      e.preventDefault();
      e.stopPropagation();
      toggleFavorite.mutate({ id: itemId, value: true });
    },
    [toggleFavorite],
  );

  const handleToggleLater = useCallback(
    (e: React.MouseEvent, itemId: number) => {
      e.preventDefault();
      e.stopPropagation();
      toggleLater.mutate({ id: itemId, value: true });
    },
    [toggleLater],
  );

  // ===== Render helpers =====

  const renderResultCard = (item: any, index: number) => {
    const itemKey = item.url || item.id || index;
    const isHovered = hoveredItemId === String(itemKey);

    return (
      <motion.div
        key={itemKey}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: Math.min(index * 0.03, 0.3), duration: 0.3 }}
      >
        <TiltCard maxTilt={2}>
          <div
            className="relative group"
            onMouseEnter={() => setHoveredItemId(String(itemKey))}
            onMouseLeave={() => setHoveredItemId(null)}
          >
            <ClickRippleWrapper>
              {tab === 'local' ? (
                <Link
                  to={`/articles/${item.id}`}
                  className="fufu-card p-4 sm:p-6 block rounded-fufu-card news-card-hover"
                >
                  {/* Meta row */}
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className="fufu-tag bg-fufu-teal/10 text-fufu-teal-deep font-cute text-xs">
                      {item.source_name || '🌸 未分类'}
                    </span>
                    {item.published_at && (
                      <span className="font-body text-xs text-fufu-text-muted">
                        {fmtDate(item.published_at)}
                      </span>
                    )}
                  </div>
                  {/* Title with highlight */}
                  <h3 className="font-cute text-base sm:text-lg text-fufu-text group-hover:text-fufu-teal transition-colors leading-snug line-clamp-2">
                    {highlightMatch(item.title, search)}
                  </h3>
                  {/* Summary with highlight */}
                  {item.summary && (
                    <p className="font-body text-xs sm:text-sm text-fufu-text-light mt-2 line-clamp-2">
                      {highlightMatch(item.summary, search)}
                    </p>
                  )}
                </Link>
              ) : item.local_id ? (
                <Link
                  to={`/articles/${item.local_id}`}
                  className="fufu-card p-4 sm:p-6 block rounded-fufu-card news-card-hover"
                >
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className="fufu-tag bg-fufu-teal/10 text-fufu-teal-deep font-cute text-xs inline-flex items-center gap-1">
                      📰 本地
                    </span>
                    {item.source && (
                      <span className="font-body text-xs text-fufu-text-muted bg-fufu-cream px-2 py-0.5 rounded-fufu-tag">
                        {item.source}
                      </span>
                    )}
                    {item.published_at && (
                      <span className="font-body text-xs text-fufu-text-muted ml-auto">
                        {fmtDate(item.published_at)}
                      </span>
                    )}
                  </div>
                  <h3 className="font-cute text-base sm:text-lg text-fufu-text group-hover:text-fufu-teal transition-colors leading-snug line-clamp-2">
                    {highlightMatch(item.title, search)}
                  </h3>
                  <p className="font-body text-xs sm:text-sm text-fufu-text-light mt-2 line-clamp-2">
                    {highlightMatch(item.snippet, search)}
                  </p>
                </Link>
              ) : (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="fufu-card p-4 sm:p-6 block rounded-fufu-card news-card-hover"
                >
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span
                      className={`fufu-tag font-cute text-xs inline-flex items-center gap-1 ${
                        item.source === 'AI搜索' || item.source === 'AI'
                          ? 'bg-purple-100 text-purple-600'
                          : 'bg-fufu-lavender/20 text-fufu-lavender'
                      }`}
                    >
                      {item.source === 'AI搜索' || item.source === 'AI' ? (
                        '🤖'
                      ) : (
                        <Globe size={12} />
                      )}{' '}
                      {item.source === 'AI搜索' || item.source === 'AI' ? 'AI 搜索' : '全网搜索'}
                    </span>
                    {item.source && item.source !== 'AI搜索' && item.source !== 'AI' && (
                      <span className="font-body text-xs text-fufu-text-muted bg-fufu-cream px-2 py-0.5 rounded-fufu-tag">
                        {item.source}
                      </span>
                    )}
                    {item.published_at && (
                      <span className="font-body text-xs text-fufu-text-muted ml-auto">
                        {fmtDate(item.published_at)}
                      </span>
                    )}
                  </div>
                  <h3 className="font-cute text-base sm:text-lg text-fufu-text group-hover:text-fufu-lavender transition-colors leading-snug">
                    {highlightMatch(item.title, search)}
                  </h3>
                  <p className="font-body text-xs sm:text-sm text-fufu-text-light mt-2 line-clamp-2">
                    {highlightMatch(item.snippet, search)}
                  </p>
                </a>
              )}
            </ClickRippleWrapper>

            {/* Quick action buttons on hover */}
            {tab === 'local' && item.id && (
              <AnimatePresence>
                {isHovered && (
                  <motion.div
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 10 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-3 top-3 flex flex-col gap-1.5 z-10"
                  >
                    <button
                      onClick={(e) => handleToggleFav(e, item.id)}
                      className="w-8 h-8 flex items-center justify-center rounded-full
                                 bg-white/90 backdrop-blur shadow-fufu border border-fufu-pink/20
                                 text-fufu-text-muted hover:text-fufu-pink hover:border-fufu-pink
                                 transition-all duration-150"
                      title="收藏"
                    >
                      <Heart size={16} weight={toggleFavorite.isPending ? 'fill' : 'regular'} />
                    </button>
                    <button
                      onClick={(e) => handleToggleLater(e, item.id)}
                      className="w-8 h-8 flex items-center justify-center rounded-full
                                 bg-white/90 backdrop-blur shadow-fufu border border-fufu-teal/20
                                 text-fufu-text-muted hover:text-fufu-teal-deep hover:border-fufu-teal
                                 transition-all duration-150"
                      title="稍后阅读"
                    >
                      <BookmarkSimple size={16} />
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            )}
          </div>
        </TiltCard>
      </motion.div>
    );
  };

  // ===== Render =====

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h2 className="font-cute text-3xl text-fufu-text">🔎 搜一搜</h2>
        <p className="font-body text-sm text-fufu-text-light mt-1">
          本地搜 + 全网搜，找找你想看的新闻～
        </p>
      </div>

      {/* SearchAutocomplete replaces the raw input */}
      <SearchAutocomplete
        query={query}
        onQueryChange={handleQueryChange}
        onSearch={handleSearchWithTerm}
      />

      {/* Hot Search Terms (show when no active search) */}
      {search.length === 0 && <HotSearchTerms onTermClick={handleSearchWithTerm} />}

      {/* Search History (show when no active search and hot terms not showing) */}
      {search.length === 0 && history.length > 0 && (
        <div className="mb-4 p-4 rounded-fufu-card bg-fufu-pink-soft/20">
          <div className="flex items-center justify-between mb-2">
            <span className="font-cute text-xs text-fufu-text-light flex items-center gap-1">
              🕐 最近搜索
            </span>
            <button
              onClick={() => {
                clearHistory();
                setHistory([]);
              }}
              className="font-body text-xs text-fufu-text-muted hover:text-fufu-pink transition-colors"
            >
              清空
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {history.map((t) => (
              <button
                key={t}
                onClick={() => handleSearchWithTerm(t)}
                className="px-3 py-1.5 rounded-fufu-tag bg-white text-fufu-text-light font-body text-xs
                           hover:bg-fufu-highlight hover:text-fufu-pink transition-all"
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Network status banner */}
      {tab === 'web' && webQuery.data && webQuery.data.ddgs_available === false && (
        <div className="mb-4 px-4 py-2.5 rounded-fufu-card bg-amber-50 border border-amber-200 text-amber-700 font-body text-xs flex items-center gap-2">
          <span>⚠️</span>
          <span>DuckDuckGo 在当前网络不可达，搜索结果来自 AI 和本地文章库</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-4 items-center">
        {(['local', 'web'] as const).map((t) => (
          <button
            key={t}
            onClick={() => handleTabChange(t)}
            className={`fufu-btn text-sm flex items-center gap-2 rounded-fufu-btn transition-all duration-200 touch-target ${
              tab === t
                ? 'bg-gradient-to-r from-fufu-teal to-fufu-teal-deep text-white shadow-sm'
                : 'bg-white text-fufu-text-light shadow-fufu hover:bg-fufu-teal-soft/20'
            }`}
          >
            {t === 'local' ? <Newspaper size={16} /> : <Globe size={16} />}
            {t === 'local' ? '本地文章' : '全网搜索'}
          </button>
        ))}

        {/* Filter toggle */}
        {search.length > 0 && (
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`fufu-btn text-sm flex items-center gap-1.5 rounded-fufu-btn transition-all duration-200 touch-target ${
              showFilters
                ? 'bg-fufu-teal/10 text-fufu-teal-deep border border-fufu-teal/20'
                : 'bg-white text-fufu-text-light shadow-fufu hover:bg-fufu-teal-soft/20'
            }`}
          >
            <FadersHorizontal size={16} />
            筛选
          </button>
        )}
      </div>

      {/* Filter panels */}
      <AnimatePresence>
        {showFilters && search.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden mb-4"
          >
            <div className="p-4 rounded-fufu-card bg-white shadow-fufu border border-fufu-teal/5 space-y-3">
              {/* Time filter */}
              <div>
                <span className="font-cute text-xs text-fufu-text-muted mb-2 block">时间范围</span>
                <div className="filter-scroll md:overflow-visible">
                  <div className="flex gap-1.5">
                    {TIME_FILTERS.map((f) => (
                      <button
                        key={f.key}
                        onClick={() => setTimeFilter(f.key)}
                        className={`flex-shrink-0 px-3 py-1.5 rounded-fufu-tag font-body text-xs transition-all duration-150 touch-target ${
                          timeFilter === f.key
                            ? 'bg-fufu-teal text-white shadow-sm'
                            : 'bg-fufu-cream text-fufu-text-light hover:bg-fufu-highlight'
                        }`}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Source filter */}
              <div>
                <span className="font-cute text-xs text-fufu-text-muted mb-2 block">来源分类</span>
                <div className="filter-scroll md:overflow-visible">
                  <div className="flex gap-1.5">
                    {SOURCE_FILTERS.map((f) => (
                      <button
                        key={f.key}
                        onClick={() => setSourceFilter(f.key)}
                        className={`flex-shrink-0 px-3 py-1.5 rounded-fufu-tag font-body text-xs transition-all duration-150 touch-target ${
                          sourceFilter === f.key
                            ? 'bg-fufu-pink text-white shadow-sm'
                            : 'bg-fufu-pink-soft/30 text-fufu-text-light hover:bg-fufu-pink-soft/50'
                        }`}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Sort order */}
              <div>
                <span className="font-cute text-xs text-fufu-text-muted mb-2 block">排序方式</span>
                <div className="filter-scroll md:overflow-visible">
                  <div className="flex gap-1.5">
                    {SORT_OPTIONS.map((o) => (
                      <button
                        key={o.key}
                        onClick={() => setSortOrder(o.key)}
                        className={`flex-shrink-0 px-3 py-1.5 rounded-fufu-tag font-body text-xs transition-all duration-150 inline-flex items-center gap-1 touch-target ${
                          sortOrder === o.key
                            ? 'bg-fufu-teal-deep text-white shadow-sm'
                            : 'bg-fufu-mint-light/30 text-fufu-text-light hover:bg-fufu-mint-light/50'
                        }`}
                      >
                        {o.icon}
                        {o.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Active filter summary */}
              {(timeFilter !== 'all' || sourceFilter !== 'all' || sortOrder !== 'relevance') && (
                <div className="pt-2 border-t border-fufu-teal/5">
                  <span className="font-body text-xs text-fufu-text-muted">
                    当前筛选：{dataArr.length} 条结果
                    {timeFilter !== 'all' &&
                      ` · ${TIME_FILTERS.find((f) => f.key === timeFilter)?.label}`}
                    {sourceFilter !== 'all' && ` · ${sourceFilter}`}
                    {sortOrder !== 'relevance' &&
                      ` · ${SORT_OPTIONS.find((o) => o.key === sortOrder)?.label}`}
                  </span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ===== Empty/Idle state ===== */}
      {search.length === 0 ? (
        <div className="text-center py-16">
          <motion.p
            className="text-6xl mb-4"
            animate={{ y: [0, -6, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
          >
            🐾
          </motion.p>
          <p className="font-cute text-xl text-fufu-text">输入点什么来搜索吧～</p>
          <p className="font-body text-sm text-fufu-text-light mt-2">
            可以搜本地已抓取的文章，也能搜全网新闻 🎵
          </p>
        </div>
      ) : isError ? (
        /* ===== Error state ===== */
        <div className="text-center py-16">
          <motion.p
            className="text-6xl mb-4"
            animate={{ scale: [1, 1.05, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            😿
          </motion.p>
          <p className="font-cute text-xl text-fufu-text">网络开小差啦～</p>
          <p className="font-body text-sm text-fufu-text-light mt-2">
            {tab === 'web'
              ? '全网搜索暂时连接不上呢…要确保后端已经启动了哦～'
              : '本地搜索出了点小问题，换个关键词试试看？'}
          </p>
          <button className="fufu-btn-primary mt-4" onClick={() => handleSearchWithTerm(search)}>
            重新搜索 🔄
          </button>
        </div>
      ) : isLoading ? (
        /* ===== Loading state ===== */
        <div className="space-y-4">
          <p className="text-center font-cute text-sm text-fufu-text-muted mb-2">
            {tab === 'web' ? '🔍 正在搜索全网...' : '🔍 正在搜索本地文章...'}
          </p>
          {Array.from({ length: 5 }).map((_, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <div className="fufu-card p-4 sm:p-6 rounded-fufu-card">
                <div className="skeleton h-5 w-3/4 rounded mb-3" />
                <div className="skeleton h-4 w-full rounded mb-2" />
                <div className="skeleton h-3 w-1/3 rounded" />
              </div>
            </motion.div>
          ))}
        </div>
      ) : dataArr.length === 0 ? (
        /* ===== No results ===== */
        <div className="text-center py-12">
          <motion.p
            className="text-6xl mb-4"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 15 }}
          >
            {tab === 'web' &&
            (webQuery.data?.message === 'timeout' || webQuery.data?.message === 'local_fallback')
              ? '⏰'
              : '🔍'}
          </motion.p>
          <p className="font-cute text-xl text-fufu-text">
            {tab === 'web' &&
            webQuery.data?.message === 'timeout' &&
            webQuery.data?.source === 'none'
              ? '全网搜索超时，本地也没有匹配结果 😿'
              : tab === 'web' &&
                  (webQuery.data?.message === 'timeout' ||
                    webQuery.data?.message === 'local_fallback')
                ? '全网搜索超时，已自动切换到本地搜索 📰'
                : '没有找到相关结果'}
          </p>

          {/* Enhanced empty state tips */}
          <div className="mt-6 max-w-md mx-auto">
            <div className="bg-fufu-cream rounded-fufu-card p-5 text-left border border-fufu-teal/5">
              <p className="font-cute text-sm text-fufu-text mb-3">💡 试试：</p>
              <ul className="space-y-2 font-body text-sm text-fufu-text-light">
                <li className="flex items-start gap-2">
                  <span className="text-fufu-teal mt-0.5">·</span>
                  <span>检查关键词拼写是否正确</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-fufu-teal mt-0.5">·</span>
                  <span>使用更简短的关键词试试</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-fufu-teal mt-0.5">·</span>
                  <span>尝试其他相关的词汇</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-fufu-teal mt-0.5">·</span>
                  <span>切换到 {tab === 'local' ? '全网搜索' : '本地文章'} 试试</span>
                </li>
              </ul>
            </div>

            {/* Hot terms suggestion in empty state */}
            <div className="mt-4">
              <p className="font-cute text-xs text-fufu-text-muted mb-2">🔥 试试热门搜索：</p>
              <div className="flex flex-wrap justify-center gap-2">
                {['AI', '科技', '游戏', '设计', '前端', '动漫'].map((t) => (
                  <button
                    key={t}
                    onClick={() => handleSearchWithTerm(t)}
                    className="px-3 py-1 rounded-fufu-tag bg-white text-fufu-text-light font-body text-xs
                               border border-fufu-teal/10 hover:bg-fufu-teal hover:text-white
                               hover:shadow-fufu-glow transition-all duration-200"
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {tab === 'web' && (
            <button
              className="fufu-btn bg-white text-fufu-text-light shadow-fufu rounded-fufu-btn mt-4 text-sm"
              onClick={() => handleTabChange('local')}
            >
              试试本地搜索 📰
            </button>
          )}
        </div>
      ) : (
        /* ===== Results ===== */
        <div className="space-y-4">
          {/* Source badge */}
          {tab === 'web' && webQuery.data && dataArr.length > 0 && (
            <div className="text-center space-y-1">
              <p className="font-cute text-xs text-fufu-text-muted">
                {webQuery.data.source === 'local' || webQuery.data.message === 'local'
                  ? '📰 以下来自本地文章库（秒级响应）'
                  : webQuery.data.source === 'web'
                    ? webQuery.data.ddgs_available === false
                      ? '🤖 以下来自 AI 智能搜索'
                      : '🌐 以下来自全网实时搜索'
                    : null}
              </p>
              {webQuery.data.ai_pending && (
                <p className="font-cute text-[10px] text-fufu-pink animate-pulse">
                  🤖 AI 正在后台分析，下次搜索同一关键词将更精准
                </p>
              )}
            </div>
          )}

          {/* Result count */}
          <p className="font-body text-xs text-fufu-text-muted text-center">
            找到 {dataArr.length} 条结果
            {timeFilter !== 'all' && ` · ${TIME_FILTERS.find((f) => f.key === timeFilter)?.label}`}
            {sourceFilter !== 'all' && ` · 来源：${sourceFilter}`}
          </p>

          {/* Result cards */}
          {dataArr.map((item: any, i: number) => renderResultCard(item, i))}
        </div>
      )}
    </div>
  );
}
