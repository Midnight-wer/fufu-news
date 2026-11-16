import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuthStore } from '../stores/authStore';

export default function LoginPage() {
  const [username, setUsername] = useState('fufu');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/articles', { replace: true });
    } catch (err: any) {
      setError(err?.response?.data?.detail || '登录失败，再试试看～');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-fufu-cream p-6">
      {/* 背景装饰 */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        {['🌸', '💕', '✨', '🎀', '💗'].map((emoji, i) => (
          <motion.span
            key={i}
            className="absolute text-3xl opacity-20"
            style={{ left: `${12 + i * 18}%`, top: `${15 + (i % 3) * 20}%` }}
            animate={{ y: [0, -30, 0], rotate: [0, 10, -10, 0] }}
            transition={{ duration: 4 + i, repeat: Infinity, ease: 'easeInOut', delay: i * 0.6 }}
          >
            {emoji}
          </motion.span>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="w-full max-w-md relative z-10"
      >
        {/* Logo */}
        <div className="text-center mb-10">
          <motion.p
            className="font-cute text-6xl mb-4"
            animate={{ y: [0, -10, 0] }}
            transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
          >
            🌸
          </motion.p>
          <h1 className="font-cute text-4xl text-fufu-pink tracking-wide">fufu新闻</h1>
          <p className="font-cute text-sm text-fufu-text-light mt-2">你的甜系阅读伙伴 💕</p>
        </div>

        {/* Form */}
        <motion.form
          onSubmit={handleSubmit}
          className="fufu-card p-8 space-y-5 rounded-fufu-card shadow-fufu-float"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.4 }}
        >
          <div>
            <label className="font-cute text-sm text-fufu-text-light block mb-1">用户名</label>
            <input
              className="fufu-input rounded-fufu-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="输入你的用户名～"
              autoComplete="username"
              required
            />
          </div>
          <div>
            <label className="font-cute text-sm text-fufu-text-light block mb-1">密码</label>
            <input
              className="fufu-input rounded-fufu-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="输入密码哦～"
              autoComplete="current-password"
              required
            />
          </div>

          {error && (
            <motion.p
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="font-body text-sm text-fufu-error bg-fufu-error-light/30 px-4 py-3 rounded-fufu"
            >
              😿 {error}
            </motion.p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="fufu-btn-primary w-full flex items-center justify-center gap-2 rounded-fufu-btn"
          >
            {loading ? (
              <>
                <span className="animate-spin text-lg">🌸</span> 登录中...
              </>
            ) : (
              '🌸 进入新闻花园'
            )}
          </button>

          <p className="text-center font-body text-xs text-fufu-text-muted">
            默认账户: fufu / fufu123
          </p>
        </motion.form>
      </motion.div>
    </div>
  );
}
