import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, PaperPlaneRight, Copy, Trash } from '@phosphor-icons/react';
import { useSettingsStore } from '@/stores/settingsStore';
import { useCompanionStore } from '@/stores/companionStore';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  _streaming?: boolean;
}

const CHAT_KEY = 'fufu-chat-history-v2';

function loadHistory(): Message[] {
  try {
    return JSON.parse(localStorage.getItem(CHAT_KEY) || '[]');
  } catch {
    return [];
  }
}
function saveHistory(msgs: Message[]) {
  // 不保存正在流式输出的消息
  const clean = msgs.filter((m) => !m._streaming);
  localStorage.setItem(CHAT_KEY, JSON.stringify(clean.slice(-60)));
}

const QUICK_REPLIES = [
  { icon: '😂', label: '讲个段子', prompt: '讲一个可爱的冷笑话给我听～' },
  { icon: '📰', label: '推荐新闻', prompt: '最近有什么有趣的热点新闻呀？给我推荐几条吧！' },
  { icon: '✍️', label: '帮我写文案', prompt: '帮我写一段可爱风格的朋友圈文案，今天的天气很好～' },
  { icon: '🎬', label: '推荐动漫', prompt: '推荐几部好看的动漫给我吧，要甜甜的那种～' },
  { icon: '💡', label: '科普一下', prompt: '给我科普一个有趣的冷知识吧！' },
  { icon: '🌸', label: '夸夸我', prompt: '快夸夸我呀，我今天有点小沮丧呢...' },
];

export default function AiChatDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const settings = useSettingsStore((s) => s.settings);
  const companion = useCompanionStore();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState('');
  const [streamingId, setStreamingId] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // 打开时加载历史
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 200);
      const hist = loadHistory();
      setMessages(
        hist.length > 0
          ? hist
          : [
              {
                role: 'assistant',
                content:
                  'こんにちは～欢迎来到 fufu 的聊天室！🎤\n有什么想聊的都可以跟我说哦，ミク会一直在这里陪着你呢～💿',
              },
            ],
      );
    }
  }, [open]);

  // 滚动到底部
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  /*
   * 持久化聊天记录。
   * 之前 saveHistory() 是写在 setMessages(prev => ...) 的 updater 里的 ——
   * updater 必须是纯函数，React 在 StrictMode 下会故意调用两次，
   * 于是同一份历史被重复写盘；更糟的是 updater 里还塞了 setInput / setTimeout，
   * 属于典型的"在渲染阶段触发副作用"。统一挪到这个 effect 里，幂等且可控。
   */
  useEffect(() => {
    if (messages.length > 0) saveHistory(messages);
  }, [messages]);

  // 关闭弹窗时掐断还在跑的流式请求（之前只有卸载才 abort，
  // 关掉窗口后请求仍在后台跑完并 setState，白白消耗一个对话轮次）
  useEffect(() => {
    if (!open) abortRef.current?.abort();
  }, [open]);

  // 卸载时清理
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const send = useCallback(
    async (text?: string) => {
      const content = (text || input).trim();
      if (!content || loading) return;
      setInput('');
      setError('');

      const userMsg: Message = { role: 'user', content };
      const newMsgs = [...messages, userMsg];
      setMessages(newMsgs);

      // 添加占位 assistant 消息用于流式输出
      const placeholderIdx = newMsgs.length;
      const placeholder: Message = { role: 'assistant', content: '', _streaming: true };
      setMessages([...newMsgs, placeholder]);
      setLoading(true);
      setConnecting(true);
      setStreamingId(placeholderIdx);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const baseUrl = settings.aiBaseUrl || 'http://localhost:11434';
        const model = settings.aiModel || 'deepseek-v4-pro';
        const token = localStorage.getItem('fufu-token') || '';

        const resp = await fetch('/api/v1/ai/chat/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: token ? `Bearer ${token}` : '',
          },
          body: JSON.stringify({
            messages: newMsgs.map((m) => ({ role: m.role, content: m.content })),
            model,
            base_url: baseUrl,
            api_key: settings.aiApiKey || undefined,
          }),
          signal: controller.signal,
        });

        if (!resp.ok) {
          const errText = await resp.text();
          throw new Error(errText || `请求失败 (${resp.status})`);
        }

        const reader = resp.body?.getReader();
        if (!reader) throw new Error('浏览器不支持流式读取');

        const decoder = new TextDecoder();
        let fullContent = '';
        let buffer = '';

        // eslint-disable-next-line no-constant-condition -- 流式读取本来就是读到 done 才停
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const dataStr = line.slice(6);
            if (dataStr === '[DONE]') break;

            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.error) {
                throw new Error(parsed.error);
              }
              if (parsed.content) {
                if (connecting) setConnecting(false);
                fullContent += parsed.content;
                // 更新消息
                setMessages((prev) => {
                  const updated = [...prev];
                  if (updated[placeholderIdx]) {
                    updated[placeholderIdx] = { ...updated[placeholderIdx], content: fullContent };
                  }
                  return updated;
                });
              }
            } catch (e: any) {
              if (e.message && !e.message.includes('JSON')) throw e;
            }
          }
        }

        // 流结束，标记为非 streaming（写盘交给上面的 effect，这里保持 updater 纯净）
        const finalContent = fullContent || '（fufu 好像走神了呢...再说一次嘛～）';
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[placeholderIdx]) {
            updated[placeholderIdx] = { role: 'assistant', content: finalContent };
          }
          return updated;
        });

        companion.setMood('happy');
        companion.showMessage('fufu 回复你啦～快来看看！💕');
      } catch (err: any) {
        if (err.name === 'AbortError') return;
        const detail = err?.message || '连接失败，再试一次嘛～';
        setError(detail);
        // 移除占位消息
        setMessages((prev) => prev.filter((_, i) => i !== placeholderIdx));
      } finally {
        setLoading(false);
        setConnecting(false);
        setStreamingId(null);
        abortRef.current = null;
      }
    },
    [input, loading, messages, settings, companion],
  );

  const clearHistory = () => {
    setMessages([
      {
        role: 'assistant',
        content: '聊天记录已清空啦～现在是一片崭新的小天地哦！🎵\n想和ミク聊点什么呀？',
      },
    ]);
    localStorage.removeItem(CHAT_KEY);
  };

  const copyMessage = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
    companion.showMessage('已复制到剪贴板～📋');
  };

  const handleQuickReply = (prompt: string) => {
    send(prompt);
  };

  const handleRetry = () => {
    setError('');
    // 重试：移除最后的 assistant 消息（如果是错误导致的占位），重新发送
    setMessages((prev) => {
      const lastUserIdx = prev.map((m) => m.role).lastIndexOf('user');
      if (lastUserIdx < 0) return prev;
      const userMsg = prev[lastUserIdx];
      const trimmed = prev.slice(0, lastUserIdx);
      setInput('');
      // 用 setTimeout 确保 state 更新后再发送
      setTimeout(() => send(userMsg.content), 50);
      return trimmed;
    });
  };

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-[300] flex items-end md:items-center justify-center pointer-events-none"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        {/* 遮罩 */}
        <div className="absolute inset-0 bg-black/20 pointer-events-auto" onClick={onClose} />

        {/* 对话面板 */}
        <motion.div
          className="relative pointer-events-auto w-full md:max-w-lg md:mx-4 h-[580px] max-h-[90vh]
                     bg-white rounded-t-fufu-card md:rounded-fufu-card shadow-fufu-float
                     flex flex-col overflow-hidden border border-fufu-pink/20"
          initial={{ y: '100%', opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: '100%', opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between px-5 py-4 border-b border-fufu-teal-soft/30 shrink-0"
            style={{
              background:
                'linear-gradient(135deg, rgb(var(--fufu-teal-soft)), rgb(var(--fufu-highlight)))',
            }}
          >
            <div className="flex items-center gap-3">
              <div
                className="w-9 h-9 rounded-full flex items-center justify-center text-lg shrink-0"
                style={{
                  background:
                    'linear-gradient(135deg, rgb(var(--fufu-teal)), rgb(var(--fufu-teal-deep)))',
                }}
              >
                🎤
              </div>
              <div>
                <p className="font-cute text-sm text-fufu-text">fufu AI 聊天</p>
                <p className="font-body text-[10px] text-fufu-text-muted">
                  {connecting
                    ? '🔗 正在连接 AI 服务...'
                    : loading
                      ? '💭 正在输出中...'
                      : '你的虚拟歌姬聊天伙伴～'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={clearHistory}
                className="p-2 rounded-full hover:bg-fufu-pink-soft/30 text-fufu-text-muted hover:text-fufu-error transition-colors"
                title="清空聊天记录"
              >
                <Trash size={16} />
              </button>
              <button
                onClick={onClose}
                className="p-2 rounded-full hover:bg-fufu-pink-soft/30 text-fufu-text-muted hover:text-fufu-pink transition-colors"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {messages.length <= 1 && messages[0]?.role === 'assistant' && (
              <div className="text-center py-8">
                <p className="text-4xl mb-3 animate-float">🌸</p>
                <p className="font-cute text-sm text-fufu-text-muted">和 fufu 聊聊天吧～</p>
                <p className="font-body text-xs text-fufu-text-muted mt-1">
                  可以问新闻、聊动漫、讲段子！
                </p>
              </div>
            )}

            <AnimatePresence>
              {messages.map((m, i) => (
                <motion.div
                  key={i}
                  className={`flex gap-2.5 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  initial={{ opacity: 0, y: 10, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.25 }}
                >
                  {/* AI 头像 */}
                  {m.role === 'assistant' && (
                    <div
                      className="w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 mt-0.5"
                      style={{
                        background:
                          'linear-gradient(135deg, rgb(var(--fufu-teal-soft)), rgb(var(--fufu-highlight)))',
                      }}
                    >
                      🎤
                    </div>
                  )}

                  {/* 气泡 */}
                  <div className="flex flex-col max-w-[75%]">
                    <div
                      className={`px-4 py-3 font-body text-sm leading-relaxed ${
                        m.role === 'user'
                          ? 'text-white rounded-fufu-bubble rounded-br-md'
                          : 'text-fufu-text bg-fufu-highlight rounded-fufu-bubble rounded-bl-md border border-fufu-teal/10'
                      }`}
                      style={
                        m.role === 'user'
                          ? {
                              background:
                                'linear-gradient(135deg, rgb(var(--fufu-teal)), rgb(var(--fufu-teal-deep)))',
                            }
                          : {}
                      }
                    >
                      {/* 内容 */}
                      <div className="whitespace-pre-wrap break-words">
                        {m.content}
                        {m._streaming && (
                          <span className="inline-block w-1.5 h-4 bg-fufu-pink ml-0.5 animate-pulse align-text-bottom rounded-sm" />
                        )}
                      </div>

                      {/* 操作按钮 */}
                      {m.role === 'assistant' && !m._streaming && m.content && (
                        <button
                          onClick={() => copyMessage(m.content)}
                          className="mt-2 text-fufu-text-muted hover:text-fufu-pink transition-colors inline-flex items-center gap-1"
                        >
                          <Copy size={12} />
                          <span className="text-[10px]">复制</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* 用户头像 */}
                  {m.role === 'user' && (
                    <div
                      className="w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 mt-0.5"
                      style={{ background: 'linear-gradient(135deg, #ffb6c1, #ffd0d9)' }}
                    >
                      🎀
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {/* 错误提示 */}
            <AnimatePresence>
              {error && (
                <motion.div
                  className="text-center px-4 py-3 rounded-fufu-card bg-fufu-error-light/30 text-fufu-error font-body text-xs"
                  initial={{ x: -5, opacity: 0 }}
                  animate={{ x: [0, 5, -5, 0], opacity: 1 }}
                  transition={{ duration: 0.3 }}
                >
                  <p className="mb-2">😿 {error}</p>
                  <button
                    onClick={handleRetry}
                    className="px-3 py-1 rounded-fufu-btn bg-white text-fufu-pink font-cute text-xs hover:bg-fufu-pink-soft/20 transition-all"
                  >
                    重新发送 🔄
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* 快捷回复 */}
          {!loading && messages.length <= 2 && (
            <div className="px-4 pb-2 shrink-0">
              <p className="font-cute text-[10px] text-fufu-text-muted mb-2">💬 快捷回复：</p>
              <div className="flex flex-wrap gap-1.5">
                {QUICK_REPLIES.slice(0, 4).map((qr) => (
                  <button
                    key={qr.label}
                    onClick={() => handleQuickReply(qr.prompt)}
                    className="px-3 py-1.5 rounded-fufu-btn font-cute text-xs bg-fufu-teal-soft/20 text-fufu-text-light hover:bg-fufu-teal-soft/40 hover:text-fufu-teal-deep transition-all border border-fufu-teal/10"
                  >
                    {qr.icon} {qr.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 输入框 */}
          <div className="px-4 py-3 border-t border-fufu-teal-soft/30 shrink-0 bg-fufu-cream">
            <div className="flex gap-2">
              <input
                ref={inputRef}
                className="flex-1 fufu-input rounded-fufu-input py-2.5 text-sm font-body"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                placeholder={
                  connecting
                    ? 'ミク正在努力连接中...'
                    : loading
                      ? 'ミク正在回复中...'
                      : '和ミク聊聊吧～'
                }
                disabled={loading}
              />
              <button
                onClick={() => {
                  if (loading) {
                    abortRef.current?.abort();
                  } else {
                    send();
                  }
                }}
                disabled={!loading && !input.trim()}
                className="p-2.5 rounded-fufu-btn text-white disabled:opacity-40 transition-all shrink-0 hover:scale-105 active:scale-95"
                style={{
                  background: loading
                    ? 'linear-gradient(135deg, #ff6b6b, #ff8787)'
                    : 'linear-gradient(135deg, rgb(var(--fufu-teal)), rgb(var(--fufu-teal-deep)))',
                }}
                title={loading ? '停止生成' : '发送'}
              >
                {loading ? <X size={20} /> : <PaperPlaneRight size={20} />}
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
