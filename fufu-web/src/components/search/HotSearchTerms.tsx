import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Fire } from '@phosphor-icons/react';
import { fetchHotSearchTerms } from '../../api/search';

interface HotSearchTermsProps {
  onTermClick: (term: string) => void;
}

const FALLBACK_TERMS = [
  'AI 人工智能',
  '芯片制裁',
  '新番推荐',
  '游戏评测',
  '设计趋势',
  '科技新闻',
  '前端开发',
  '开源项目',
];

export default function HotSearchTerms({ onTermClick }: HotSearchTermsProps) {
  const [terms, setTerms] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchHotTerms() {
      try {
        const list = await fetchHotSearchTerms(8);
        if (cancelled) return;
        setTerms(list.length > 0 ? list.slice(0, 8) : FALLBACK_TERMS);
      } catch {
        if (!cancelled) setTerms(FALLBACK_TERMS);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchHotTerms();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="mb-4 p-4 rounded-fufu-card bg-fufu-pink-soft/10">
        <div className="flex items-center gap-2 mb-3">
          <Fire size={16} className="text-fufu-pink" />
          <span className="font-cute text-xs text-fufu-text-light">热门搜索</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton h-8 w-24 rounded-fufu-tag" />
          ))}
        </div>
      </div>
    );
  }

  if (terms.length === 0) return null;

  return (
    <div className="mb-4 p-4 rounded-fufu-card bg-gradient-to-r from-fufu-pink-soft/15 to-fufu-teal-soft/10 border border-fufu-pink/10">
      <div className="flex items-center gap-2 mb-3">
        <Fire size={16} className="text-fufu-pink" weight="fill" />
        <span className="font-cute text-xs text-fufu-text-light">热门搜索</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {terms.map((term, index) => (
          <motion.button
            key={term}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.06, duration: 0.3, ease: 'easeOut' }}
            whileHover={{ scale: 1.05, y: -1 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => onTermClick(term)}
            className="px-3 py-1.5 rounded-fufu-tag bg-white text-fufu-text-light font-body text-xs
                       hover:bg-fufu-teal hover:text-white hover:shadow-fufu-glow
                       transition-all duration-200 border border-fufu-teal/10"
          >
            {term}
          </motion.button>
        ))}
      </div>
    </div>
  );
}
