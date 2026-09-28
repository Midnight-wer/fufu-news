import { useState, useCallback, useRef } from 'react';
import { Play, Pause, Stop } from '@phosphor-icons/react';

interface TTSReaderProps {
  content: string;
  title: string;
}

export default function TTSReader({ content, title }: TTSReaderProps) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  const stripHtml = (html: string) => {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    return (doc.body.textContent || '').replace(/\s+/g, ' ').trim();
  };

  const speak = useCallback(() => {
    const synth = window.speechSynthesis;

    if (isPaused) {
      synth.resume();
      setIsPaused(false);
      setIsSpeaking(true);
      return;
    }

    synth.cancel();

    const text = stripHtml(content);
    const fullText = `${title}。${text}`;
    const utterance = new SpeechSynthesisUtterance(fullText);
    utterance.lang = 'zh-CN';
    utterance.rate = 0.9;
    utterance.pitch = 1.1;

    // try to find a Chinese voice
    const voices = synth.getVoices();
    const zhVoice = voices.find((v) => v.lang.startsWith('zh'));
    if (zhVoice) utterance.voice = zhVoice;

    utterance.onend = () => {
      setIsSpeaking(false);
      setIsPaused(false);
    };
    utterance.onerror = () => {
      setIsSpeaking(false);
      setIsPaused(false);
    };

    utteranceRef.current = utterance;
    synth.speak(utterance);
    setIsSpeaking(true);
    setIsPaused(false);
  }, [content, title, isPaused]);

  const pause = () => {
    window.speechSynthesis.pause();
    setIsPaused(true);
    setIsSpeaking(true);
  };

  const stop = () => {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
    setIsPaused(false);
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={isSpeaking && !isPaused ? pause : speak}
        className="flex items-center gap-2 px-4 py-2 rounded-fufu font-cute text-sm
                   bg-gradient-to-r from-fufu-soft-purple/40 to-fufu-pink-soft/40
                   text-fufu-warm-gray/60 hover:text-fufu-peach transition-all"
      >
        {isSpeaking && !isPaused ? (
          <>
            <span className="flex items-center gap-0.5">
              <span className="w-1 h-4 bg-fufu-peach/60 rounded-full animate-pulse" />
              <span className="w-1 h-3 bg-fufu-peach/40 rounded-full animate-pulse" style={{ animationDelay: '0.15s' }} />
              <span className="w-1 h-5 bg-fufu-peach/50 rounded-full animate-pulse" style={{ animationDelay: '0.3s' }} />
            </span>
            正在读...
          </>
        ) : isPaused ? (
          <>
            <Play size={16} />
            继续读
          </>
        ) : (
          <>
            <Play size={16} />
            念给我听 📖
          </>
        )}
      </button>
      {isSpeaking && (
        <button
          onClick={stop}
          className="p-2 rounded-full text-fufu-warm-gray/30 hover:text-red-400 hover:bg-red-50 transition-all"
        >
          <Stop size={18} />
        </button>
      )}
    </div>
  );
}
