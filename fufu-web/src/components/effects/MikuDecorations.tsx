import { motion } from 'framer-motion';

/** 初音未来 Q 版装饰元素 — SVG 音符、耳机、话筒、星芒 */
export default function MikuDecorations() {
  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden" style={{ zIndex: 0 }}>
      {/* 左上音符群 */}
      <motion.div
        className="absolute top-20 left-8"
        animate={{ y: [0, -8, 0], rotate: [0, 5, 0] }}
        transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
      >
        <svg width="40" height="50" viewBox="0 0 40 50" fill="none" opacity="0.15">
          <circle cx="12" cy="38" r="4" fill="#00e5ff" />
          <rect x="14" y="10" width="3" height="28" rx="1.5" fill="#00e5ff" />
          <path d="M17 12 Q25 8 30 14" stroke="#00e5ff" strokeWidth="2" fill="none" />
          <circle cx="32" cy="16" r="3" fill="#ffb6c1" />
          <rect x="14" y="28" width="18" height="2" rx="1" fill="#39c5bb" />
        </svg>
      </motion.div>

      {/* 右上耳机 */}
      <motion.div
        className="absolute top-16 right-16"
        animate={{ y: [0, -6, 0] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
      >
        <svg width="50" height="44" viewBox="0 0 50 44" fill="none" opacity="0.13">
          <path d="M5 22 A22 22 0 0 1 45 22" stroke="#00e5ff" strokeWidth="3" fill="none" />
          <rect x="2" y="22" width="12" height="18" rx="5" fill="#39c5bb" />
          <rect x="36" y="22" width="12" height="18" rx="5" fill="#39c5bb" />
          <rect x="6" y="26" width="4" height="10" rx="2" fill="#ffb6c1" opacity="0.5" />
          <rect x="40" y="26" width="4" height="10" rx="2" fill="#ffb6c1" opacity="0.5" />
        </svg>
      </motion.div>

      {/* 底部初音剪影 */}
      <motion.div
        className="absolute bottom-8 left-[5%]"
        animate={{ y: [0, -10, 0], rotate: [-2, 2, -2] }}
        transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
      >
        <svg width="64" height="64" viewBox="0 0 64 64" fill="none" opacity="0.1">
          {/* 双马尾 */}
          <ellipse cx="20" cy="22" rx="14" ry="28" fill="#00e5ff" transform="rotate(-15 20 22)" />
          <ellipse cx="44" cy="22" rx="14" ry="28" fill="#00e5ff" transform="rotate(15 44 22)" />
          {/* 脸 */}
          <circle cx="32" cy="28" r="14" fill="#ffb6c1" />
          {/* 刘海 */}
          <path d="M18 26 Q26 14 32 14 Q38 14 46 26" stroke="#00e5ff" strokeWidth="2" fill="none" />
          {/* 眼睛 */}
          <circle cx="27" cy="28" r="2.5" fill="#3A4A50" />
          <circle cx="37" cy="28" r="2.5" fill="#3A4A50" />
          {/* 微笑 */}
          <path d="M28 34 Q32 38 36 34" stroke="#3A4A50" strokeWidth="1.5" fill="none" />
          {/* 耳机 */}
          <rect x="14" y="22" width="6" height="10" rx="3" fill="#39c5bb" />
          <rect x="44" y="22" width="6" height="10" rx="3" fill="#39c5bb" />
          <path d="M20 26 Q32 18 44 26" stroke="#39c5bb" strokeWidth="1.5" fill="none" />
        </svg>
      </motion.div>

      {/* 右下角星芒 */}
      <motion.div
        className="absolute bottom-12 right-10"
        animate={{ rotate: [0, 15, 0], scale: [1, 1.15, 1] }}
        transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut', delay: 0.5 }}
      >
        <svg width="36" height="36" viewBox="0 0 36 36" opacity="0.12">
          <path d="M18 2 L21 14 L33 14 L23 22 L27 34 L18 26 L9 34 L13 22 L3 14 L15 14 Z"
                fill="#00e5ff" />
        </svg>
      </motion.div>

      {/* 右侧中间音符 */}
      <motion.div
        className="absolute top-[45%] right-6"
        animate={{ y: [0, 12, 0], rotate: [0, -8, 0] }}
        transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
      >
        <span className="text-3xl music-note" style={{ color: '#00e5ff', opacity: 0.2 }}>♪</span>
      </motion.div>

      {/* 左下话筒 */}
      <motion.div
        className="absolute bottom-[25%] left-6"
        animate={{ scale: [1, 1.08, 1] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut', delay: 1.5 }}
      >
        <svg width="32" height="48" viewBox="0 0 32 48" fill="none" opacity="0.12">
          <rect x="10" y="2" width="12" height="22" rx="6" fill="#00e5ff" />
          <path d="M6 22 Q16 38 26 22" stroke="#39c5bb" strokeWidth="3" fill="none" />
          <rect x="14" y="28" width="4" height="16" rx="2" fill="#ffb6c1" />
        </svg>
      </motion.div>

      {/* 分散小音符 */}
      {[
        { left: '15%', top: '35%', delay: 0 },
        { left: '72%', top: '25%', delay: 1.2 },
        { left: '8%', top: '70%', delay: 2.4 },
        { left: '60%', top: '75%', delay: 0.8 },
        { left: '35%', top: '85%', delay: 1.8 },
      ].map((pos, i) => (
        <motion.span
          key={i}
          className="absolute text-lg font-serif"
          style={{ left: pos.left, top: pos.top, color: i % 2 === 0 ? '#00e5ff' : '#ffb6c1', opacity: 0.12 }}
          animate={{ y: [0, -14, 0], rotate: [0, (i % 2 === 0 ? 8 : -8), 0] }}
          transition={{ duration: 4 + i * 0.4, repeat: Infinity, ease: 'easeInOut', delay: pos.delay }}
        >
          {['♬', '♫', '♪', '♩', '🎵'][i]}
        </motion.span>
      ))}
    </div>
  );
}
