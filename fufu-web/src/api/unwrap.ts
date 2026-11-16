/**
 * 后端响应解包工具（tolerant unwrap）
 * ===================================
 *
 * 背景：后端目前存在两种响应形态并存的情况
 *   - 信封：{ code, data, message }（ranking / history / comments / folders 等）
 *   - 裸返回：ArticleListResponse / Source[] / { access_token } 等
 *
 * 本工具对两种形态都能安全解包，且**对裸返回是恒等变换** ——
 * 这是「不破坏 articles / sources / auth 等现有调用点」的核心保证。
 *
 * 幂等性：unwrap(unwrap(x)) 恒成立（解包后的对象不再同时具备 code+data 键），
 * 所以 api 层和 hook 层各解一次也不会出错，改造可以分批进行。
 */

/** 约定的响应信封（宽容定义：只要同时有 number 型 code 和 data 键就认定为信封） */
export interface ApiEnvelope<T = unknown> {
  code?: number;
  data?: T | null;
  message?: string;
  detail?: unknown;
  [key: string]: unknown;
}

/** 业务错误：仅 unwrapStrict 或显式调用时抛出 */
export class ApiError extends Error {
  readonly code: number;
  readonly detail?: unknown;

  constructor(code: number, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.detail = detail;
  }
}

/** 判定是否为信封：必须是非数组对象，且有 number 型 code + data 键 */
export function isEnvelope(v: unknown): v is ApiEnvelope {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return false;
  const o = v as Record<string, unknown>;
  return typeof o.code === 'number' && Object.prototype.hasOwnProperty.call(o, 'data');
}

/**
 * 解包核心。
 *
 * - null / undefined        → null
 * - 非对象（纯文本/数字等） → null
 *   （后端崩溃时 axios 会把 "Internal Server Error" 放进 data，
 *     这里返回 null 让调用方走 fallback，而不是把字符串当对象用）
 * - 裸数组                  → 原样返回
 * - 裸对象（无 code+data）  → 原样返回  ← articles / sources / rss_proxy / auth 走这条
 * - 信封 且 code < 400      → 返回 data（data 为 null/undefined 时返回 null）
 * - 信封 且 code >= 400     → 抛 ApiError
 */
export function unwrap<T = unknown>(raw: unknown): T | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw !== 'object') return null;
  if (Array.isArray(raw)) return raw as unknown as T;
  if (!isEnvelope(raw)) return raw as unknown as T;

  if (typeof raw.code === 'number' && raw.code >= 400) {
    throw new ApiError(
      raw.code,
      typeof raw.message === 'string' && raw.message ? raw.message : '请求失败',
      raw.detail,
    );
  }
  return raw.data === undefined || raw.data === null ? null : (raw.data as T);
}

/**
 * 带兜底的解包：解包失败（空 / 错误信封 / 非对象）一律返回 fallback，不抛错。
 * 迁移期默认用这个 —— 错误态退化为默认值，不会让页面报错。
 */
export function unwrapOr<T>(raw: unknown, fallback: T): T {
  try {
    const v = unwrap<T>(raw);
    return v === null || v === undefined ? fallback : v;
  } catch {
    return fallback;
  }
}

/** 严格解包：错误信封直接抛 ApiError，交给 react-query 的 error 态。新代码建议用这个。 */
export function unwrapStrict<T>(raw: unknown): T {
  const v = unwrap<T>(raw);
  if (v === null || v === undefined) throw new ApiError(500, '响应为空');
  return v;
}

/** 解包成数组：非数组一律返回 [] —— 符合项目「列表一律 [] 兜底」的约定 */
export function unwrapList<T>(raw: unknown): T[] {
  try {
    const v = unwrap<unknown>(raw);
    return Array.isArray(v) ? (v as T[]) : [];
  } catch {
    return [];
  }
}
