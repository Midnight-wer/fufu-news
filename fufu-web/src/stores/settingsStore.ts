import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ================================================================
// fufu新闻 — settingsStore v4
// 策略：任何异常直接丢弃旧数据，返回默认 miku 配置
// ================================================================

export type ThemeMode = 'miku' | 'milktea' | 'dark';

/** 支持的 AI 后端标识（与设置页的预设表保持一致） */
export type AiBackendKey = 'deepseek' | 'openai' | 'moonshot' | 'ollama';

const AI_BACKEND_KEYS: readonly AiBackendKey[] = ['deepseek', 'openai', 'moonshot', 'ollama'];

function isAiBackendKey(v: unknown): v is AiBackendKey {
  return typeof v === 'string' && (AI_BACKEND_KEYS as readonly string[]).includes(v);
}

export interface Settings {
  aiBackend: AiBackendKey;
  aiModel: string;
  aiBaseUrl: string;
  aiApiKey: string;
  aiModels: string;
  theme: ThemeMode;
  fontSize: 'small' | 'medium' | 'large';
  effectIntensity: number;
  showCompanion: boolean;
  showMouseTrail: boolean;
  showSakura: boolean;
}

interface SettingsState {
  settings: Settings;
  updateSettings: (partial: Partial<Settings>) => void;
}

// ================================================================
const DEFAULTS: Settings = {
  aiBackend: 'deepseek',
  aiModel: 'deepseek-v4-pro',
  aiBaseUrl: 'https://api.deepseek.com/v1/chat/completions',
  aiApiKey: '',
  aiModels: 'deepseek-v4-pro\ndeepseek-chat\ndeepseek-reasoner',
  theme: 'miku',
  fontSize: 'medium',
  effectIntensity: 75,
  showCompanion: true,
  showMouseTrail: true,
  showSakura: true,
};

const VALID_THEMES: readonly string[] = ['miku', 'milktea', 'dark'];
const VALID_FONT_SIZES: readonly string[] = ['small', 'medium', 'large'];
const STORAGE_KEY = 'fufu-settings-v2';
const CURRENT_VERSION = 4;

// ================================================================
// L0: localStorage 安全原语（永不抛异常）
// ================================================================
function _lsGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function _lsDel(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    /* 静默 */
  }
}

// ================================================================
// L1: _isValidTheme —— 访问 .length 前强制判断变量存在且为字符串
// ================================================================

/**
 * 校验 theme 值是否有效。
 *
 * 校验顺序（杜绝 undefined.length）：
 *   ① v === null || v === undefined  → false  （变量存在性检查）
 *   ② typeof v !== 'string'          → false  （类型检查）
 *   ③ v.length === 0                 → false  （长度检查）
 *   ④ VALID_THEMES.includes(v)       → 白名单
 */
function _isValidTheme(v: unknown): v is ThemeMode {
  if (v === null || v === undefined) return false;
  if (typeof v !== 'string') return false;
  if (v.length === 0) return false;
  return VALID_THEMES.includes(v);
}

function _isValidFontSize(v: unknown): v is string {
  if (v === null || v === undefined) return false;
  if (typeof v !== 'string') return false;
  if (v.length === 0) return false;
  return VALID_FONT_SIZES.includes(v);
}

function _isNonEmptyStr(v: unknown): v is string {
  if (v === null || v === undefined) return false;
  return typeof v === 'string' && v.length > 0;
}

function _isStr(v: unknown): v is string {
  if (v === null || v === undefined) return false;
  return typeof v === 'string';
}

function _isValidNum(v: unknown): v is number {
  if (v === null || v === undefined) return false;
  return typeof v === 'number' && !isNaN(v) && isFinite(v);
}

function _isBool(v: unknown): v is boolean {
  if (v === null || v === undefined) return false;
  return typeof v === 'boolean';
}

// ================================================================
// L2: _stripUndefined —— 过滤旧存储 undefined 字段
// ================================================================

/**
 * 移除对象中所有值为 undefined 的键。
 *
 * 旧数据 { aiModels: undefined, theme: 'miku' }
 *   → 过滤后 { theme: 'miku' }
 *
 * 空值防护：
 *   obj === null      → {}
 *   obj === undefined → {}
 *   typeof !== 'object' → {}
 */
function _stripUndefined(obj: unknown): Record<string, unknown> {
  if (obj === null || obj === undefined) return {};
  if (typeof obj !== 'object' || Array.isArray(obj)) return {};

  const out: Record<string, unknown> = {};
  const keys = Object.keys(obj as Record<string, unknown>);
  for (let i = 0; i < keys.length; i++) {
    const k = keys[i];
    const v = (obj as Record<string, unknown>)[k];
    if (v !== undefined) {
      out[k] = v;
    }
  }
  return out;
}

// ================================================================
// L3: _safeMerge —— 逐字段安全合并（非法丢弃，合法写入）
// ================================================================
function _safeMerge(raw: Record<string, unknown>): Settings {
  const s: Settings = { ...DEFAULTS };

  if (_isValidTheme(raw.theme)) s.theme = raw.theme;
  if (_isValidFontSize(raw.fontSize)) s.fontSize = raw.fontSize as Settings['fontSize'];
  // aiBackend 修复：原先这一行漏掉了，导致每次读取设置时 aiBackend 都被重置为
  // DEFAULTS 里的 'deepseek'，用户在设置页选的后端刷新后丢失。
  if (_isNonEmptyStr(raw.aiBackend) && isAiBackendKey(raw.aiBackend)) {
    s.aiBackend = raw.aiBackend;
  }
  if (_isNonEmptyStr(raw.aiModel)) s.aiModel = raw.aiModel;
  if (_isNonEmptyStr(raw.aiBaseUrl)) s.aiBaseUrl = raw.aiBaseUrl;
  if (_isStr(raw.aiApiKey)) s.aiApiKey = raw.aiApiKey;
  if (_isNonEmptyStr(raw.aiModels)) s.aiModels = raw.aiModels;
  if (_isValidNum(raw.effectIntensity) && raw.effectIntensity >= 0 && raw.effectIntensity <= 100) {
    s.effectIntensity = raw.effectIntensity;
  }
  if (_isBool(raw.showCompanion)) s.showCompanion = raw.showCompanion;
  if (_isBool(raw.showMouseTrail)) s.showMouseTrail = raw.showMouseTrail;
  if (_isBool(raw.showSakura)) s.showSakura = raw.showSakura;

  return s;
}

// ================================================================
// 核心: safeReadAndMigrateSettings()
//
// 策略: 任何异常 → 直接丢弃旧数据 → 返回 DEFAULTS (miku 主题)
//
//   ① 读不到 key                     → DEFAULTS
//   ② JSON 解析失败 / 结果非对象       → 🔴 日志 → 删 key → DEFAULTS
//   ③ 缺少 settings 字段               → 🟠 日志 → 删 key → DEFAULTS
//   ④ version < 4（旧版本/无版本号）    → 🟡 日志 → 全量重置 → DEFAULTS
//   ⑤ version >= 4                    → 过滤 undefined → 逐字段合并
// ================================================================
function safeReadAndMigrateSettings(): Settings {
  // ① 读不到 key
  const raw = _lsGet(STORAGE_KEY);
  if (raw === null) return { ...DEFAULTS };

  // ② JSON 解析失败 / 非对象
  let parsed: Record<string, unknown> | null = null;
  if (typeof raw === 'string' && raw.length > 0) {
    try {
      const v = JSON.parse(raw);
      if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
        parsed = v as Record<string, unknown>;
      }
    } catch {
      /* 解析失败 → parsed 保持 null */
    }
  }

  if (parsed === null) {
    console.warn('[fufu] 🔴 解析失败 — 旧数据已损坏，丢弃并重置默认配置');
    _lsDel(STORAGE_KEY);
    return { ...DEFAULTS };
  }

  // ③ 提取 settings — 只接受 { state: { settings: {} } } 格式
  let rawSettings: Record<string, unknown> | null = null;

  const state = parsed.state;
  if (state !== null && state !== undefined && typeof state === 'object' && !Array.isArray(state)) {
    const s = (state as Record<string, unknown>).settings;
    if (s !== null && s !== undefined && typeof s === 'object' && !Array.isArray(s)) {
      rawSettings = s as Record<string, unknown>;
    }
  }

  if (rawSettings === null) {
    console.warn('[fufu] 🟠 数据残缺 — 缺少 settings 字段，丢弃并重置默认配置');
    _lsDel(STORAGE_KEY);
    return { ...DEFAULTS };
  }

  // ④ 版本检查: version < 4 → 全量重置
  let storedVersion = 0;
  const ver = parsed.version;
  if (typeof ver === 'number' && !isNaN(ver) && isFinite(ver)) {
    storedVersion = ver;
  }

  if (storedVersion < CURRENT_VERSION) {
    if (import.meta.env.DEV)
      console.info('[fufu] 版本过低，已重置为默认配置', storedVersion, '→', CURRENT_VERSION);
    return { ...DEFAULTS };
  }

  // ⑤ 正常路径: 过滤 undefined → 逐字段合并
  const cleaned = _stripUndefined(rawSettings);
  return _safeMerge(cleaned);
}

// ================================================================
// Zustand Store
// ================================================================
export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      settings: safeReadAndMigrateSettings(),
      updateSettings: (partial) =>
        set((s) => {
          const base = s && s.settings ? s.settings : { ...DEFAULTS };
          const next = { ...base, ...partial };
          _applyDOM(next.theme, next.fontSize);
          return { settings: next };
        }),
    }),
    {
      name: 'fufu-settings-v2',
      partialize: (state) => ({ settings: state.settings }),
      migrate: () => ({ settings: safeReadAndMigrateSettings() }),
      version: CURRENT_VERSION,
    },
  ),
);

// ================================================================
// DOM 应用
// ================================================================
function _applyDOM(theme: unknown, fontSize: unknown): void {
  try {
    const root = document.documentElement;
    if (!root) return;
    root.classList.remove('dark');
    root.setAttribute('data-theme', _isValidTheme(theme) ? theme : 'miku');
    root.setAttribute('data-font-size', _isValidFontSize(fontSize) ? String(fontSize) : 'medium');
  } catch {
    /* DOM 不可用 */
  }
}

// ================================================================
// 初始化入口（main.tsx 调用，React 渲染前）
// ================================================================
export function initThemeAndFontSize(): void {
  try {
    // 1. 调用核心函数，内部处理所有异常路径
    const settings = safeReadAndMigrateSettings();

    // 2. 应用 theme（safeReadAndMigrateSettings 保证返回完整对象）
    _applyDOM(settings.theme, settings.fontSize);

    // 3. 终极兜底
    const root = document.documentElement;
    if (root) {
      const t = root.getAttribute('data-theme');
      if (t === null || t === undefined || (typeof t === 'string' && t.length === 0)) {
        root.setAttribute('data-theme', 'miku');
      }
      const f = root.getAttribute('data-font-size');
      if (f === null || f === undefined || (typeof f === 'string' && f.length === 0)) {
        root.setAttribute('data-font-size', 'medium');
      }
    }
  } catch {
    _applyDOM('miku', 'medium');
  }
}

// ================================================================
// 调试: resetAllSettings() — 清空全部本地存储并刷新
// ================================================================
export function resetAllSettings(): void {
  const KEYS = [
    'fufu-settings',
    'fufu-settings-v2',
    'fufu-token',
    'fufu-search-history',
    'fufu-sort',
    'fufu-since',
    'fufu-cat',
    'fufu-poll-votes',
    'fufu-cleanup-version',
    'fufu-reshuffle',
  ];

  let n = 0;
  for (let i = 0; i < KEYS.length; i++) {
    if (_lsGet(KEYS[i]) !== null) {
      _lsDel(KEYS[i]);
      n++;
    }
  }

  if (import.meta.env.DEV) console.info('[fufu] 已清除缓存项:', n);
  _applyDOM('miku', 'medium');

  try {
    setTimeout(() => window.location.reload(), 200);
  } catch {
    /* 无 window */
  }
}

if (typeof window !== 'undefined') {
  (window as any).__fufu_resetAllSettings = resetAllSettings;
}
