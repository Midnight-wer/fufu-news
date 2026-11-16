import type { AchievementItem } from '@/stores/achievementStore';

interface AchievementBadgeProps {
  item: AchievementItem;
}

const TIER_NAMES: Record<number, string> = { 1: '铜', 2: '银', 3: '金' };
const TIER_COLORS: Record<number, string> = {
  1: 'from-fufu-pink to-fufu-peach',
  2: 'from-fufu-lavender to-fufu-pink',
  3: 'from-yellow-300 to-amber-500',
};

export default function AchievementBadge({ item }: AchievementBadgeProps) {
  const unlocked = item.unlocked;
  const pct = Math.min(100, Math.round((item.progress / item.threshold) * 100));

  return (
    <div
      className={`relative flex flex-col items-center p-4 rounded-fufu-card transition-all duration-300 ${
        unlocked
          ? 'bg-white shadow-fufu ring-1 ring-fufu-pink/20'
          : 'bg-white/50 opacity-50 grayscale'
      }`}
    >
      <div
        className={`w-14 h-14 rounded-full flex items-center justify-center text-2xl mb-2 ${
          unlocked
            ? `bg-gradient-to-br ${TIER_COLORS[item.tier] || TIER_COLORS[1]}`
            : 'bg-fufu-pink-soft/30'
        }`}
      >
        {item.icon}
      </div>
      <p className="font-cute text-sm text-fufu-text text-center">{item.title}</p>
      <p className="font-body text-[10px] text-fufu-text-muted text-center mt-0.5">
        {item.description}
      </p>
      <div className="w-full mt-2">
        <div className="flex items-center justify-between mb-0.5">
          <span className="font-body text-[10px] text-fufu-text-muted">
            {item.progress}/{item.threshold}
          </span>
          <span className="font-body text-[10px] text-fufu-pink">
            {unlocked ? '✨ 已解锁' : `${pct}%`}
          </span>
        </div>
        <div className="w-full h-1.5 rounded-full bg-fufu-pink-soft/30 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${unlocked ? 'bg-fufu-mint' : 'bg-fufu-pink'}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
      <span
        className={`absolute -top-1.5 -right-1.5 font-cute text-[10px] px-1.5 py-0.5 rounded-full ${
          unlocked ? 'bg-fufu-pink text-white' : 'bg-fufu-pink-soft/30 text-fufu-text-muted'
        }`}
      >
        {TIER_NAMES[item.tier]}
      </span>
    </div>
  );
}
