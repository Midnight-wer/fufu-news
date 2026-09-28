import { useRef, useState, useEffect, useCallback } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { List, X } from '@phosphor-icons/react';
import Sidebar from './Sidebar';
import MobileNav from './MobileNav';
import FloatingParticles from '../effects/FloatingParticles';
import ScrollRubberBand from '../effects/ScrollRubberBand';
import NewsTicker from '../companion/NewsTicker';

export default function MainLayout() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navigate = useNavigate();

  // 键盘快捷键
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Ctrl+K / Cmd+K → 搜索页
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      navigate('/search');
      return;
    }
    // ESC → 关闭移动端菜单
    if (e.key === 'Escape') {
      setMobileMenuOpen(false);
      return;
    }
  }, [navigate]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div className="flex min-h-screen bg-fufu-cream relative">
      {/* 桌面端侧边栏 */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      {/* 移动端毛玻璃侧边栏 */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <>
            <motion.div
              className="fixed inset-0 bg-black/20 z-40 md:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileMenuOpen(false)}
            />
            <motion.div
              className="fixed left-0 top-0 bottom-0 z-50 md:hidden"
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            >
              <div className="relative h-full">
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="absolute top-4 right-4 z-50 p-2 rounded-full bg-fufu-white/80 text-fufu-text-light hover:text-fufu-pink"
                >
                  <X size={22} />
                </button>
                <Sidebar />
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* 移动端汉堡按钮 */}
      <button
        onClick={() => setMobileMenuOpen(true)}
        className="md:hidden fixed top-4 left-4 z-30 p-3 rounded-fufu bg-fufu-white/90 shadow-fufu text-fufu-text-light hover:text-fufu-pink transition-colors"
      >
        <List size={24} />
      </button>

      <main ref={scrollRef} id="main-scroll" className="flex-1 overflow-y-auto relative pb-mobile-nav md:pb-0">
        <FloatingParticles />
        <ScrollRubberBand scrollContainerRef={scrollRef}>
          <motion.div
            className="max-w-4xl mx-auto px-4 sm:px-6 md:px-8 py-6 md:py-8 pt-16 sm:pt-20 md:pt-8 relative z-10"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
          >
            <Outlet />
          </motion.div>
        </ScrollRubberBand>

        {/* 左下角新闻轮播 */}
        <NewsTicker />

        {/* 移动端底部导航栏 */}
        <MobileNav />
      </main>
    </div>
  );
}
