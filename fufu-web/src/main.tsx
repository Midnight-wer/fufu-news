import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/index.css';
import ErrorBoundary from './components/common/ErrorBoundary';

const IS_STATIC_BUILD = import.meta.env.VITE_STATIC_MODE === 'true';

// ===== 本地全栈版：自动清理旧版/损坏的 localStorage 配置 =====
if (!IS_STATIC_BUILD) {
(function autoCleanupStorage() {
  const CLEANUP_VERSION = 1; // 递增此数字强制清理所有旧配置
  const CLEANUP_KEY = 'fufu-cleanup-version';

  try {
    const lastCleanup = parseInt(localStorage.getItem(CLEANUP_KEY) || '0', 10);

    if (lastCleanup < CLEANUP_VERSION) {
      console.log('[fufu] 🧹 检测到旧版配置，自动清理 localStorage...');

      // 列出所有需要检查/清理的 key
      const keysToCheck = [
        'fufu-settings', // 旧版 settings key (v1)
        'fufu-settings-v2', // 当前 settings key
        'fufu-token', // JWT token（保留，只清理损坏的）
        'fufu-search-history', // 搜索历史
        'fufu-sort', // 排序偏好
        'fufu-since', // 时间筛选
        'fufu-cat', // 分类筛选
        'fufu-poll-votes', // 投票记录
      ];

      let cleanedCount = 0;

      for (const key of keysToCheck) {
        try {
          const raw = localStorage.getItem(key);
          if (raw === null) continue; // key 不存在，跳过

          // 尝试解析 JSON key
          if (key.startsWith('fufu-settings')) {
            const parsed = JSON.parse(raw);
            // 验证数据结构完整性
            const settings = parsed?.state?.settings || parsed?.settings;
            if (!settings || typeof settings !== 'object') {
              // 数据结构损坏
              console.log(`[fufu]   🗑 清除损坏配置: ${key}`);
              localStorage.removeItem(key);
              cleanedCount++;
              continue;
            }
            // 验证必填字段
            if (settings.theme && !['miku', 'milktea', 'dark', 'light'].includes(settings.theme)) {
              console.log(`[fufu]   🔧 修复无效主题: ${key} (${settings.theme} → miku)`);
              settings.theme = 'miku';
              localStorage.setItem(key, JSON.stringify(parsed));
              cleanedCount++;
            }
          }
        } catch (e) {
          // JSON 解析失败 → 数据损坏，直接清除
          console.log(`[fufu]   🗑 清除损坏数据: ${key} (${(e as Error).message})`);
          localStorage.removeItem(key);
          cleanedCount++;
        }
      }

      // 写入清理版本标记
      localStorage.setItem(CLEANUP_KEY, String(CLEANUP_VERSION));

      if (cleanedCount > 0) {
        console.log(`[fufu] ✅ 已清理 ${cleanedCount} 项旧配置，正在刷新页面...`);
        // 延迟刷新，确保新配置写入
        setTimeout(() => window.location.reload(), 300);
        return; // 阻止后续渲染，等待刷新
      }

      console.log('[fufu] ✅ 配置检查完成，无需清理');
    }
  } catch (e) {
    // localStorage 完全不可用（隐私模式等），静默降级
    console.warn('[fufu] localStorage 不可用，跳过清理:', e);
  }
})();
}

async function bootstrap() {
  if (IS_STATIC_BUILD) {
    const { default: PublicApp } = await import('./public/PublicApp');
    ReactDOM.createRoot(document.getElementById('root')!).render(
      <React.StrictMode>
        <ErrorBoundary>
          <PublicApp />
        </ErrorBoundary>
      </React.StrictMode>,
    );
    return;
  }

  const [{ default: App }, { initThemeAndFontSize }] = await Promise.all([
    import('./App'),
    import('./stores/settingsStore'),
  ]);
  initThemeAndFontSize();
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </React.StrictMode>,
  );
}

void bootstrap();
