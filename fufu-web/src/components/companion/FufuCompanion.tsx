import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { anim } from '@/config/animation';
import { useSettingsStore } from '@/stores/settingsStore';
import { useCompanionStore } from '@/stores/companionStore';
import SpeechBubble from './SpeechBubble';

const TIPS = [
  'こんにちは～今天也是元气满满的一天呢！🎵',
  '发现新文章啦！一起来看吧～ミクミク～',
  '已经收藏了好多呢～すごい！💿',
  '我会一直为你歌唱哦～🎤',
  '休息一下，听听新闻吧～🎶',
  '你真是个阅读小达人！✨',
  '来杯奶茶边喝边看吧～',
  '今天的新闻都好有趣！わくわく～',
];

interface FufuCompanionProps {
  onChatOpen?: () => void;
}

export default function FufuCompanion({ onChatOpen }: FufuCompanionProps) {
  const showCompanion = useSettingsStore((s) => s.settings.showCompanion);
  const intensity = useSettingsStore((s) => s.settings.effectIntensity);
  const { message, showMessage } = useCompanionStore();
  const [blinking, setBlinking] = useState(false);

  const factor = intensity / 100;
  const floatAmplitude = anim.companion.floatAmplitude * factor;
  const floatPeriod = anim.companion.floatPeriod;
  const baseSize = anim.companion.size + 20;

  // 眨眼动画
  useEffect(() => {
    const id = setInterval(() => {
      setBlinking(true);
      setTimeout(() => setBlinking(false), 100);
    }, 3500 + Math.random() * 2500);
    return () => clearInterval(id);
  }, []);

  const handleClick = useCallback(() => {
    if (onChatOpen) {
      onChatOpen();
    } else {
      const tip = TIPS[Math.floor(Math.random() * TIPS.length)];
      showMessage(tip);
    }
  }, [showMessage, onChatOpen]);

  if (!showCompanion) return null;

  return (
    <motion.div
      className="fixed right-4 bottom-4 z-[50] select-none cursor-pointer"
      style={{ width: baseSize, height: baseSize }}
      animate={{ y: [0, -floatAmplitude, 0] }}
      transition={{ y: { duration: floatPeriod, repeat: Infinity, ease: 'easeInOut' } }}
      onClick={handleClick}
      whileHover={{ scale: 1.08 }}
      whileTap={{ scale: 0.92 }}
    >
      <SpeechBubble message={message} />

      {/* 呼吸光晕（初音青绿） */}
      <motion.div
        className="absolute inset-0 rounded-full pointer-events-none"
        animate={{ scale: [1, 1.1, 1] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          background: 'radial-gradient(circle, rgba(0,229,255,0.22) 0%, rgba(57,197,187,0.10) 35%, rgba(255,182,193,0.06) 55%, transparent 70%)',
          filter: 'blur(14px)',
        }}
      />

      {/* 角色图片 */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="relative" style={{ width: baseSize * 0.88, height: baseSize * 0.88 }}>
          <img
            src="/fufu-mascot.png"
            alt="fufu"
            className="w-full h-full object-contain select-none"
            draggable={false}
          />
          {/* 眨眼遮罩 */}
          <div
            className="absolute top-0 left-0 w-full h-full rounded-full flex items-center justify-center pointer-events-none transition-opacity duration-75"
            style={{ opacity: blinking ? 1 : 0 }}
          >
            <div className="w-full h-[30%] bg-[#FFF5F0] rounded-full absolute top-[30%]" />
          </div>
        </div>
      </div>
    </motion.div>
  );
}
