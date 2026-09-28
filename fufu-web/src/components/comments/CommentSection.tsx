import { useState, useCallback, useRef, type FormEvent } from 'react';
import { Chat, Heart, ChatCircle, Trash, X, CaretDown, CaretUp } from '@phosphor-icons/react';
import { motion, AnimatePresence } from 'framer-motion';
import { useComments, useCreateComment, useReplyComment, useDeleteComment, useToggleLike } from '../../hooks/useComments';
import { useAuthStore } from '../../stores/authStore';
import type { CommentItem, CommentsResponse } from '../../api/comments';

// ===== Helpers =====
function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr + 'Z').getTime();
  const diff = Math.max(0, now - then);
  const sec = Math.floor(diff / 1000);
  const min = Math.floor(sec / 60);
  const hr = Math.floor(min / 60);
  const day = Math.floor(hr / 24);
  if (day > 0) return `${day}天前`;
  if (hr > 0) return `${hr}小时前`;
  if (min > 0) return `${min}分钟前`;
  return '刚刚';
}

const staggerItem = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } },
};

// ===== Skeleton =====
function CommentSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="bg-white/60 rounded-fufu-card border border-fufu-highlight/20 p-4 animate-pulse-soft">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-fufu-soft-purple/30" />
            <div className="space-y-1.5">
              <div className="h-3 w-20 bg-fufu-soft-purple/20 rounded" />
              <div className="h-2.5 w-14 bg-fufu-soft-purple/10 rounded" />
            </div>
          </div>
          <div className="space-y-2 ml-11">
            <div className="h-3 w-full bg-fufu-soft-purple/10 rounded" />
            <div className="h-3 w-3/4 bg-fufu-soft-purple/10 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ===== Single comment card =====
function CommentCard({
  comment,
  articleId,
  onReplyClick,
  replyingTo,
  replyContent,
  onReplyContentChange,
  onReplySubmit,
  replyPending,
  onCancelReply,
  currentUsername,
  isLoggedIn,
  depth = 0,
}: {
  comment: CommentItem;
  articleId: number;
  onReplyClick: (id: number) => void;
  replyingTo: number | null;
  replyContent: string;
  onReplyContentChange: (v: string) => void;
  onReplySubmit: (id: number) => void;
  replyPending: boolean;
  onCancelReply: () => void;
  currentUsername: string | null;
  isLoggedIn: boolean;
  depth?: number;
}) {
  const deleteComment = useDeleteComment();
  const toggleLike = useToggleLike();
  const [showReplies, setShowReplies] = useState(true);
  const [heartBurst, setHeartBurst] = useState(false);

  const isOwn = currentUsername === comment.username;
  const isDeleted = comment.content === '[已删除]';
  const replyCount = comment.replies?.length || 0;

  const handleLike = useCallback(() => {
    toggleLike.mutate(comment.id);
    setHeartBurst(true);
    setTimeout(() => setHeartBurst(false), 600);
  }, [comment.id, toggleLike]);

  const handleDelete = useCallback(() => {
    if (window.confirm('确定要删除这条评论吗？')) {
      deleteComment.mutate(comment.id);
    }
  }, [comment.id, deleteComment]);

  return (
    <motion.div
      variants={staggerItem}
      className={`${depth === 0 ? '' : 'ml-6 md:ml-10 mt-2'}`}
    >
      <div className="bg-white/60 rounded-fufu-card border border-fufu-highlight/20 p-3 md:p-4 group">
        {/* Header: avatar + username + time */}
        <div className="flex items-center gap-2.5 mb-2">
          <div className="w-7 h-7 rounded-full bg-fufu-teal/15 flex items-center justify-center flex-shrink-0">
            <span className="text-xs font-cute text-fufu-teal-deep">
              {isDeleted ? '👻' : (comment.username || '?')[0]}
            </span>
          </div>
          <span className={`font-cute text-sm truncate max-w-[120px] ${isDeleted ? 'text-fufu-text-muted italic' : 'text-fufu-text'}`}>
            {isDeleted ? '用户已删除' : comment.username}
          </span>
          <span className="text-xs text-fufu-text-muted font-body shrink-0 ml-auto">
            {timeAgo(comment.created_at)}
          </span>

          {/* Delete button (own comment, hover) */}
          {isOwn && !isDeleted && (
            <button
              onClick={handleDelete}
              disabled={deleteComment.isPending}
              className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-fufu hover:bg-fufu-error-light/20 text-fufu-text-muted hover:text-fufu-error"
              title="删除评论"
            >
              <Trash size={14} />
            </button>
          )}
        </div>

        {/* Content */}
        <p className={`font-body text-sm leading-relaxed mb-2.5 ml-9 ${isDeleted ? 'text-fufu-text-muted italic' : 'text-fufu-text'}`}>
          {comment.content}
        </p>

        {/* Actions */}
        {!isDeleted && (
          <div className="flex items-center gap-4 ml-9">
            {/* Like button */}
            <button
              onClick={handleLike}
              disabled={!isLoggedIn || toggleLike.isPending}
              className={`flex items-center gap-1 text-xs font-cute transition-all ${
                comment.is_liked
                  ? 'text-fufu-pink'
                  : 'text-fufu-text-muted hover:text-fufu-pink'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
              title={!isLoggedIn ? '请先登录' : undefined}
            >
              <motion.span
                animate={heartBurst ? { scale: [1, 1.4, 0.9, 1] } : {}}
                transition={{ duration: 0.4 }}
              >
                <Heart size={15} weight={comment.is_liked ? 'fill' : 'regular'} />
              </motion.span>
              {(comment.likes_count ?? 0) > 0 && (
                <span className="font-body">{comment.likes_count}</span>
              )}
            </button>

            {/* Reply button (only top-level comments) */}
            {depth === 0 && (
              <button
                onClick={() => onReplyClick(comment.id)}
                className={`flex items-center gap-1 text-xs font-cute transition-colors ${
                  replyingTo === comment.id
                    ? 'text-fufu-teal-deep'
                    : 'text-fufu-text-muted hover:text-fufu-teal-deep'
                }`}
              >
                <ChatCircle size={15} />
                回复
              </button>
            )}
          </div>
        )}
      </div>

      {/* Inline reply form */}
      <AnimatePresence>
        {replyingTo === comment.id && isLoggedIn && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="ml-6 md:ml-10 overflow-hidden"
          >
            <div className="mt-2 p-3 bg-fufu-cream/60 rounded-fufu border border-fufu-highlight/20">
              <textarea
                value={replyContent}
                onChange={(e) => onReplyContentChange(e.target.value)}
                placeholder={`回复 @${comment.username}...`}
                maxLength={500}
                rows={2}
                className="w-full bg-white/80 rounded-fufu-input border border-fufu-highlight/40 p-2.5 text-sm font-body text-fufu-text placeholder:text-fufu-text-muted resize-none focus:outline-none focus:border-fufu-teal/50 focus:ring-1 focus:ring-fufu-teal/20"
              />
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs text-fufu-text-muted font-body">
                  {replyContent.length}/500
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={onCancelReply}
                    className="px-3 py-1.5 text-xs font-cute text-fufu-text-muted hover:text-fufu-text-light transition-colors"
                  >
                    取消
                  </button>
                  <button
                    onClick={() => onReplySubmit(comment.id)}
                    disabled={!replyContent.trim() || replyPending}
                    className="px-4 py-1.5 text-xs font-cute bg-fufu-teal/80 text-white rounded-fufu-btn hover:bg-fufu-teal transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {replyPending ? '发送中...' : '回复'}
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Replies (1 level) */}
      {replyCount > 0 && depth === 0 && (
        <div className="mt-1">
          {/* Toggle */}
          {replyCount > 3 && (
            <button
              onClick={() => setShowReplies(!showReplies)}
              className="ml-6 md:ml-10 flex items-center gap-1 text-xs text-fufu-teal-deep font-cute hover:text-fufu-teal transition-colors py-1"
            >
              {showReplies ? (
                <>
                  <CaretUp size={14} /> 收起回复
                </>
              ) : (
                <>
                  <CaretDown size={14} /> 显示全部 {replyCount} 条回复
                </>
              )}
            </button>
          )}

          <AnimatePresence>
            {showReplies &&
              comment.replies.map((reply) => (
                <CommentCard
                  key={reply.id}
                  comment={reply}
                  articleId={articleId}
                  onReplyClick={onReplyClick}
                  replyingTo={replyingTo}
                  replyContent={replyContent}
                  onReplyContentChange={onReplyContentChange}
                  onReplySubmit={onReplySubmit}
                  replyPending={replyPending}
                  onCancelReply={onCancelReply}
                  currentUsername={currentUsername}
                  isLoggedIn={isLoggedIn}
                  depth={1}
                />
              ))}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  );
}

// ===== Main CommentSection =====
interface CommentSectionProps {
  articleId: number;
  /** If true, show only the top 3 hot comments as a preview */
  previewOnly?: boolean;
}

export default function CommentSection({ articleId, previewOnly = false }: CommentSectionProps) {
  const token = useAuthStore((s) => s.token);
  const isLoggedIn = !!token;

  // We need the current username for own-comment check.
  // The token contains the username in the JWT. Let's decode it from localStorage.
  const currentUsername = token ? decodeUsername(token) : null;

  const [sort, setSort] = useState<'latest' | 'hot'>('latest');
  const [page, setPage] = useState(1);
  const pageSize = previewOnly ? 3 : 20;

  const { data, isLoading, isError } = useComments(articleId, page, pageSize, sort);

  const createComment = useCreateComment();
  const replyComment = useReplyComment();

  // Comment input
  const [commentText, setCommentText] = useState('');
  const [replyingTo, setReplyingTo] = useState<number | null>(null);
  const [replyText, setReplyText] = useState('');

  const handleCreateComment = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      const trimmed = commentText.trim();
      if (!trimmed || createComment.isPending) return;
      createComment.mutate(
        { articleId, content: trimmed },
        {
          onSuccess: () => {
            setCommentText('');
            setPage(1);
          },
        },
      );
    },
    [articleId, commentText, createComment],
  );

  const handleReply = useCallback(
    (commentId: number) => {
      const trimmed = replyText.trim();
      if (!trimmed || replyComment.isPending) return;
      replyComment.mutate(
        { commentId, content: trimmed },
        {
          onSuccess: () => {
            setReplyText('');
            setReplyingTo(null);
          },
        },
      );
    },
    [replyText, replyComment],
  );

  const handleReplyClick = useCallback(
    (commentId: number) => {
      setReplyingTo((prev) => (prev === commentId ? null : commentId));
      setReplyText('');
    },
    [],
  );

  const loadMore = useCallback(() => {
    setPage((p) => p + 1);
  }, []);

  const items = data?.items || [];
  const total = data?.total ?? 0;
  const hasMore = page * pageSize < total;

  // ===== Loading =====
  if (isLoading && page === 1) {
    return (
      <section className="mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Chat size={20} className="text-fufu-teal-deep" />
          <h3 className="font-cute text-fufu-text text-base">💬 评论</h3>
        </div>
        <CommentSkeleton />
      </section>
    );
  }

  // ===== Error =====
  if (isError && !items.length) {
    return (
      <section className="mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Chat size={20} className="text-fufu-teal-deep" />
          <h3 className="font-cute text-fufu-text text-base">💬 评论</h3>
        </div>
        <div className="text-center py-8">
          <p className="text-fufu-text-muted font-body text-sm">加载评论失败，请稍后再试～</p>
        </div>
      </section>
    );
  }

  // ===== Preview mode =====
  if (previewOnly) {
    if (!items.length) return null;

    return (
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-40px' }}
        transition={{ duration: 0.4, delay: 0.35 }}
        className="mb-6"
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Chat size={18} className="text-fufu-teal-deep" />
            <h3 className="font-cute text-fufu-text text-sm">💬 热门评论 ({total})</h3>
          </div>
          <span className="text-xs text-fufu-teal-deep font-cute cursor-default">
            下拉查看全部
          </span>
        </div>

        <div className="space-y-2">
          {items.slice(0, 3).map((comment) => (
            <div
              key={comment.id}
              className="bg-white/60 rounded-fufu-card border border-fufu-highlight/20 p-3 cursor-default"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <div className="w-6 h-6 rounded-full bg-fufu-teal/10 flex items-center justify-center flex-shrink-0">
                  <span className="text-xs font-cute text-fufu-teal-deep">
                    {(comment.username || '?')[0]}
                  </span>
                </div>
                <span className="font-cute text-xs text-fufu-text">{comment.username}</span>
                <span className="text-xs text-fufu-text-muted font-body">{timeAgo(comment.created_at)}</span>
              </div>
              <p className="font-body text-xs text-fufu-text leading-relaxed line-clamp-2 ml-8">
                {comment.content}
              </p>
              {(comment.likes_count ?? 0) > 0 && (
                <div className="flex items-center gap-1 ml-8 mt-1 text-xs text-fufu-text-muted font-body">
                  <Heart size={12} weight="fill" className="text-fufu-pink" />
                  {comment.likes_count}
                </div>
              )}
            </div>
          ))}
        </div>
      </motion.div>
    );
  }

  // ===== Full comment section =====
  return (
    <section className="mb-6">
      {/* Header: title + sort toggle */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Chat size={20} className="text-fufu-teal-deep" />
          <h3 className="font-cute text-fufu-text text-base">
            💬 评论{total > 0 && ` (${total})`}
          </h3>
        </div>

        {/* Sort toggle */}
        <div className="flex items-center bg-white/70 rounded-fufu border border-fufu-highlight/30 overflow-hidden">
          <button
            onClick={() => { setSort('latest'); setPage(1); }}
            className={`px-3 py-1 text-xs font-cute transition-colors ${
              sort === 'latest'
                ? 'bg-fufu-teal/15 text-fufu-teal-deep'
                : 'text-fufu-text-muted hover:text-fufu-text-light'
            }`}
          >
            最新
          </button>
          <button
            onClick={() => { setSort('hot'); setPage(1); }}
            className={`px-3 py-1 text-xs font-cute transition-colors ${
              sort === 'hot'
                ? 'bg-fufu-teal/15 text-fufu-teal-deep'
                : 'text-fufu-text-muted hover:text-fufu-text-light'
            }`}
          >
            最热
          </button>
        </div>
      </div>

      {/* Comment input form */}
      <div className="mb-5">
        {isLoggedIn ? (
          <form onSubmit={handleCreateComment} className="bg-white/70 rounded-fufu-card border border-fufu-highlight/30 p-3 md:p-4 shadow-fufu">
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-fufu-teal/15 flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-cute text-fufu-teal-deep">
                  {currentUsername?.[0] || '?'}
                </span>
              </div>
              <div className="flex-1">
                <textarea
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  placeholder="写下你的看法..."
                  maxLength={1000}
                  rows={2}
                  className="w-full bg-fufu-cream/60 rounded-fufu-input border border-fufu-highlight/40 p-2.5 text-sm font-body text-fufu-text placeholder:text-fufu-text-muted resize-none focus:outline-none focus:border-fufu-teal/50 focus:ring-1 focus:ring-fufu-teal/20"
                />
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-fufu-text-muted font-body">
                    {commentText.length}/1000
                  </span>
                  <button
                    type="submit"
                    disabled={!commentText.trim() || createComment.isPending}
                    className="px-5 py-1.5 text-sm font-cute bg-fufu-teal/80 text-white rounded-fufu-btn hover:bg-fufu-teal transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {createComment.isPending ? '发送中...' : '发送'}
                  </button>
                </div>
              </div>
            </div>
          </form>
        ) : (
          <div className="bg-fufu-cream/60 rounded-fufu-card border border-dashed border-fufu-highlight/30 p-4 text-center">
            <p className="font-body text-sm text-fufu-text-muted">
              🔒 登录后即可评论
            </p>
          </div>
        )}
      </div>

      {/* Comment list */}
      {items.length > 0 ? (
        <motion.div
          variants={{
            hidden: {},
            visible: { transition: { staggerChildren: 0.06 } },
          }}
          initial="hidden"
          animate="visible"
          className="space-y-2"
        >
          {items.map((comment) => (
            <CommentCard
              key={comment.id}
              comment={comment}
              articleId={articleId}
              onReplyClick={handleReplyClick}
              replyingTo={replyingTo}
              replyContent={replyText}
              onReplyContentChange={setReplyText}
              onReplySubmit={handleReply}
              replyPending={replyComment.isPending}
              onCancelReply={() => setReplyingTo(null)}
              currentUsername={currentUsername}
              isLoggedIn={isLoggedIn}
            />
          ))}

          {/* Load more */}
          {hasMore && (
            <div className="text-center pt-2">
              <button
                onClick={loadMore}
                className="px-4 py-2 text-xs font-cute text-fufu-teal-deep bg-fufu-teal/5 rounded-fufu-btn hover:bg-fufu-teal/10 transition-colors"
              >
                加载更多评论
              </button>
            </div>
          )}
        </motion.div>
      ) : (
        !isLoading && (
          <div className="text-center py-10">
            <p className="text-3xl mb-3 animate-float">💭</p>
            <p className="font-cute text-fufu-text-muted">
              还没有评论，来发表第一条吧～
            </p>
          </div>
        )
      )}
    </section>
  );
}

// ===== JWT decoder (client-side, no verification needed for display) =====
function decodeUsername(token: string): string | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload?.sub || null;
  } catch {
    return null;
  }
}
