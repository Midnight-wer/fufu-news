import { motion, AnimatePresence } from 'framer-motion';
import { Sparkle } from '@phosphor-icons/react';
import { useAchievementStore } from '@/stores/achievementStore';

export default function AchievementToast() {
  const toasts = useAchievementStore((s) => s.toasts);

  return (
    <div className="fixed top-6 right-6 z-[200] flex flex-col gap-3 pointer-events-none">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.key}
            className="pointer-events-auto flex items-start gap-3 bg-white/95 backdrop-blur-sm
                       rounded-fufu-toast shadow-fufu-float border border-fufu-pink/20
                       px-5 py-4 min-w-[260px] max-w-[320px]"
            initial={{ opacity: 0, x: 80, scale: 0.9 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 40, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
          >
            <div className="flex items-center justify-center w-10 h-10 rounded-full bg-gradient-to-br from-fufu-pink to-fufu-peach text-xl shrink-0">
              {toast.icon}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <Sparkle size={12} className="text-fufu-pink" weight="fill" />
                <p className="font-cute text-sm text-fufu-text">成就解锁！</p>
              </div>
              <p className="font-cute text-base text-fufu-pink mt-0.5">{toast.title}</p>
              <p className="font-body text-xs text-fufu-text-light mt-0.5">{toast.description}</p>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
