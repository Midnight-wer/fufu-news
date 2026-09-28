import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import client from '../../api/client';

const GREETINGS = [
  'こんにちは～来听听今天的新闻吧！🎶',
  'ミク为你播报最新资讯哦～💿',
  '发现了好多有趣的新闻呢！わくわく～',
  '休息一下，看看世界在发生什么～☕',
  '来自未来的信号已接收～✨',
  '今天的头条会是什么呢？🎤',
  '来杯奶茶，一起看新闻吧～🫧',
];

const PREFIXES = [
  '快看！',
  '哇～',
  '诶？',
  'ミク发现：',
  '新鲜出炉：',
  '🎵 ',
  '注目！',
  '刚刚刷到：',
];

interface Article {
  id: number;
  title: string;
  source_name?: string;
}

export default function NewsTicker() {
  const navigate = useNavigate();
  const [index, setIndex] = useState(0);
  const [greeting, setGreeting] = useState(GREETINGS[0]);
  const [visible, setVisible] = useState(true);

  // 拉取最新20篇用于轮播
  const { data } = useQuery<{ articles: Article[] }>({
    queryKey: ['news-ticker'],
    queryFn: async () => {
      const { data: res } = await client.get('/articles', {
        params: { page: 1, page_size: 20, sort: 'latest', since: '3d' },
      });
      return res;
    },
    refetchInterval: 180_000, // 每3分钟刷新一次
    staleTime: 120_000,
  });

  const articles = data?.articles ?? [];

  // 每10秒轮换
  useEffect(() => {
    if (articles.length === 0) return;
    const id = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setIndex((i) => (i + 1) % articles.length);
        setGreeting(GREETINGS[Math.floor(Math.random() * GREETINGS.length)]);
        setVisible(true);
      }, 400);
    }, 10_000);
    return () => clearInterval(id);
  }, [articles.length]);

  const handleClick = useCallback(() => {
    if (articles.length > 0) {
      const article = articles[index];
      navigate(`/articles/${article.id}`);
    }
  }, [articles, index, navigate]);

  // 没有文章时不显示
  if (articles.length === 0) return null;

  const current = articles[index];
  if (!current) return null;

  const prefix = PREFIXES[Math.floor(Math.random() * PREFIXES.length)];

  return (
    <motion.div
      className="fixed left-6 bottom-20 z-40 select-none max-w-[260px]"
      initial={{ opacity: 0, y: 30, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: 1.2, duration: 0.5, ease: 'easeOut' }}
      onClick={handleClick}
    >
      {/* 对话气泡 */}
      <motion.div
        className="relative cursor-pointer group"
        whileHover={{ scale: 1.03 }}
        whileTap={{ scale: 0.97 }}
      >
        {/* 气泡主体 */}
        <div className="relative bg-white/92 backdrop-blur-md border-2 border-fufu-teal-soft/40 rounded-2xl rounded-bl-md px-4 py-3 shadow-lg shadow-fufu-teal/8">
          {/* 小尾巴 */}
          <div className="absolute -left-[10px] bottom-3 w-0 h-0
            border-t-[10px] border-t-transparent
            border-r-[14px] border-r-white/92
            border-b-[10px] border-b-transparent
            drop-shadow-[-1px_1px_0_rgba(57,197,187,0.15)]"
          />

          {/* 顶部问候语 */}
          <p className="font-cute text-[11px] text-fufu-text-muted mb-1.5 leading-relaxed">
            {greeting}
          </p>

          {/* 新闻标题 — 轮播 */}
          <AnimatePresence mode="wait">
            <motion.div
              key={current.id}
              initial={{ opacity: 0, y: 8 }}
              animate={visible ? { opacity: 1, y: 0 } : { opacity: 0, y: -8 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35, ease: 'easeOut' }}
            >
              <p className="font-cute text-[13px] text-fufu-text leading-snug line-clamp-2 group-hover:text-fufu-teal-deep transition-colors">
                <span className="text-fufu-pink font-bold">{prefix}</span>
                {current.title}
              </p>
              {current.source_name && (
                <p className="font-body text-[10px] text-fufu-text-muted mt-1">
                  — {current.source_name}
                </p>
              )}
            </motion.div>
          </AnimatePresence>

          {/* 点按提示 */}
          <p className="font-body text-[9px] text-fufu-text-muted/50 mt-2 text-right opacity-0 group-hover:opacity-100 transition-opacity">
            点击查看详情 →
          </p>
        </div>
      </motion.div>

      {/* 进度条 — 10秒倒计时 */}
      <div className="mt-2 mx-1 h-[3px] rounded-full bg-fufu-teal-soft/15 overflow-hidden">
        <motion.div
          key={index}
          className="h-full rounded-full bg-gradient-to-r from-fufu-teal via-fufu-teal-deep to-fufu-pink"
          initial={{ width: '0%' }}
          animate={{ width: '100%' }}
          transition={{ duration: 10, ease: 'linear' }}
        />
      </div>
    </motion.div>
  );
}
