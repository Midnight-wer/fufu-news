import { SignOut, Sparkle, Wrench, Trash } from '@phosphor-icons/react';
import { useState } from 'react';
import { useAuthStore } from '../stores/authStore';
import { useSettingsStore, type ThemeMode } from '../stores/settingsStore';
import { useAIProcessAll, useAIHealthCheck } from '../hooks/useAI';
import AchievementList from '../components/achievements/AchievementList';

const themeOptions: { value: ThemeMode; label: string; emoji: string; desc: string; swatches: string[] }[] = [
  {
    value: 'miku',
    label: '初音未来',
    emoji: '🎵',
    desc: '青绿科技风·甜酷初音',
    swatches: ['#00e5ff', '#39c5bb', '#ffb6c1', '#F5FCFF', '#3A4A50'],
  },
  {
    value: 'milktea',
    label: '温柔奶咖',
    emoji: '🍂',
    desc: '暖棕拿铁风·温润治愈',
    swatches: ['#C4A77D', '#7BA05B', '#FFB5BA', '#FAF8F5', '#3D3530'],
  },
  {
    value: 'dark',
    label: '深色模式',
    emoji: '🌙',
    desc: '暗夜静谧·护眼舒适',
    swatches: ['#1A1C2E', '#00c8dc', '#ff96a0', '#2C2E48', '#D8E0E8'],
  },
];

export default function SettingsPage() {
  const logout = useAuthStore((s) => s.logout);
  const { settings, updateSettings } = useSettingsStore();
  const processAll = useAIProcessAll();
  const healthCheck = useAIHealthCheck();
  const [aiStatus, setAiStatus] = useState<{ ok: boolean; msg: string } | null>(null);

  const handleAiHealthCheck = async () => {
    setAiStatus(null);
    try {
      const result = await healthCheck.mutateAsync();
      setAiStatus(result.status === 'ok' ? { ok: true, msg: `AI 连接成功！模型: ${result.model}` } : { ok: false, msg: result.detail || '连接失败' });
    } catch {
      setAiStatus({ ok: false, msg: '无法连接到 AI 服务，请确认地址和模型名称正确～' });
    }
  };

  const handleClearData = () => {
    if (!window.confirm('确定要清除所有本地数据吗？\n\n这将删除你的设置、收藏列表和已读记录。此操作不可撤销！')) return;
    if (!window.confirm('真的要清除吗？再确认一次哦～')) return;
    localStorage.clear();
    window.location.reload();
  };

  return (
    <div>
      <div className="mb-8">
        <h2 className="font-cute text-3xl text-fufu-text">小设置</h2>
        <p className="font-body text-sm text-fufu-text-light mt-1">调一调，让fufu更懂你～</p>
      </div>

      <div className="space-y-6">
        {/* AI Settings */}
        <section className="fufu-card p-6">
          <h3 className="font-cute text-lg text-fufu-text mb-4">AI 小伙伴</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="font-cute text-sm text-fufu-text-light block mb-1">AI 后端</label>
              <select className="fufu-input" value={settings.aiBackend} onChange={(e) => updateSettings({ aiBackend: e.target.value as 'ollama' | 'openai' })}>
                <option value="ollama">Ollama（本地）</option>
                <option value="openai">OpenAI 兼容</option>
              </select>
            </div>
            <div>
              <label className="font-cute text-sm text-fufu-text-light block mb-1">模型名称</label>
              <input className="fufu-input" value={settings.aiModel} onChange={(e) => updateSettings({ aiModel: e.target.value })} placeholder="qwen2.5:7b" />
            </div>
            <div className="md:col-span-2">
              <label className="font-cute text-sm text-fufu-text-light block mb-1">API 地址</label>
              <input className="fufu-input" value={settings.aiBaseUrl} onChange={(e) => updateSettings({ aiBaseUrl: e.target.value })} placeholder="http://localhost:11434" />
            </div>
            <div>
              <label className="font-cute text-sm text-fufu-text-light block mb-1">API Key <span className="text-fufu-text-muted">(可选)</span></label>
              <input className="fufu-input" type="password" value={settings.aiApiKey} onChange={(e) => updateSettings({ aiApiKey: e.target.value })} placeholder="sk-... 留空则无需鉴权" />
            </div>
            <div className="md:col-span-2">
              <label className="font-cute text-sm text-fufu-text-light block mb-1">备选模型列表 <span className="text-fufu-text-muted">(每行一个)</span></label>
              <textarea className="fufu-input resize-none" rows={3} value={settings.aiModels} onChange={(e) => updateSettings({ aiModels: e.target.value })} placeholder="qwen2.5:7b&#10;llama3:8b" />
            </div>
          </div>
          <div className="mt-5 pt-4 border-t border-fufu-pink-soft/20 space-y-3">
            <button onClick={handleAiHealthCheck} disabled={healthCheck.isPending}
              className="flex items-center gap-2 px-5 py-3 rounded-fufu-btn font-cute text-sm bg-fufu-lavender/10 text-fufu-text-light hover:text-fufu-lavender hover:bg-fufu-lavender/20 transition-all">
              <Wrench size={18} className={healthCheck.isPending ? 'animate-spin' : ''} />
              {healthCheck.isPending ? '检测中...' : '测试 AI 连接'}
            </button>
            {aiStatus && (
              <p className={`font-body text-xs px-3 py-2 rounded-fufu ${aiStatus.ok ? 'bg-fufu-mint-light/40 text-fufu-mint' : 'bg-fufu-error-light/30 text-fufu-error'}`}>
                {aiStatus.ok ? ' ' : ' '}{aiStatus.msg}
              </p>
            )}
            <button
              onClick={() => processAll.mutate(50)} disabled={processAll.isPending}
              className="flex items-center gap-2 px-5 py-3 rounded-fufu-btn font-cute text-sm
                         bg-gradient-to-r from-fufu-lavender/20 to-fufu-pink/20 text-fufu-text-light hover:text-fufu-pink transition-all">
              <Sparkle size={18} className={processAll.isPending ? 'animate-spin' : ''} />
              {processAll.isPending ? 'AI 正在努力工作中...' : processAll.isSuccess ? `${(processAll.data as any)?.queued ?? '一些'} 篇文章已安排处理～` : '批量 AI 处理未标记文章'}
            </button>
          </div>
        </section>

        {/* Appearance — 三主题卡片选择器 */}
        <section className="fufu-card p-6">
          <h3 className="font-cute text-lg text-fufu-text mb-4">外观</h3>

          {/* 主题选择 */}
          <div className="mb-5">
            <label className="font-cute text-sm text-fufu-text-light block mb-3">主题风格</label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {themeOptions.map((opt) => {
                const isActive = settings.theme === opt.value;
                return (
                  <button
                    key={opt.value}
                    onClick={() => updateSettings({ theme: opt.value })}
                    className={`relative text-left p-4 rounded-fufu transition-all duration-200 border-2 cursor-pointer
                      ${isActive
                        ? 'border-fufu-teal bg-fufu-highlight/30 shadow-fufu'
                        : 'border-fufu-teal-soft/10 hover:border-fufu-teal/30 hover:shadow-fufu'
                      }`}
                  >
                    {/* 选中勾 */}
                    {isActive && (
                      <span className="absolute top-2 right-2 w-6 h-6 rounded-full bg-fufu-teal flex items-center justify-center text-white text-xs font-bold">
                        ✓
                      </span>
                    )}
                    {/* 色块预览 */}
                    <div className="flex gap-1 mb-3">
                      {opt.swatches.map((color, i) => (
                        <span
                          key={i}
                          className="w-7 h-7 rounded-full border border-white/30 shadow-sm"
                          style={{ backgroundColor: color }}
                          title={color}
                        />
                      ))}
                    </div>
                    {/* 标题与描述 */}
                    <p className="font-cute text-sm text-fufu-text">
                      {opt.emoji} {opt.label}
                    </p>
                    <p className="font-body text-xs text-fufu-text-muted mt-1">{opt.desc}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 字体大小 */}
          <div>
            <label className="font-cute text-sm text-fufu-text-light block mb-1">字体大小</label>
            <select className="fufu-input" value={settings.fontSize} onChange={(e) => updateSettings({ fontSize: e.target.value as 'small' | 'medium' | 'large' })}>
              <option value="small">小巧精致</option>
              <option value="medium">刚刚好</option>
              <option value="large">大大方方</option>
            </select>
          </div>
        </section>

        {/* Effects */}
        <section className="fufu-card p-6">
          <h3 className="font-cute text-lg text-fufu-text mb-4">特效设置</h3>
          <div className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <label className="font-cute text-sm text-fufu-text-light">特效强度</label>
              <span className="font-body text-xs text-fufu-pink font-medium">{settings.effectIntensity}%</span>
            </div>
            <input type="range" min="0" max="100" step="5" value={settings.effectIntensity}
              onChange={(e) => updateSettings({ effectIntensity: Number(e.target.value) })}
              className="w-full h-2 rounded-full appearance-none cursor-pointer accent-fufu-pink"
              style={{ background: `linear-gradient(to right, rgb(var(--fufu-teal)) ${settings.effectIntensity}%, rgba(var(--fufu-teal), 0.2) ${settings.effectIntensity}%)` }}
            />
            <div className="flex justify-between mt-1">
              <span className="font-body text-xs text-fufu-text-muted">极简</span>
              <span className="font-body text-xs text-fufu-text-muted">沉浸</span>
            </div>
          </div>
          <div className="space-y-3">
            {[
              { key: 'showSakura', emoji: '🌸', label: '樱花飘落特效' },
              { key: 'showCompanion', emoji: '💕', label: 'fufu 陪伴角色' },
              { key: 'showMouseTrail', emoji: '✨', label: '鼠标拖尾特效' },
            ].map(({ key, emoji, label }) => (
              <label key={key} className="flex items-center justify-between cursor-pointer">
                <span className="font-cute text-sm text-fufu-text">{emoji} {label}</span>
                <button role="switch" aria-checked={(settings as any)[key]}
                  onClick={() => updateSettings({ [key]: !(settings as any)[key] })}
                  className={`relative w-11 h-6 rounded-full transition-colors duration-300 ${(settings as any)[key] ? 'bg-fufu-pink' : 'bg-fufu-text-muted/20'}`}>
                  <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-fufu-white shadow transition-transform duration-300 ${(settings as any)[key] ? 'translate-x-5 left-0.5' : 'left-0.5'}`} />
                </button>
              </label>
            ))}
          </div>
        </section>

        {/* Achievements */}
        <section className="fufu-card p-6">
          <h3 className="font-cute text-lg text-fufu-text mb-4">成就</h3>
          <AchievementList />
        </section>

        {/* Account */}
        <section className="fufu-card p-6">
          <h3 className="font-cute text-lg text-fufu-text mb-4">账户</h3>
          <div className="space-y-3">
            <button onClick={logout}
              className="flex items-center gap-2 px-5 py-3 rounded-fufu-btn font-cute text-sm bg-fufu-error-light/20 text-fufu-error hover:bg-fufu-error-light/40 transition-all">
              <SignOut size={18} /> 退出登录
            </button>
            <button onClick={handleClearData}
              className="flex items-center gap-2 px-5 py-3 rounded-fufu-btn font-cute text-sm bg-fufu-soft-yellow/30 text-fufu-text-light hover:bg-fufu-soft-yellow/50 transition-all">
              <Trash size={18} /> 一键清除本地数据
            </button>
          </div>
        </section>

        {/* About */}
        <section className="text-center py-8">
          <p className="font-cute text-2xl text-fufu-pink">fufu新闻 </p>
          <p className="font-body text-sm text-fufu-text-muted mt-2">v1.0.0 . 你的甜系阅读伙伴 </p>
        </section>
      </div>
    </div>
  );
}
