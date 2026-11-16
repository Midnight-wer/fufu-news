import { motion } from 'framer-motion';
import { useAchievements } from '@/hooks/useAchievements';
import AchievementBadge from './AchievementBadge';

const CATEGORY_NAMES: Record<string, string> = {
  explore: '🔍 探索',
  reading: '📖 阅读',
  collecting: '💎 收集',
};

export default function AchievementList() {
  const { data, isLoading, isPlaceholderData } = useAchievements();
  const achievements = data ?? [];
  const showLoading = isLoading || isPlaceholderData;

  if (showLoading) {
    return (
      <div className="grid grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="skeleton h-40 rounded-fufu-card" />
        ))}
      </div>
    );
  }

  if (achievements.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="font-cute text-fufu-text-muted">还没有成就哦～🌸</p>
      </div>
    );
  }

  const grouped: Record<string, typeof achievements> = {};
  for (const item of achievements) {
    (grouped[item.category] ??= []).push(item);
  }

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([cat, items]) => (
        <div key={cat}>
          <h4 className="font-cute text-sm text-fufu-text-light mb-3">
            {CATEGORY_NAMES[cat] || cat}
          </h4>
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-4">
            {items.map((item, i) => (
              <motion.div
                key={item.key}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <AchievementBadge item={item} />
              </motion.div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
