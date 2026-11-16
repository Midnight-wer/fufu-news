import { useParams, useNavigate } from 'react-router-dom';
import { createPortal } from 'react-dom';
import {
  Star,
  BookmarkSimple,
  ArrowLeft,
  Share,
  Sparkle,
  Tag,
  CaretDown,
  CaretUp,
  Robot,
} from '@phosphor-icons/react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  useArticle,
  useToggleFavorite,
  useToggleLater,
  useMarkRead,
  useUpdateReadProgress,
} from '../hooks/useArticles';
import { useAISummarize, useAITag, useGenerateDeepSummary } from '../hooks/useAI';
import { useRecordHit } from '../hooks/useRanking';
import { useRecordRead } from '../hooks/useHistory';
import { useEffect, useState, useMemo, useRef, type MouseEvent } from 'react';
import TTSReader from '../components/reader/TTSReader';
import HeartBurst from '../components/effects/HeartBurst';
import { useCompanionStore } from '../stores/companionStore';
import { useCheckAchievement } from '../hooks/useAchievements';
import { useFolders, useAddToFolder } from '../hooks/useFolders';
import { useQuery } from '@tanstack/react-query';
import { fetchPoll, submitPoll, type PollOption, type PollResult } from '../api/articles';
import { fetchSimilarArticles } from '../api/recommendations';
import AggregatedView from '../components/common/AggregatedView';
import CommentSection from '../components/comments/CommentSection';
import ShareButton from '../components/common/ShareButton';
import { setArticleSEO, resetSEO } from '../lib/seo';
import { sanitizeHtml } from '../lib/sanitize';

// ===== Animation variants =====
const fadeInUp = {
  hidden: { opacity: 0, y: 28 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' } },
};

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
};

// ===== Section wrapper =====
function DeepSection({
  icon,
  title,
  children,
  className = '',
  delay = 0,
}: {
  icon: string;
  title: string;
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.section
      variants={fadeInUp}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: '-60px' }}
      transition={{ delay }}
      className={`bg-white/70 backdrop-blur-sm rounded-fufu-card border border-fufu-highlight/30 p-5 md:p-6 shadow-fufu ${className}`}
    >
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xl">{icon}</span>
        <h3 className="font-cute text-fufu-text text-base">{title}</h3>
      </div>
      {children}
    </motion.section>
  );
}

// ===== 立场投票 =====
// 修复：原先这里是纯 localStorage 假数据，换设备即丢失；
// 更严重的是 getPollCounts() 遍历的是**全部文章**的投票记录、没有按 articleId 过滤，
// 所以在第 5 篇投票，第 100 篇也会显示"已有 1 人参与"。
// 现在改为调用真实的后端接口（article_poll 表，一人一票、可改票/撤票）。

// PollOption / PollResult / fetchPoll / submitPoll 已下沉到 api/articles

function ArticlePoll({ articleId }: { articleId: number }) {
  const [myVote, setMyVote] = useState<PollOption | null>(null);
  const [counts, setCounts] = useState({ support: 0, oppose: 0, neutral: 0 });
  const [total, setTotal] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [voting, setVoting] = useState<PollOption | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoaded(false);
    fetchPoll(articleId)
      .then((r) => {
        if (cancelled) return;
        setCounts({ support: r.support, oppose: r.oppose, neutral: r.neutral });
        setTotal(r.total);
        setMyVote(r.my_vote);
      })
      .catch(() => {
        /* 拉取失败时保持空票态，用户可以照常投票 */
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [articleId]);

  const handleVote = async (option: PollOption) => {
    if (voting) return;
    setVoting(option);
    // 再次点击当前选项 = 撤票
    const next = myVote === option ? null : option;
    try {
      const r = await submitPoll(articleId, next);
      setCounts({ support: r.support, oppose: r.oppose, neutral: r.neutral });
      setTotal(r.total);
      setMyVote(r.my_vote);
    } catch {
      /* 投票失败不打断阅读，静默返回 */
    } finally {
      setVoting(null);
    }
  };

  const displayTotal = total || 1;

  const options = [
    {
      key: 'support' as const,
      label: '支持',
      icon: '👍',
      color: 'rgb(var(--fufu-teal-deep))',
      bg: 'bg-fufu-soft-green/20 hover:bg-fufu-soft-green/40',
    },
    {
      key: 'oppose' as const,
      label: '反对',
      icon: '👎',
      color: '#FF9E9E',
      bg: 'bg-fufu-error-light/20 hover:bg-fufu-error-light/40',
    },
    {
      key: 'neutral' as const,
      label: '中立',
      icon: '🤔',
      color: '#A0B8C0',
      bg: 'bg-fufu-soft-purple/20 hover:bg-fufu-soft-purple/40',
    },
  ];

  return (
    <DeepSection icon="🤔" title="你怎么看？" delay={0.25}>
      <div className="space-y-3">
        {/* 投票按钮：始终可见，点击当前选项可撤票 */}
        <div className="flex flex-wrap gap-3">
          {options.map((opt) => {
            const isMine = myVote === opt.key;
            return (
              <button
                key={opt.key}
                onClick={() => handleVote(opt.key)}
                disabled={voting !== null}
                aria-pressed={isMine}
                className={`flex items-center gap-2 px-5 py-3 rounded-fufu-btn font-cute text-sm
                  transition-all border-2 hover:shadow-fufu-hover touch-target
                  disabled:opacity-60 disabled:cursor-not-allowed
                  ${isMine ? 'border-fufu-pink bg-fufu-pink-soft/40' : 'border-transparent ' + opt.bg}
                  text-fufu-text`}
                title={isMine ? '再点一次可撤销' : `投「${opt.label}」一票`}
              >
                <span className="text-lg">{opt.icon}</span>
                <span>{opt.label}</span>
                {isMine && <span className="text-xs text-fufu-pink">✓</span>}
              </button>
            );
          })}
        </div>

        {/* 结果条：有人投票时展示 */}
        {total > 0 && (
          <div className="space-y-2.5 pt-1">
            {options.map((opt) => {
              const pct = Math.round((counts[opt.key] / displayTotal) * 100);
              return (
                <div key={opt.key} className="space-y-1">
                  <div className="flex items-center justify-between text-sm font-body">
                    <span className="flex items-center gap-1.5">
                      <span>{opt.icon}</span>
                      <span className="text-fufu-text">{opt.label}</span>
                      {myVote === opt.key && (
                        <span className="text-xs text-fufu-pink font-cute">我的选择</span>
                      )}
                    </span>
                    <span className="text-fufu-text-muted text-xs">
                      {counts[opt.key]} 票 ({pct}%)
                    </span>
                  </div>
                  <div className="h-2.5 bg-fufu-cream rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.max(pct, 3)}%` }}
                      transition={{ duration: 0.8, ease: 'easeOut' }}
                      className="h-full rounded-full"
                      style={{ backgroundColor: opt.color }}
                    />
                  </div>
                </div>
              );
            })}
            <p className="text-xs text-fufu-text-muted text-center mt-2">已有 {total} 人参与</p>
          </div>
        )}

        {loaded && total === 0 && (
          <p className="text-xs text-fufu-text-muted">还没有人投票，你来当第一个吧～</p>
        )}
      </div>
    </DeepSection>
  );
}

// ===== Reason badge helper =====
function getReasonBadge(reason: string): { icon: string; color: string; bg: string } {
  if (reason.includes('喜欢') || reason.includes('阅读')) {
    return { icon: '💝', color: 'text-fufu-pink', bg: 'bg-fufu-pink-soft/30' };
  }
  if (reason.includes('热门') || reason.includes('趋势')) {
    return { icon: '🔥', color: 'text-orange-500', bg: 'bg-orange-50' };
  }
  if (reason.includes('标签') || reason.includes('相似')) {
    return { icon: '🏷️', color: 'text-fufu-teal-deep', bg: 'bg-fufu-teal-soft/20' };
  }
  if (reason.includes('常读') || reason.includes('来源') || reason.includes('同源')) {
    return { icon: '📰', color: 'text-fufu-lavender', bg: 'bg-fufu-lavender/20' };
  }
  return { icon: '✨', color: 'text-fufu-text-light', bg: 'bg-fufu-highlight/60' };
}

// ===== Related articles =====
function RelatedArticles({
  articleId,
  sourceId,
  tags,
}: {
  articleId: number;
  sourceId: number;
  tags: string[];
}) {
  const navigate = useNavigate();

  const { data, isLoading } = useQuery({
    queryKey: ['recommendations', 'related', articleId],
    queryFn: async () => {
      return fetchSimilarArticles(articleId, 5);
    },
    enabled: !!articleId,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const articles = useMemo(() => {
    const items = data?.items ?? [];
    return items.filter((a) => a.article_id !== articleId).slice(0, 5);
  }, [data, articleId]);

  // Show loading skeleton
  if (isLoading) {
    return (
      <DeepSection icon="📚" title="相关推荐" delay={0.3}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="p-3 rounded-fufu bg-fufu-cream/40 animate-pulse">
              <div className="skeleton h-4 w-full rounded mb-1.5" />
              <div className="skeleton h-4 w-3/4 rounded mb-2" />
              <div className="skeleton h-3 w-16 rounded" />
            </div>
          ))}
        </div>
      </DeepSection>
    );
  }

  if (!articles.length) return null;

  return (
    <DeepSection icon="📚" title="相关推荐" delay={0.3}>
      <p className="font-body text-xs text-fufu-text-muted mb-3">基于标签相似度和热度为你推荐</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {articles.map((a: any) => {
          const reasonMeta = getReasonBadge(a.reason || '相关内容');
          return (
            <button
              key={a.article_id}
              onClick={() => navigate(`/articles/${a.article_id}`)}
              className="text-left p-3 rounded-fufu bg-fufu-cream/60 hover:bg-fufu-highlight/40 transition-colors group flex flex-col"
            >
              <p className="font-body text-sm text-fufu-text leading-snug line-clamp-2 group-hover:text-fufu-teal-deep transition-colors flex-1">
                {a.title}
              </p>
              <div className="flex items-center gap-2 mt-1.5 text-xs text-fufu-text-muted">
                {a.source_name && <span className="truncate max-w-[100px]">{a.source_name}</span>}
                {a.published_at && (
                  <span>{new Date(a.published_at).toLocaleDateString('zh-CN')}</span>
                )}
              </div>
              {/* Recommendation reason badge */}
              {a.reason && (
                <span
                  className={`inline-flex items-center gap-1 mt-2 px-2 py-0.5 rounded-full font-cute text-[10px] ${reasonMeta.bg} ${reasonMeta.color}`}
                >
                  <span>{reasonMeta.icon}</span>
                  {a.reason}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </DeepSection>
  );
}

// ===== Main page =====
export default function ArticlePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const articleId = Number(id);
  const { data: article, isLoading } = useArticle(articleId);
  const toggleFav = useToggleFavorite();
  const toggleLater = useToggleLater();
  const markRead = useMarkRead();
  const aiSummarize = useAISummarize();
  const aiTag = useAITag();
  const generateDeep = useGenerateDeepSummary();
  const recordHit = useRecordHit();
  const recordRead = useRecordRead();
  const companion = useCompanionStore();
  const checkAchievement = useCheckAchievement();
  const [heartBurst, setHeartBurst] = useState<{ active: boolean; x: number; y: number }>({
    active: false,
    x: 0,
    y: 0,
  });
  const [bgExpanded, setBgExpanded] = useState(false);

  // XSS 防护：正文来自第三方 RSS 源，属完全不可信输入。
  // 原先直接 dangerouslySetInnerHTML 渲染，恶意订阅源可注入脚本（存储型 XSS）。
  // 这里用白名单策略清洗后再渲染。
  const safeContent = useMemo(() => sanitizeHtml(article?.content ?? ''), [article?.content]);

  // 文件夹选择器状态
  const { data: folders = [] } = useFolders();
  const addToFolder = useAddToFolder();
  const [showFolderPicker, setShowFolderPicker] = useState(false);
  const folderPickerRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭文件夹选择器
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (folderPickerRef.current && !folderPickerRef.current.contains(e.target as Node)) {
        setShowFolderPicker(false);
      }
    }
    document.addEventListener('mousedown', handleClick as any);
    return () => document.removeEventListener('mousedown', handleClick as any);
  }, []);

  const deepSummary = article?.deep_summary;
  const hasDeep =
    deepSummary &&
    !deepSummary._parse_error &&
    (deepSummary.one_liner || (deepSummary.core_points && deepSummary.core_points.length > 0));

  const handleFavorite = (e: MouseEvent) => {
    if (!article) return;
    if (!article.is_favorite) {
      setHeartBurst({ active: true, x: e.clientX, y: e.clientY });
      setTimeout(() => setHeartBurst((s) => ({ ...s, active: false })), 800);
      companion.setMood('happy');
      companion.showMessage('收藏成功！fufu 也喜欢这篇呢～🌸');
      // 收藏后显示文件夹选择器
      setShowFolderPicker(true);
    }
    toggleFav.mutate({ id: article.id, value: !article.is_favorite });
    if (!article.is_favorite) {
      checkAchievement.mutate({ key: 'fav_10' });
      checkAchievement.mutate({ key: 'fav_50' });
    }
  };

  const handleAddToFolder = (folderId: number) => {
    if (!article) return;
    addToFolder.mutate(
      { folderId, articleId: article.id },
      {
        onSuccess: () => {
          setShowFolderPicker(false);
          companion.setMood('happy');
          companion.showMessage('已添加到文件夹啦～📁');
        },
      },
    );
  };

  const handleGenerateDeep = () => {
    if (!article) return;
    companion.setMood('excited');
    companion.showMessage('正在深度解读这篇文章，请稍等哦～✨');
    generateDeep.mutate(article.id);
  };

  // Track reading duration: start timer on mount, record on unmount
  const readStartRef = useRef<number>(0);

  useEffect(() => {
    if (article) {
      // Record hit and mark as read
      recordHit.mutate(article.id);
      recordRead.mutate({ articleId: article.id });
      if (!article.is_read) {
        markRead.mutate(article.id);
        checkAchievement.mutate({ key: 'read_10' });
        checkAchievement.mutate({ key: 'read_50' });
        checkAchievement.mutate({ key: 'read_100' });
      }
      // Start reading timer
      readStartRef.current = Date.now();
    }

    return () => {
      // On unmount, record reading duration
      if (article && readStartRef.current > 0) {
        const elapsed = Math.round((Date.now() - readStartRef.current) / 1000);
        if (elapsed > 0) {
          recordRead.mutate({ articleId: article.id, duration: elapsed });
        }
      }
    };
  }, [article?.id]);

  // ===== SEO 元标签（社交分享预览） =====
  useEffect(() => {
    if (article) {
      setArticleSEO({
        title: article.title,
        description: article.summary || '',
        image: article.image_url || '',
        url: window.location.href,
      });
    }
    return () => {
      resetSEO();
    };
  }, [article?.id, article?.title, article?.summary, article?.image_url]);

  // ===== 阅读进度条 =====
  const [readProgress, setReadProgress] = useState(0);
  const updateReadProgress = useUpdateReadProgress();
  // 已上报过的进度档位（每 25% 上报一次），避免滚动时疯狂 PATCH
  const reportedProgressRef = useRef<number>(0);

  useEffect(() => {
    const handleScroll = () => {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (docHeight <= 0) {
        setReadProgress(0);
        return;
      }
      const progress = Math.min(100, Math.round((scrollTop / docHeight) * 100));
      setReadProgress(progress);

      // 落库：后端 read_progress 字段一直存在且 PATCH 支持，
      // 但前端从没调用过，刷新后进度永远归零。这里按 25% 档位防抖上报。
      if (articleId && Number.isFinite(articleId)) {
        const milestone = Math.floor(progress / 25) * 25;
        if (milestone > reportedProgressRef.current) {
          reportedProgressRef.current = milestone;
          updateReadProgress.mutate({ id: articleId, progress: progress / 100 });
        }
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll(); // initial

    return () => window.removeEventListener('scroll', handleScroll);
  }, [articleId, updateReadProgress]);

  // 切换文章时重置上报档位
  useEffect(() => {
    reportedProgressRef.current = 0;
  }, [articleId]);

  // ===== Loading skeleton =====
  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="skeleton h-8 w-2/3 rounded mb-4" />
        <div className="skeleton h-4 w-32 rounded mb-8" />
        <div className="space-y-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="skeleton h-4 w-full rounded" />
          ))}
        </div>
      </div>
    );
  }

  // ===== Not found =====
  if (!article) {
    return (
      <div className="text-center py-20">
        <p className="text-6xl mb-4 animate-float">🔍</p>
        <p className="font-cute text-xl text-fufu-text">找不到这篇文章呢...</p>
        <button className="fufu-btn-primary mt-4" onClick={() => navigate('/articles')}>
          回到首页
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto pb-16 md:pb-16">
      <HeartBurst active={heartBurst.active} x={heartBurst.x} y={heartBurst.y} count={14} />

      {/* ===== 阅读进度条 ===== */}
      <div className="reading-progress-bar" style={{ width: `${readProgress}%` }} />

      {/* ===== 1. Back button ===== */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 font-cute text-fufu-text-light hover:text-fufu-pink transition-colors mb-6 touch-target"
      >
        <ArrowLeft size={20} /> 返回
      </button>

      {/* ===== 2. Title + source + time ===== */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="mb-6"
      >
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <span className="fufu-tag bg-fufu-pink/10 text-fufu-pink font-cute">
            {article.source_name || '🌸 未分类'}
          </span>
          {article.tags?.slice(0, 5).map((tag) => (
            <span key={tag} className="fufu-tag bg-fufu-lavender/20 text-fufu-text-light font-body">
              {tag}
            </span>
          ))}
        </div>

        <h1 className="font-cute text-2xl md:text-3xl text-fufu-text leading-relaxed line-clamp-3 break-words">
          {article.title}
        </h1>

        <div className="flex items-center gap-4 mt-3 text-sm text-fufu-text-muted font-body">
          {article.author && <span>✍️ {article.author}</span>}
          {article.published_at && (
            <span>📅 {new Date(article.published_at).toLocaleDateString('zh-CN')}</span>
          )}
        </div>
      </motion.div>

      {/* ===== 3. Action bar ===== */}
      {/* 桌面端：内联操作栏 */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="hidden md:flex flex-wrap items-center gap-2 mb-6 pb-5 border-b border-fufu-pink-soft/20"
      >
        <div className="relative inline-flex" ref={folderPickerRef}>
          <button
            onClick={handleFavorite}
            className={`flex items-center gap-2 px-4 py-2 rounded-fufu-btn font-cute text-sm transition-all ${
              article.is_favorite
                ? 'bg-fufu-pink-soft/30 text-fufu-pink'
                : 'bg-fufu-cream text-fufu-text-light hover:text-fufu-pink'
            }`}
          >
            <Star size={18} weight={article.is_favorite ? 'fill' : 'regular'} />
            {article.is_favorite ? '已收藏' : '收藏'}
          </button>

          {/* 文件夹选择器下拉 */}
          <AnimatePresence>
            {showFolderPicker && article.is_favorite && folders.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: -4, scale: 0.95 }}
                animate={{ opacity: 1, y: 4, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className="absolute top-full left-0 mt-1 bg-white rounded-fufu-modal shadow-fufu-float border border-fufu-highlight/30 p-1.5 min-w-[180px] z-30"
              >
                <p className="px-3 py-1.5 text-xs text-fufu-text-muted font-body">
                  📁 添加到文件夹
                </p>
                {folders.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => handleAddToFolder(f.id)}
                    disabled={addToFolder.isPending}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-fufu text-sm font-body text-fufu-text hover:bg-fufu-cream transition-colors text-left disabled:opacity-40"
                  >
                    <span>{f.icon}</span>
                    <span>{f.name}</span>
                    <span className="text-fufu-text-muted text-xs ml-auto">{f.article_count}</span>
                  </button>
                ))}
                <div className="my-1 border-t border-fufu-highlight/20" />
                <button
                  onClick={() => setShowFolderPicker(false)}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-fufu text-sm font-body text-fufu-text-muted hover:bg-fufu-cream transition-colors"
                >
                  暂不分类
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <button
          onClick={() => toggleLater.mutate({ id: article.id, value: !article.is_later })}
          className={`flex items-center gap-2 px-4 py-2 rounded-fufu-btn font-cute text-sm transition-all ${
            article.is_later
              ? 'bg-fufu-mint-light/40 text-fufu-mint'
              : 'bg-fufu-cream text-fufu-text-light hover:text-fufu-lavender'
          }`}
        >
          <BookmarkSimple size={18} weight={article.is_later ? 'fill' : 'regular'} />
          {article.is_later ? '待阅读' : '稍后读'}
        </button>

        {/* TTS inline */}
        {article.content && (
          <div className="inline-flex">
            <TTSReader content={article.content} title={article.title} />
          </div>
        )}

        {/* 分享按钮 */}
        <div className="inline-flex">
          <ShareButton
            title={article.title}
            url={window.location.href}
            description={article.summary || ''}
            imageUrl={article.image_url || ''}
          />
        </div>

        <div className="md:ml-auto flex items-center gap-1 mt-2 md:mt-0">
          <button
            onClick={() => aiSummarize.mutate(article.id)}
            disabled={aiSummarize.isPending}
            className="flex items-center gap-1.5 px-3 py-2 rounded-fufu-btn font-cute text-xs bg-fufu-lavender/10 text-fufu-text-light hover:text-fufu-lavender hover:bg-fufu-lavender/20 transition-all"
            title="AI 生成摘要"
          >
            <Sparkle size={16} className={aiSummarize.isPending ? 'animate-spin' : ''} />
            {!article.summary ? '✨ 生成摘要' : '重新摘要'}
          </button>
          <button
            onClick={() => aiTag.mutate(article.id)}
            disabled={aiTag.isPending}
            className="flex items-center gap-1.5 px-3 py-2 rounded-fufu-btn font-cute text-xs bg-fufu-pink-soft/20 text-fufu-text-light hover:text-fufu-pink hover:bg-fufu-pink-soft/40 transition-all"
            title="AI 生成标签"
          >
            <Tag size={16} className={aiTag.isPending ? 'animate-spin' : ''} />
            {article.tags?.length ? '重新标签' : '🏷️ 生成标签'}
          </button>
        </div>
      </motion.div>

      {/* 移动端：粘性底部操作栏。
          必须 portal 到 body：framer-motion 会在 motion 祖先上临时写入
          will-change: transform，而 will-change 会像 transform 一样劫持
          后代 fixed 元素的包含块 —— 操作栏会被钉进文档流深处而不是视口
          底部（实测 top≈3176px，视口高 844px，等于完全不可见）。 */}
      {createPortal(
        <div className="md:hidden mobile-sticky-actions px-3 py-2">
          <div className="flex items-center justify-between gap-1 max-w-3xl mx-auto">
            <div className="relative" ref={folderPickerRef}>
              <button
                onClick={handleFavorite}
                className={`flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-fufu font-cute text-[11px] transition-all touch-target ${
                  article.is_favorite ? 'text-fufu-pink' : 'text-fufu-text-muted'
                }`}
              >
                <Star size={20} weight={article.is_favorite ? 'fill' : 'regular'} />
                {article.is_favorite ? '已收藏' : '收藏'}
              </button>

              {/* 文件夹选择器（移动端） */}
              <AnimatePresence>
                {showFolderPicker && article.is_favorite && folders.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: -4, scale: 0.95 }}
                    animate={{ opacity: 1, y: -4, scale: 1 }}
                    exit={{ opacity: 0, y: -4, scale: 0.95 }}
                    transition={{ duration: 0.15 }}
                    className="absolute bottom-full left-0 mb-1 bg-white rounded-fufu-modal shadow-fufu-float border border-fufu-highlight/30 p-1.5 min-w-[180px] z-30"
                  >
                    <p className="px-3 py-1.5 text-xs text-fufu-text-muted font-body">
                      📁 添加到文件夹
                    </p>
                    {folders.map((f) => (
                      <button
                        key={f.id}
                        onClick={() => handleAddToFolder(f.id)}
                        disabled={addToFolder.isPending}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded-fufu text-sm font-body text-fufu-text hover:bg-fufu-cream transition-colors text-left disabled:opacity-40"
                      >
                        <span>{f.icon}</span>
                        <span>{f.name}</span>
                        <span className="text-fufu-text-muted text-xs ml-auto">
                          {f.article_count}
                        </span>
                      </button>
                    ))}
                    <div className="my-1 border-t border-fufu-highlight/20" />
                    <button
                      onClick={() => setShowFolderPicker(false)}
                      className="w-full flex items-center gap-2 px-3 py-2 rounded-fufu text-sm font-body text-fufu-text-muted hover:bg-fufu-cream transition-colors"
                    >
                      暂不分类
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <button
              onClick={() => toggleLater.mutate({ id: article.id, value: !article.is_later })}
              className={`flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-fufu font-cute text-[11px] transition-all touch-target ${
                article.is_later ? 'text-fufu-mint' : 'text-fufu-text-muted'
              }`}
            >
              <BookmarkSimple size={20} weight={article.is_later ? 'fill' : 'regular'} />
              {article.is_later ? '待阅读' : '稍后读'}
            </button>

            {/* TTS on mobile */}
            {article.content && (
              <div className="flex flex-col items-center gap-0.5">
                <TTSReader content={article.content} title={article.title} />
              </div>
            )}

            {/* Share on mobile */}
            <div className="flex flex-col items-center gap-0.5">
              <ShareButton
                title={article.title}
                url={window.location.href}
                description={article.summary || ''}
                imageUrl={article.image_url || ''}
              />
            </div>

            <button
              onClick={() => aiSummarize.mutate(article.id)}
              disabled={aiSummarize.isPending}
              className="flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-fufu font-cute text-[11px] text-fufu-text-muted transition-all touch-target"
              title="AI 摘要"
            >
              <Sparkle size={20} className={aiSummarize.isPending ? 'animate-spin' : ''} />
              AI摘要
            </button>
          </div>
        </div>,
        document.body,
      )}

      {/* ===== 4. Existing quick summary ===== */}
      {article.summary &&
        (() => {
          const cleanSummary = article.summary
            .replace(/<[^>]+>/g, '')
            .replace(/&[^;]+;/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
          return cleanSummary ? (
            <motion.div
              variants={fadeInUp}
              initial="hidden"
              animate="visible"
              transition={{ delay: 0.15 }}
              className={`mb-5 p-4 rounded-fufu-card border border-dashed ${
                hasDeep
                  ? 'bg-fufu-highlight/20 border-fufu-teal/15'
                  : 'bg-fufu-highlight/40 border-fufu-pink/20'
              }`}
            >
              <p className="font-cute text-xs text-fufu-text-light mb-1">
                {hasDeep ? '💡 快速摘要' : '💡 fufu帮你读'}
              </p>
              <p className="font-body text-sm text-fufu-text leading-relaxed">{cleanSummary}</p>
            </motion.div>
          ) : null;
        })()}

      {/* ===== 5. Deep Summary sections ===== */}
      {deepSummary && hasDeep ? (
        <motion.div
          variants={stagger}
          initial="hidden"
          animate="visible"
          className="space-y-4 mb-6"
        >
          {/* 5a. One-liner */}
          {deepSummary.one_liner && (
            <DeepSection icon="📌" title="一句话总结" delay={0}>
              <div className="border-l-4 border-fufu-teal pl-4 py-1">
                <p className="font-body text-base md:text-lg text-fufu-text leading-relaxed font-medium">
                  {deepSummary.one_liner}
                </p>
              </div>
            </DeepSection>
          )}

          {/* 5b. Key data */}
          {deepSummary.key_data && deepSummary.key_data.length > 0 && (
            <DeepSection icon="📊" title="关键数据" delay={0.05}>
              <div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-hide">
                {deepSummary.key_data.map((item, i) => (
                  <div
                    key={i}
                    className="flex-shrink-0 min-w-[120px] bg-fufu-cream/80 rounded-fufu p-3 text-center border border-fufu-highlight/40"
                  >
                    <p className="font-cute text-xl md:text-2xl text-fufu-teal-deep leading-tight">
                      {item.value}
                    </p>
                    <p className="font-body text-xs text-fufu-text-muted mt-1 leading-snug">
                      {item.label}
                    </p>
                  </div>
                ))}
              </div>
            </DeepSection>
          )}

          {/* 5c. Core points */}
          {deepSummary.core_points && deepSummary.core_points.length > 0 && (
            <DeepSection icon="🔍" title="核心观点" delay={0.1}>
              <ol className="space-y-3">
                {deepSummary.core_points.map((point, i) => (
                  <li key={i} className="flex gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-fufu-teal/10 text-fufu-teal-deep font-cute text-xs flex items-center justify-center mt-0.5">
                      {i + 1}
                    </span>
                    <p className="font-body text-sm text-fufu-text leading-relaxed">{point}</p>
                  </li>
                ))}
              </ol>
            </DeepSection>
          )}

          {/* 5d. Background */}
          {deepSummary.background && (
            <DeepSection icon="💡" title="背景补充" delay={0.15}>
              <div className="font-body text-sm text-fufu-text leading-relaxed">
                {!bgExpanded && deepSummary.background.length > 200 ? (
                  <>
                    <p className="line-clamp-3">{deepSummary.background}</p>
                    <button
                      onClick={() => setBgExpanded(true)}
                      className="flex items-center gap-1 mt-2 text-xs font-cute text-fufu-teal-deep hover:text-fufu-teal transition-colors"
                    >
                      展开全部 <CaretDown size={14} />
                    </button>
                  </>
                ) : (
                  <>
                    <p className="whitespace-pre-line">{deepSummary.background}</p>
                    {deepSummary.background.length > 200 && (
                      <button
                        onClick={() => setBgExpanded(false)}
                        className="flex items-center gap-1 mt-2 text-xs font-cute text-fufu-text-muted hover:text-fufu-text-light transition-colors"
                      >
                        收起 <CaretUp size={14} />
                      </button>
                    )}
                  </>
                )}
              </div>
            </DeepSection>
          )}

          {/* 5e. Reactions */}
          {deepSummary.reactions &&
            (deepSummary.reactions.support ||
              deepSummary.reactions.oppose ||
              deepSummary.reactions.neutral) && (
              <DeepSection icon="🗣️" title="各方反应" delay={0.2}>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {deepSummary.reactions.support && (
                    <div className="bg-fufu-soft-green/20 border border-fufu-mint/20 rounded-fufu p-4">
                      <p className="font-cute text-sm text-fufu-mint mb-1">👍 支持方</p>
                      <p className="font-body text-xs text-fufu-text leading-relaxed">
                        {deepSummary.reactions.support}
                      </p>
                    </div>
                  )}
                  {deepSummary.reactions.oppose && (
                    <div className="bg-fufu-error-light/20 border border-fufu-error/20 rounded-fufu p-4">
                      <p className="font-cute text-sm text-fufu-error mb-1">👎 反对方</p>
                      <p className="font-body text-xs text-fufu-text leading-relaxed">
                        {deepSummary.reactions.oppose}
                      </p>
                    </div>
                  )}
                  {deepSummary.reactions.neutral && (
                    <div className="bg-fufu-soft-purple/20 border border-fufu-lavender/20 rounded-fufu p-4">
                      <p className="font-cute text-sm text-fufu-lavender mb-1">🤔 中立方</p>
                      <p className="font-body text-xs text-fufu-text leading-relaxed">
                        {deepSummary.reactions.neutral}
                      </p>
                    </div>
                  )}
                </div>
              </DeepSection>
            )}
        </motion.div>
      ) : (
        /* ===== Generate Deep Summary button (when no deep_summary) ===== */
        <div className="mb-6">
          <motion.div
            variants={fadeInUp}
            initial="hidden"
            animate="visible"
            transition={{ delay: 0.2 }}
            className="bg-white/70 backdrop-blur-sm rounded-fufu-card border-2 border-dashed border-fufu-teal/20 p-6 text-center shadow-fufu"
          >
            <div className="flex justify-center mb-3">
              <div
                className={`w-14 h-14 rounded-full bg-fufu-teal/10 flex items-center justify-center ${generateDeep.isPending ? 'animate-pulse-soft' : ''}`}
              >
                <Robot
                  size={28}
                  className={`text-fufu-teal ${generateDeep.isPending ? 'animate-float' : ''}`}
                  weight="duotone"
                />
              </div>
            </div>
            <h3 className="font-cute text-fufu-text mb-1.5">🤖 AI 深度解读</h3>
            <p className="font-body text-sm text-fufu-text-muted mb-4 max-w-md mx-auto">
              点击生成结构化摘要，包含关键数据、核心观点、背景补充等
            </p>
            <button
              onClick={handleGenerateDeep}
              disabled={generateDeep.isPending}
              className={`fufu-btn-primary inline-flex items-center gap-2 px-6 py-2.5 rounded-fufu-btn font-cute text-sm transition-all ${
                generateDeep.isPending ? 'opacity-70' : ''
              }`}
            >
              {generateDeep.isPending ? (
                <>
                  <span className="inline-block w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  正在深度解读...
                </>
              ) : (
                <>
                  <Sparkle size={18} />
                  生成深度摘要
                </>
              )}
            </button>
          </motion.div>

          {/* Pulsing skeleton while generating */}
          {generateDeep.isPending && (
            <div className="space-y-3 mt-5">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="bg-white/40 rounded-fufu-card p-5 animate-pulse-soft">
                  <div className="skeleton h-5 w-32 rounded mb-3" />
                  <div className="space-y-2">
                    <div className="skeleton h-3 w-full rounded" />
                    <div className="skeleton h-3 w-4/5 rounded" />
                    {i === 2 && <div className="skeleton h-3 w-3/5 rounded" />}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ===== 6. Poll ===== */}
      <div className="mb-6">
        <ArticlePoll articleId={articleId} />
      </div>

      {/* ===== 7. Article content (original body) ===== */}
      {article.content ? (
        <motion.div
          variants={fadeInUp}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-60px' }}
          transition={{ delay: 0.2 }}
          className="fufu-card p-4 sm:p-6 md:p-8 rounded-fufu-card font-body text-fufu-text leading-relaxed prose max-w-none mb-6 md:mb-6
            break-words [&_*]:break-words
            prose-mobile
            [&_p]:mb-4 [&_img]:rounded-fufu-img [&_img]:max-w-full [&_a]:text-fufu-pink
            [&_h1]:font-cute [&_h2]:font-cute [&_h3]:font-cute
            [&_blockquote]:border-l-4 [&_blockquote]:border-fufu-pink [&_blockquote]:pl-4 [&_blockquote]:text-fufu-text-light"
          dangerouslySetInnerHTML={{ __html: safeContent }}
        />
      ) : (
        <motion.div
          variants={fadeInUp}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-60px' }}
          className="fufu-card p-6 sm:p-8 rounded-fufu-card text-center mb-6"
        >
          <p className="font-cute text-fufu-text-light">📭 这篇文章还没有提取到内容呢～</p>
        </motion.div>
      )}

      {/* ===== 8. Multi-source aggregation ===== */}
      <AggregatedView articleId={article.id} />

      {/* ===== 9. View original link (bottom, subtle) ===== */}
      <motion.div
        variants={fadeInUp}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin: '-60px' }}
        className="text-center mb-8 pt-6 border-t border-fufu-pink-soft/20"
      >
        <p className="font-body text-xs text-fufu-text-muted mb-3">
          以上内容由 AI 辅助生成，查看原文获取完整信息
        </p>
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 font-cute text-sm text-fufu-text-light hover:text-fufu-teal-deep transition-colors underline underline-offset-2 decoration-fufu-text-muted/30 hover:decoration-fufu-teal-deep/50"
        >
          <Share size={16} />
          查看原文
        </a>
      </motion.div>

      {/* ===== 10. Related articles ===== */}
      <RelatedArticles
        articleId={article.id}
        sourceId={article.source_id}
        tags={article.tags || []}
      />

      {/* ===== 11. 评论区 =====
          修复：原先这里渲染了两次 CommentSection（一次 previewOnly、一次完整版），
          两者 queryKey 完全相同，会并发发两份相同的请求并渲染两套评论区。
          现在只保留一个完整评论区。 */}
      <CommentSection articleId={article.id} />
    </div>
  );
}
