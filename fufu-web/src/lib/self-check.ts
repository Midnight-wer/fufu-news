/**
 * 启动自检模块 — 页面加载时自动诊断
 *
 * 检查项:
 * 1. 网络状态
 * 2. IndexedDB 读写
 * 3. API 接口连通性
 * 4. 缓存数据完整性
 */
import { cacheSelfCheck, cacheIntegrityCheck } from './cache-db';

export interface CheckResult {
  name: string;
  status: 'pass' | 'warn' | 'fail';
  detail: string;
}

const results: CheckResult[] = [];

function log(result: CheckResult) {
  results.push(result);
  const emoji = result.status === 'pass' ? '✅' : result.status === 'warn' ? '⚠️' : '❌';
  console.log(`[自检] ${emoji} ${result.name}: ${result.detail}`);
}

export async function runSelfCheck(): Promise<CheckResult[]> {
  console.log('🔍 ======== fufu 新闻 · 启动自检 ========');

  // 1. 网络检查
  if (navigator.onLine) {
    log({ name: '网络状态', status: 'pass', detail: '在线' });
  } else {
    log({ name: '网络状态', status: 'warn', detail: '离线 — 仅使用缓存数据' });
  }

  // 2. IndexedDB 读写
  const dbOk = await cacheSelfCheck();
  log({
    name: 'IndexedDB',
    status: dbOk ? 'pass' : 'fail',
    detail: dbOk ? '读写正常' : '读写失败 — 缓存不可用',
  });

  // 3. API 连通性
  if (navigator.onLine) {
    try {
      const resp = await fetch('/api/v1/health', {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
      });
      const data = await resp.json();
      log({
        name: 'API 连通性',
        status: data?.status ? 'pass' : 'warn',
        detail: data?.status ? `后端正常 (${data.app || ''})` : '后端响应异常',
      });
    } catch {
      log({
        name: 'API 连通性',
        status: 'fail',
        detail: '无法连接后端 — 仅使用本地缓存',
      });
    }
  } else {
    log({ name: 'API 连通性', status: 'warn', detail: '跳过（离线）' });
  }

  // 4. 缓存完整性
  if (dbOk) {
    try {
      const integrity = await cacheIntegrityCheck();
      if (integrity.total === 0) {
        log({ name: '缓存完整性', status: 'pass', detail: '缓存为空（首次使用）' });
      } else if (integrity.corrupt === 0) {
        log({
          name: '缓存完整性',
          status: 'pass',
          detail: `${integrity.total} 条数据完整`,
        });
      } else {
        log({
          name: '缓存完整性',
          status: 'warn',
          detail: `${integrity.total} 条中 ${integrity.corrupt} 条损坏`,
        });
      }
    } catch {
      log({ name: '缓存完整性', status: 'warn', detail: '检查失败' });
    }
  }

  console.log('🔍 ======== 自检完成 ========');
  return results;
}

export function getOfflineBanner(): { show: boolean; text: string; type: 'warning' | 'error' | 'info' } {
  const api = results.find((r) => r.name === 'API 连通性');
  const net = results.find((r) => r.name === '网络状态');
  const db = results.find((r) => r.name === 'IndexedDB');

  if (net?.status === 'warn') {
    return { show: true, text: '📡 网络已断开，仅展示缓存数据', type: 'warning' };
  }
  if (api?.status === 'fail') {
    return {
      show: true,
      text: db?.status === 'pass'
        ? '🔌 无法连接后端服务，仅展示本地缓存数据'
        : '🔌 无法连接后端服务',
      type: 'error',
    };
  }
  if (api?.status === 'warn') {
    return { show: true, text: '⚠️ 后端服务响应异常，数据可能不完整', type: 'warning' };
  }
  return { show: false, text: '', type: 'info' };
}
