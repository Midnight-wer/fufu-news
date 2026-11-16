import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios';
import { ApiError } from './unwrap';

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// 允许调用方对单个请求做细粒度控制
export interface FufuRequestConfig extends AxiosRequestConfig {
  /** 已被自动重试过一次（内部使用） */
  _retried?: boolean;
  /** 显式声明该请求可安全重试（用于幂等的 POST，例如查询类接口） */
  _retryable?: boolean;
  /** 跳过 401 自动跳转登录页（登录接口本身需要） */
  _skipAuthRedirect?: boolean;
}

/** 幂等方法：重试是安全的 */
const IDEMPOTENT_METHODS = new Set(['get', 'head', 'options']);

/** 401 时是否已经跳转过，避免并发多个 401 重复赋值 location */
let _authRedirecting = false;

function isBrowser(): boolean {
  return typeof window !== 'undefined';
}

/**
 * 从任意错误里取出可展示的中文提示。
 * 后端统一信封保留了 detail，前端多处依赖它展示具体原因。
 */
export function extractErrorMessage(err: unknown, fallback = '请求失败了～'): string {
  if (err instanceof ApiError) return err.message;
  const e = err as AxiosError<{ message?: string; detail?: unknown }> | undefined;
  if (!e) return fallback;

  const data = e.response?.data;
  if (!data) {
    if (e.code === 'ECONNABORTED') return '请求超时了，请检查网络～';
    return fallback;
  }
  if (typeof data.message === 'string' && data.message) return data.message;
  if (typeof data.detail === 'string' && data.detail) return data.detail;
  return fallback;
}

// ===== 请求拦截：自动附带 token =====
client.interceptors.request.use((config) => {
  if (!isBrowser()) return config;
  const token = localStorage.getItem('fufu-token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ===== 响应拦截：401 清理并跳转 + 有限重试 =====
client.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    // err.config 在少数场景（如请求构造失败）下可能为空，原先直接解引用会二次抛错
    const config = (err.config ?? {}) as FufuRequestConfig;
    const status = err.response?.status;

    // 401/403 → 清理 token 并跳转登录页
    // 修复：原先只删 token 不跳转，用户会卡在「所有接口都 401」的空白界面上；
    // 现在跳去登录页，并记住来路以便登录后返回。
    if (status === 401 || status === 403) {
      if (isBrowser()) {
        localStorage.removeItem('fufu-token');
        const onLoginPage = window.location.pathname === '/login';
        if (!config._skipAuthRedirect && !onLoginPage && !_authRedirecting) {
          _authRedirecting = true;
          try {
            sessionStorage.setItem('fufu-redirect', window.location.pathname);
          } catch {
            /* sessionStorage 不可用时忽略 */
          }
          window.location.href = '/login';
        }
      }
      return Promise.reject(err);
    }

    // 自动重试一次。
    // 修复：原先 POST/PATCH/DELETE 也会被重试，非幂等请求可能造成重复写入
    // （例如重复发评论、重复收藏）。现在仅对幂等方法或显式声明可重试的请求生效，
    // 且只针对网络错误与 502+（原先 500 也重试，会放大服务端压力）。
    const method = (config.method ?? 'get').toLowerCase();
    const canRetry = IDEMPOTENT_METHODS.has(method) || config._retryable === true;
    const shouldRetry =
      canRetry &&
      !config._retried &&
      (err.code === 'ECONNABORTED' || !err.response || (status ?? 0) >= 502);

    if (shouldRetry) {
      config._retried = true;
      await new Promise((resolve) => setTimeout(resolve, 800));
      return client(config as InternalAxiosRequestConfig);
    }

    return Promise.reject(err);
  },
);

export default client;
