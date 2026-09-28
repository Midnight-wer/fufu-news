import { NavLink } from 'react-router-dom';
import { House, Rss, Star, BookmarkSimple, MagnifyingGlass, Gear, Fire, Clock } from '@phosphor-icons/react';
import { useSettingsStore } from '../../stores/settingsStore';

const navItems = [
  { to: '/articles', icon: House, label: '首页' },
  { to: '/sources', icon: Rss, label: '订阅源' },
  { to: '/ranking', icon: Fire, label: '排行榜' },
  { to: '/favorites', icon: Star, label: '收藏夹' },
  { to: '/later', icon: BookmarkSimple, label: '稍后阅读' },
  { to: '/history', icon: Clock, label: '阅读历史' },
  { to: '/search', icon: MagnifyingGlass, label: '搜一搜' },
];

const subtitleMap: Record<string, { text: string; icon: string }> = {
  miku: { text: '你的虚拟歌姬阅读伙伴', icon: '🎵' },
  milktea: { text: '一杯拿铁，慢读时光', icon: '🍂' },
  dark: { text: '夜深了，fufu 陪你', icon: '🌙' },
};

export default function Sidebar() {
  const theme = useSettingsStore((s) => s.settings.theme);
  const sub = subtitleMap[theme] || subtitleMap.miku;

  return (
    <aside className="w-[240px] h-screen sticky top-0 flex flex-col sidebar-miku z-30">
      {/* Logo */}
      <div className="px-6 pt-8 pb-6">
        <h1 className="font-cute text-2xl tracking-wide miku-gradient-text">
          fufu新闻{' '}
          <span className="inline-block animate-float text-lg">{sub.icon}</span>
        </h1>
        <p className="font-cute text-xs text-fufu-text-light mt-1">
          {sub.text}
        </p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-fufu font-cute text-base
               transition-all duration-200 ${
                 isActive
                   ? 'bg-gradient-to-r from-fufu-teal/12 to-fufu-lavender/10 text-fufu-teal-deep shadow-sm border border-fufu-teal/15'
                   : 'text-fufu-text-light hover:bg-fufu-teal-soft/20 hover:text-fufu-text'
               }`
            }
          >
            <Icon size={22} weight="duotone" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Settings */}
      <div className="px-3 pb-6">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex items-center gap-3 px-4 py-3 rounded-fufu font-cute text-base
             transition-all duration-200 ${
               isActive
                 ? 'bg-gradient-to-r from-fufu-teal/12 to-fufu-lavender/10 text-fufu-teal-deep shadow-sm border border-fufu-teal/15'
                 : 'text-fufu-text-light hover:bg-fufu-teal-soft/20 hover:text-fufu-text'
             }`
          }
        >
          <Gear size={22} weight="duotone" />
          小设置
        </NavLink>
      </div>
    </aside>
  );
}
