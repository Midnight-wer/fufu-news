import client from './client';
import { unwrapOr } from './unwrap';

/**
 * 订阅源相关接口集合（健康检测 / 批量校验 / 全量爬取 / OPML 导入导出）。
 *
 * 收敛目的：SourcesPage 原先内联了 6 处 `client.*` 调用，
 * 这些是页面里最集中的一处「绕过 api 层」。现在全部收口到此模块，
 * 页面只负责状态与交互。
 */

/** 单个源的健康统计（/sources/health/{id}）。字段可选，后端无数据时为空。 */
export interface SourceHealth {
  total?: number;
  success_rate?: number;
  avg_latency?: number;
  consecutive_fails?: number;
}

export interface ValidateAllResult {
  results: unknown[];
  total: number;
  unhealthy: number;
}

export interface ValidateSourceResult {
  status: string;
  issues?: { detail: string }[];
  [key: string]: unknown;
}

export interface FetchAllResult {
  message?: string;
}

export interface OpmlExportResult {
  xml: string;
}

export interface OpmlImportResult {
  imported: number;
  skipped: number;
}

/** 查询单个源的健康统计；无数据返回 null（由调用方决定如何展示）。 */
export async function fetchSourceHealth(sourceId: number): Promise<SourceHealth | null> {
  const { data } = await client.get(`/sources/health/${sourceId}`);
  return unwrapOr<SourceHealth | null>(data, null);
}

/** 批量校验所有源的健康状态。 */
export async function validateAllSources(): Promise<ValidateAllResult> {
  const { data } = await client.post('/sources/validate-all');
  return unwrapOr<ValidateAllResult>(data, { results: [], total: 0, unhealthy: 0 });
}

/** 试解析一个 RSS/网页地址，用于「加入前先看看能不能抓」。 */
export async function validateSource(url: string): Promise<ValidateSourceResult> {
  const { data } = await client.post('/sources/validate', { url });
  return unwrapOr<ValidateSourceResult>(data, {
    status: 'error',
    issues: [{ detail: '请求失败' }],
  });
}

/** 触发全量爬取。 */
export async function fetchAllSources(): Promise<FetchAllResult> {
  const { data } = await client.post('/sources/fetch-all');
  return unwrapOr<FetchAllResult>(data, {});
}

/** 导出 OPML（返回 xml 文本，由调用方落成文件下载）。 */
export async function exportOpml(): Promise<OpmlExportResult> {
  const { data } = await client.post('/sources/opml-export');
  return unwrapOr<OpmlExportResult>(data, { xml: '' });
}

/** 导入 OPML。 */
export async function importOpml(xml: string): Promise<OpmlImportResult> {
  const { data } = await client.post('/sources/opml-import', { xml });
  return unwrapOr<OpmlImportResult>(data, { imported: 0, skipped: 0 });
}
