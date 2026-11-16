import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Star,
  FolderSimple,
  DotsThreeVertical,
  CaretRight,
  ArrowRight,
} from '@phosphor-icons/react';
import { motion } from 'framer-motion';
import { useFavorites, useToggleFavorite } from '../hooks/useArticles';
import {
  useFolders,
  useFolderArticles,
  useRemoveFromFolder,
  useMoveArticle,
  useAddToFolder,
} from '../hooks/useFolders';
import FolderManager from '../components/favorites/FolderManager';
import VirtualArticleList from '../components/common/VirtualArticleList';
import TiltCard from '../components/effects/TiltCard';
import { ClickRippleWrapper } from '../components/effects/ClickRipple';

export default function FavoritesPage() {
  const [page, setPage] = useState(1);
  const [folderPage, setFolderPage] = useState(1);
  const [activeFolderId, setActiveFolderId] = useState<number | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    articleId: number;
    currentFolderId: number | null;
  } | null>(null);

  // 加载文件夹列表
  const { data: folders = [] } = useFolders();
  const activeFolder = folders.find((f) => f.id === activeFolderId) ?? null;

  // 加载全部收藏
  const {
    data: allFavData,
    isLoading: allLoading,
    isPlaceholderData: allPlaceholder,
    error: allError,
    refetch: allRefetch,
  } = useFavorites(page);
  const showAllLoading = allLoading || allPlaceholder;

  // 加载文件夹内的文章
  const {
    data: folderData,
    isLoading: folderLoading,
    isPlaceholderData: folderPlaceholder,
  } = useFolderArticles(activeFolderId, folderPage);

  const toggleFav = useToggleFavorite();
  const removeFromFolder = useRemoveFromFolder();
  const moveArticle = useMoveArticle();
  const addToFolder = useAddToFolder();

  // 根据当前选中的 tab 决定显示哪些文章
  const isFolderView = activeFolderId !== null;
  const articles = isFolderView ? (folderData?.items ?? []) : (allFavData?.articles ?? []);
  const total = isFolderView ? (folderData?.total ?? 0) : (allFavData?.total ?? 0);
  const currentPage = isFolderView ? folderPage : page;
  const pageSize = isFolderView ? (folderData?.page_size ?? 20) : (allFavData?.page_size ?? 20);
  const isLoading = isFolderView ? folderLoading || folderPlaceholder : showAllLoading;
  const error = isFolderView ? null : allError;

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const handlePrevPage = () => {
    if (isFolderView) setFolderPage((p) => Math.max(1, p - 1));
    else setPage((p) => Math.max(1, p - 1));
  };
  const handleNextPage = () => {
    if (isFolderView) setFolderPage((p) => Math.min(totalPages, p + 1));
    else setPage((p) => Math.min(totalPages, p + 1));
  };

  const handleSelectFolder = (folderId: number | null) => {
    setActiveFolderId(folderId);
    setFolderPage(1);
    setContextMenu(null);
  };

  // 右键菜单
  const handleContextMenu = (e: React.MouseEvent, articleId: number) => {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, articleId, currentFolderId: activeFolderId });
  };

  const handleMoveToFolder = (toFolderId: number) => {
    if (!contextMenu) return;

    if (contextMenu.currentFolderId === null) {
      // 文章不在任何文件夹中，直接添加到目标文件夹
      addToFolder.mutate(
        { folderId: toFolderId, articleId: contextMenu.articleId },
        { onSettled: () => setContextMenu(null) },
      );
      return;
    }

    if (toFolderId === contextMenu.currentFolderId) {
      setContextMenu(null);
      return;
    }

    // 文章在文件夹中，移动到另一个文件夹
    moveArticle.mutate(
      { articleId: contextMenu.articleId, fromFolderId: contextMenu.currentFolderId, toFolderId },
      { onSettled: () => setContextMenu(null) },
    );
  };

  const handleUnfavorite = (articleId: number) => {
    toggleFav.mutate({ id: articleId, value: false });
    setContextMenu(null);
  };

  const handleRemoveFromFolder = (articleId: number) => {
    if (activeFolderId) {
      removeFromFolder.mutate({ folderId: activeFolderId, articleId });
    }
    setContextMenu(null);
  };

  // 关闭右键菜单（点击空白处）
  const closeContextMenu = () => setContextMenu(null);

  return (
    <div onClick={closeContextMenu}>
      {/* 标题区 */}
      <div className="mb-4">
        <h2 className="font-cute text-3xl text-fufu-text">❤️ 我的收藏</h2>
        <p className="font-body text-sm text-fufu-text-light mt-1">
          {activeFolder
            ? `正在浏览「${activeFolder.icon} ${activeFolder.name}」`
            : '这些都是你珍视的好文章呢～💕'}
        </p>
      </div>

      {/* 文件夹管理栏 */}
      <FolderManager
        folders={folders}
        activeFolderId={activeFolderId}
        onSelectFolder={handleSelectFolder}
      />

      {/* 内容区 */}
      {error ? (
        <div className="text-center py-20">
          <p className="text-6xl mb-4 animate-float">😿</p>
          <p className="font-cute text-xl text-fufu-text">加载收藏失败啦～</p>
          <button className="fufu-btn-primary mt-4" onClick={() => allRefetch()}>
            重新加载
          </button>
        </div>
      ) : isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="fufu-card p-4 sm:p-6 rounded-fufu-card">
              <div className="skeleton h-5 w-3/4 rounded mb-3" />
              <div className="skeleton h-4 w-full rounded mb-2" />
            </div>
          ))}
        </div>
      ) : articles.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-6xl mb-4 animate-float">{isFolderView ? '📂' : '💛'}</p>
          <p className="font-cute text-xl text-fufu-text">
            {isFolderView ? '这个文件夹还是空的呢～' : '收藏夹还是空的呢～'}
          </p>
          <p className="font-body text-sm text-fufu-text-light mt-2">
            {isFolderView ? '去文章页面把喜欢的文章加进来吧！' : '遇到喜欢的文章记得点星星哦！'}
          </p>
          {isFolderView && (
            <Link to="/articles" className="fufu-btn-primary inline-flex items-center gap-2 mt-4">
              <ArrowRight size={16} /> 去发现文章
            </Link>
          )}
        </div>
      ) : (
        <VirtualArticleList
          items={articles}
          estimateSize={160}
          renderItem={(a: any, idx: number) => (
            <motion.div
              className="pb-4 relative"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.02 }}
            >
              <TiltCard maxTilt={2}>
                <div className="fufu-card p-4 sm:p-6 rounded-fufu-card news-card-hover group relative">
                  <div className="flex items-start justify-between">
                    <Link to={`/articles/${a.id}`} className="flex-1 min-w-0">
                      <span className="fufu-tag bg-fufu-pink/10 text-fufu-pink font-cute">
                        {a.source_name || '🌸 未分类'}
                      </span>
                      <h3 className="font-cute text-lg text-fufu-text group-hover:text-fufu-pink transition-colors line-clamp-2 mt-2">
                        {a.title}
                      </h3>
                      <p className="font-body text-sm text-fufu-text-light mt-2 line-clamp-2">
                        {a.summary}
                      </p>
                      <div className="flex items-center gap-3 mt-2.5 text-xs text-fufu-text-muted font-body">
                        {a.published_at && (
                          <span>{new Date(a.published_at).toLocaleDateString('zh-CN')}</span>
                        )}
                        {isFolderView && folders.length > 0 && (
                          <span className="text-fufu-teal-deep">📁 {activeFolder?.name}</span>
                        )}
                      </div>
                    </Link>

                    {/* 操作按钮组 */}
                    <div className="flex items-center gap-1 shrink-0 ml-4">
                      {/* 取消收藏 */}
                      <ClickRippleWrapper>
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            handleUnfavorite(a.id);
                          }}
                          className="p-2 rounded-full text-fufu-pink bg-fufu-pink-soft/30 hover:bg-fufu-pink-soft/50 transition-all"
                          title="取消收藏"
                        >
                          <Star size={20} weight="fill" />
                        </button>
                      </ClickRippleWrapper>
                      {/* 右键菜单触发 */}
                      <ClickRippleWrapper>
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            handleContextMenu(e as any, a.id);
                          }}
                          className="p-2 rounded-full text-fufu-text-muted hover:text-fufu-text bg-transparent hover:bg-fufu-cream transition-all"
                          title="更多操作"
                        >
                          <DotsThreeVertical size={18} />
                        </button>
                      </ClickRippleWrapper>
                    </div>
                  </div>
                </div>
              </TiltCard>
            </motion.div>
          )}
        />
      )}

      {/* 分页 */}
      {total > 0 && (
        <div className="flex items-center justify-center gap-4 mt-8">
          <button
            className="fufu-btn bg-white text-fufu-text-light disabled:opacity-30 rounded-fufu-btn shadow-fufu"
            disabled={currentPage <= 1}
            onClick={handlePrevPage}
          >
            ← 上一页
          </button>
          <span className="font-cute text-sm text-fufu-text-light">
            {currentPage} / {totalPages}
          </span>
          <button
            className="fufu-btn bg-white text-fufu-text-light disabled:opacity-30 rounded-fufu-btn shadow-fufu"
            disabled={currentPage >= totalPages}
            onClick={handleNextPage}
          >
            下一页 →
          </button>
        </div>
      )}

      {/* ===== 右键菜单 ===== */}
      {contextMenu && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.15 }}
          className="fixed z-50 bg-white rounded-fufu-modal shadow-fufu-float border border-fufu-highlight/30 p-1.5 min-w-[180px] overflow-hidden"
          style={{
            left: Math.min(contextMenu.x, window.innerWidth - 200),
            top: Math.min(contextMenu.y, window.innerHeight - 300),
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* 移动到文件夹子菜单 */}
          <div className="relative group/menu">
            <button className="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-fufu text-sm font-body text-fufu-text hover:bg-fufu-cream transition-colors">
              <span className="flex items-center gap-2">
                <FolderSimple size={16} />
                移动到文件夹
              </span>
              <CaretRight size={14} />
            </button>
            <div className="absolute left-full top-0 ml-0.5 bg-white rounded-fufu-modal shadow-fufu-float border border-fufu-highlight/30 p-1.5 min-w-[160px] hidden group-hover/menu:block">
              {folders
                .filter((f) => f.id !== contextMenu.currentFolderId)
                .map((f) => (
                  <button
                    key={f.id}
                    onClick={() => handleMoveToFolder(f.id)}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-fufu text-sm font-body text-fufu-text hover:bg-fufu-cream transition-colors text-left"
                  >
                    <span>{f.icon}</span>
                    <span>{f.name}</span>
                    <span className="text-fufu-text-muted text-xs ml-auto">{f.article_count}</span>
                  </button>
                ))}
              {folders.filter((f) => f.id !== contextMenu.currentFolderId).length === 0 && (
                <p className="px-3 py-2 text-xs text-fufu-text-muted">还没有其他文件夹呢～</p>
              )}
            </div>
          </div>

          {/* 从文件夹移除 */}
          {contextMenu.currentFolderId !== null && (
            <button
              onClick={() => handleRemoveFromFolder(contextMenu.articleId)}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-fufu text-sm font-body text-fufu-text hover:bg-fufu-cream transition-colors"
            >
              <ArrowRight size={16} />
              从本文件夹移除
            </button>
          )}

          <div className="my-1 border-t border-fufu-highlight/20" />

          {/* 取消收藏 */}
          <button
            onClick={() => handleUnfavorite(contextMenu.articleId)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-fufu text-sm font-body text-fufu-error hover:bg-fufu-error-light/20 transition-colors"
          >
            <Star size={16} weight="fill" />
            取消收藏
          </button>
        </motion.div>
      )}
    </div>
  );
}
