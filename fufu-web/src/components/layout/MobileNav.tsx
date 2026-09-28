import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  House,
  Fire,
  Star,
  MagnifyingGlass,
  Gear,
} from '@phosphor-icons/react';

const navItems = [
  { to: '/articles', icon: House, label: '首页', emoji: '🏠' },
  { to: '/ranking', icon: Fire, label: '热榜', emoji: '🔥' },
  { to: '/favorites', icon: Star, label: '收藏', emoji: '⭐' },
  { to: '/search', icon: MagnifyingGlass, label: '搜索', emoji: '🔍' },
  { to: '/settings', icon: Gear, label: '设置', emoji: '⚙️' },
];

export default function MobileNav() {
  return (
    <motion.nav
      initial={{ y: 80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.4, ease: 'easeOut', delay: 0.2 }}
      className="fixed bottom-0 left-0 right-0 z-50 md:hidden"
      style={{
        paddingBottom: 'env(safe-area-inset-bottom, 8px)',
      }}
    >
      {/* Glass-morphism 背景 */}
      <div
        className="absolute inset-0"
        style={{
          background: 'rgba(255, 255, 255, 0.82)',
          backdropFilter: 'blur(20px) saturate(180%)',
          WebkitBackdropFilter: 'blur(20px) saturate(180%)',
          borderTop: '1px solid rgba(var(--fufu-teal), 0.12)',
        }}
      />

      {/* 顶部渐变发光条 */}
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{
          background: 'linear-gradient(90deg, transparent, rgb(var(--fufu-teal)) 30%, rgb(var(--fufu-pink)) 70%, transparent)',
          opacity: 0.4,
        }}
      />

      {/* 导航项 */}
      <div className="relative flex items-center justify-around px-1 pt-2 pb-1">
        {navItems.map(({ to, icon: Icon, label, emoji }, index) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `relative flex flex-col items-center justify-center gap-0.5 py-1.5 px-2 rounded-fufu min-w-[56px] min-h-[48px] transition-all duration-200 select-none ${
                isActive
                  ? 'text-fufu-teal-deep'
                  : 'text-fufu-text-muted hover:text-fufu-text-light active:scale-95'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {/* 活跃背景 */}
                {isActive && (
                  <motion.div
                    layoutId="mobileNavActive"
                    className="absolute inset-1 rounded-fufu"
                    style={{
                      background: 'rgba(var(--fufu-teal), 0.08)',
                    }}
                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                  />
                )}

                {/* 图标 */}
                <span className="relative z-10 flex items-center justify-center">
                  {isActive ? (
                    <motion.span
                      key="active-icon"
                      initial={{ scale: 0.6, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ duration: 0.2 }}
                    >
                      <Icon size={22} weight="fill" />
                    </motion.span>
                  ) : (
                    <Icon size={22} weight="regular" />
                  )}
                </span>

                {/* 标签 */}
                <span
                  className={`relative z-10 font-cute text-[10px] leading-tight ${
                    isActive ? 'font-bold' : ''
                  }`}
                >
                  {label}
                </span>

                {/* 活跃指示点 */}
                {isActive && (
                  <motion.div
                    layoutId="mobileNavDot"
                    className="absolute top-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full"
                    style={{
                      background: 'rgb(var(--fufu-teal))',
                    }}
                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                  />
                )}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </motion.nav>
  );
}
