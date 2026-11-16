import { useState } from 'react';
import { Link } from 'react-router-dom';
import { BookmarkSimple } from '@phosphor-icons/react';
import { motion } from 'framer-motion';
import { useLater, useToggleLater } from '../hooks/useArticles';
import VirtualArticleList from '../components/common/VirtualArticleList';
import TiltCard from '../components/effects/TiltCard';
import { ClickRippleWrapper } from '../components/effects/ClickRipple';

export default function LaterPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isPlaceholderData, error, refetch } = useLater(page);
  const showLoading = isLoading || isPlaceholderData;
  const toggleLater = useToggleLater();

  const articles = data?.articles ?? [];
  const total = data?.total ?? 0;
  const pageSize = data?.page_size ?? 20;

  return (
    <div>
      <div className="mb-8">
        <h2 className="font-cute text-3xl text-fufu-text">📖 稍后阅读</h2>
        <p className="font-body text-sm text-fufu-text-light mt-1">有空的时候再慢慢看～☕</p>
      </div>

      {error ? (
        <div className="text-center py-20">
          <p className="text-6xl mb-4 animate-float">😿</p>
          <p className="font-cute text-xl text-fufu-text">加载列表失败啦～</p>
          <button className="fufu-btn-primary mt-4" onClick={() => refetch()}>
            重新加载
          </button>
        </div>
      ) : showLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="fufu-card p-6 rounded-fufu-card">
              <div className="skeleton h-5 w-3/4 rounded mb-3" />
              <div className="skeleton h-4 w-full rounded mb-2" />
            </div>
          ))}
        </div>
      ) : articles.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-6xl mb-4 animate-float">☕</p>
          <p className="font-cute text-xl text-fufu-text">这里还空空的呢～</p>
          <p className="font-body text-sm text-fufu-text-light mt-2">
            看到感兴趣的文章可以先存下来哦！
          </p>
        </div>
      ) : (
        <VirtualArticleList
          items={articles}
          estimateSize={160}
          renderItem={(a, idx) => (
            <motion.div
              className="pb-4"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.02 }}
            >
              <TiltCard maxTilt={2}>
                <ClickRippleWrapper>
                  <Link
                    to={`/articles/${a.id}`}
                    className="fufu-card p-6 block group rounded-fufu-card news-card-hover"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <span className="fufu-tag bg-fufu-mint-light/50 text-fufu-mint font-cute">
                          {a.source_name || '🌸 未分类'}
                        </span>
                        <h3 className="font-cute text-lg text-fufu-text group-hover:text-fufu-lavender transition-colors line-clamp-2 mt-2">
                          {a.title}
                        </h3>
                        <p className="font-body text-sm text-fufu-text-light mt-2 line-clamp-2">
                          {a.summary}
                        </p>
                      </div>
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          toggleLater.mutate({ id: a.id, value: false });
                        }}
                        className="p-2 rounded-full text-fufu-mint bg-fufu-mint-light/30 hover:bg-fufu-mint-light/50 transition-all shrink-0 ml-4"
                      >
                        <BookmarkSimple size={20} weight="fill" />
                      </button>
                    </div>
                  </Link>
                </ClickRippleWrapper>
              </TiltCard>
            </motion.div>
          )}
        />
      )}

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
