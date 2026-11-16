import { motion, AnimatePresence } from 'framer-motion';

interface SpeechBubbleProps {
  message: string | null;
}

export default function SpeechBubble({ message }: SpeechBubbleProps) {
  return (
    <AnimatePresence>
      {message && (
        <motion.div
          className="absolute bottom-full mb-3 left-1/2 -translate-x-1/2"
          initial={{ opacity: 0, y: 8, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -4, scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 300, damping: 25 }}
        >
          <div
            className="bg-white/95 backdrop-blur-sm text-fufu-warm-gray text-xs font-body
                        px-4 py-2.5 rounded-2xl shadow-lg border border-fufu-pink-soft/30
                        whitespace-nowrap max-w-[200px] text-center"
          >
            {message}
          </div>
          <div
            className="absolute left-1/2 -translate-x-1/2 top-full -mt-1
                          w-0 h-0 border-[6px] border-transparent
                          border-t-white/95"
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
