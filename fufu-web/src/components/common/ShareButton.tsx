import { useState, useRef, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ShareNetwork,
  Link,
  ChatCircle,
  Globe,
  DeviceMobile,
  X,
} from '@phosphor-icons/react';
import { useCompanionStore } from '../../stores/companionStore';

interface ShareButtonProps {
  title: string;
  url?: string;
  description?: string;
  imageUrl?: string;
  className?: string;
}

interface ShareOption {
  key: string;
  label: string;
  icon: React.ReactNode;
  action: () => void;
  mobileOnly?: boolean;
  desktopOnly?: boolean;
}

/**
 * 生成 Weibo 分享链接
 */
function weiboShareUrl(title: string, url: string, pic?: string): string {
  const params = new URLSearchParams({
    url,
    title: `【${title}】`,
    appkey: '',
  });
  if (pic) params.set('pic', pic);
  return `https://service.weibo.com/share/share.php?${params.toString()}`;
}

/**
 * 生成 Twitter 分享链接
 */
function twitterShareUrl(text: string, url: string): string {
  const params = new URLSearchParams({ url, text });
  return `https://twitter.com/intent/tweet?${params.toString()}`;
}

/**
 * 检测是否支持 Native Share API
 */
function supportsNativeShare(): boolean {
  return typeof navigator !== 'undefined' && !!navigator.share;
}

/**
 * 检测是否为移动端（触摸设备）
 */
function isTouchDevice(): boolean {
  return (
    typeof window !== 'undefined' &&
    ('ontouchstart' in window || navigator.maxTouchPoints > 0)
  );
}

export default function ShareButton({
  title,
  url,
  description,
  imageUrl,
  className = '',
}: ShareButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const companion = useCompanionStore();

  const shareUrl = url || (typeof window !== 'undefined' ? window.location.href : '');
  const shareTitle = title;
  const shareDescription = description || '';
  const shareImage = imageUrl || '';

  // 点击外部关闭
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClick);
      return () => document.removeEventListener('mousedown', handleClick);
    }
  }, [isOpen]);

  // 复制链接
  const handleCopyLink = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      companion.setMood('happy');
      companion.showMessage('链接已复制～📋 快分享给小伙伴吧！');
      setTimeout(() => setCopied(false), 2000);
      setIsOpen(false);
    } catch {
      // 降级方案：使用传统方法
      const textarea = document.createElement('textarea');
      textarea.value = shareUrl;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      try {
        document.execCommand('copy');
        setCopied(true);
        companion.setMood('happy');
        companion.showMessage('链接已复制～📋');
        setTimeout(() => setCopied(false), 2000);
      } catch {
        companion.showMessage('复制失败了，请手动复制链接吧～😿');
      }
      document.body.removeChild(textarea);
      setIsOpen(false);
    }
  }, [shareUrl, companion]);

  // 微信分享（显示提示，微信没有直接的 URL scheme）
  const handleWechat = useCallback(() => {
    companion.showMessage('请截屏后分享到微信哦～💬 微信暂不支持直接分享链接');
    setIsOpen(false);
  }, [companion]);

  // 微博分享
  const handleWeibo = useCallback(() => {
    window.open(
      weiboShareUrl(shareTitle, shareUrl, shareImage),
      '_blank',
      'noopener,noreferrer'
    );
    setIsOpen(false);
  }, [shareTitle, shareUrl, shareImage]);

  // Twitter 分享
  const handleTwitter = useCallback(() => {
    window.open(
      twitterShareUrl(shareTitle, shareUrl),
      '_blank',
      'noopener,noreferrer'
    );
    setIsOpen(false);
  }, [shareTitle, shareUrl]);

  // Native Share API
  const handleNativeShare = useCallback(async () => {
    if (!supportsNativeShare()) return;
    try {
      await navigator.share({
        title: shareTitle,
        text: shareDescription || shareTitle,
        url: shareUrl,
      });
      companion.setMood('happy');
      companion.showMessage('分享成功～🎵');
    } catch (err) {
      // 用户取消分享不算错误
      if ((err as DOMException)?.name !== 'AbortError') {
        companion.showMessage('分享出了点小问题呢～😿');
      }
    }
    setIsOpen(false);
  }, [shareTitle, shareDescription, shareUrl, companion]);

  // 构建分享选项
  const shareOptions: ShareOption[] = [
    {
      key: 'copy',
      label: copied ? '已复制!' : '复制链接',
      icon: copied ? (
        <span className="text-fufu-mint text-sm">✓</span>
      ) : (
        <Link size={18} />
      ),
      action: handleCopyLink,
    },
    {
      key: 'wechat',
      label: '分享到微信',
      icon: <ChatCircle size={18} />,
      action: handleWechat,
    },
    {
      key: 'weibo',
      label: '分享到微博',
      icon: <Globe size={18} />,
      action: handleWeibo,
    },
    {
      key: 'twitter',
      label: '分享到 Twitter',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
        </svg>
      ),
      action: handleTwitter,
    },
  ];

  // 移动端原生分享
  if (supportsNativeShare() && isTouchDevice()) {
    shareOptions.push({
      key: 'native',
      label: '分享到...',
      icon: <DeviceMobile size={18} />,
      action: handleNativeShare,
    });
  }

  return (
    <div className={`relative inline-flex ${className}`}>
      <button
        ref={buttonRef}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsOpen(!isOpen);
        }}
        className={`flex items-center gap-2 px-4 py-2 rounded-fufu-btn font-cute text-sm transition-all ${
          isOpen
            ? 'bg-fufu-teal/10 text-fufu-teal-deep border border-fufu-teal/20'
            : 'bg-fufu-cream text-fufu-text-light hover:text-fufu-teal-deep hover:bg-fufu-teal-soft/20'
        }`}
        title="分享"
      >
        <ShareNetwork size={18} weight={isOpen ? 'fill' : 'regular'} />
        分享
      </button>

      {/* 弹出菜单 */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop for mobile */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 md:hidden"
              onClick={() => setIsOpen(false)}
            />

            <motion.div
              ref={popoverRef}
              initial={{ opacity: 0, y: -6, scale: 0.96 }}
              animate={{ opacity: 1, y: 4, scale: 1 }}
              exit={{ opacity: 0, y: -6, scale: 0.96 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              className="absolute top-full left-0 mt-1 z-50 bg-white rounded-fufu-modal shadow-fufu-float border border-fufu-highlight/30 p-1.5 min-w-[200px]"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-3 py-1.5">
                <span className="font-cute text-xs text-fufu-text-muted flex items-center gap-1.5">
                  📤 分享这篇文章
                </span>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1 rounded-full text-fufu-text-muted hover:text-fufu-text hover:bg-fufu-cream transition-colors"
                >
                  <X size={14} />
                </button>
              </div>

              <div className="my-1 border-t border-fufu-highlight/20" />

              {/* Share options */}
              {shareOptions.map((opt) => (
                <button
                  key={opt.key}
                  onClick={opt.action}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-fufu text-sm font-body transition-colors text-left ${
                    opt.key === 'copy' && copied
                      ? 'text-fufu-mint bg-fufu-mint-light/10'
                      : 'text-fufu-text hover:bg-fufu-cream'
                  }`}
                >
                  <span
                    className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
                      opt.key === 'wechat'
                        ? 'bg-green-50 text-green-500'
                        : opt.key === 'weibo'
                          ? 'bg-red-50 text-red-500'
                          : opt.key === 'twitter'
                            ? 'bg-blue-50 text-blue-500'
                            : opt.key === 'native'
                              ? 'bg-fufu-teal-soft/30 text-fufu-teal-deep'
                              : 'bg-fufu-cream text-fufu-text-light'
                    }`}
                  >
                    {opt.icon}
                  </span>
                  <span>{opt.label}</span>
                </button>
              ))}

              {/* 底部提示 */}
              <div className="px-3 py-1.5 mt-1 border-t border-fufu-highlight/20">
                <p className="font-body text-[10px] text-fufu-text-muted">
                  💕 和朋友们一起分享好内容吧～
                </p>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
