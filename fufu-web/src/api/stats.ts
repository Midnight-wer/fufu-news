import client from './client';
import { unwrapOr } from './unwrap';

/** 区间总量 */
export interface VisitTotals {
  pv: number;
  uv: number;
  depth: number;
  days: number;
}

/** 按天分布 */
export interface DailyPoint {
  date: string;
  pv: number;
  uv: number;
}

/** 热门页面 */
export interface PathCount {
  path: string;
  pv: number;
}

/** 来源 IP（后端已脱敏） */
export interface IpCount {
  ip: string;
  pv: number;
}

/** 名称 + 计数（设备、浏览器分布） */
export interface NameValue {
  name: string;
  value: number;
}

/** 最近一条访问记录 */
export interface RecentVisit {
  time: string;
  method: string;
  path: string;
  status: number;
  ip: string;
  device: string;
  is_page_view: boolean;
}

/** 外部统计口径基线（如托管平台访问统计） */
export interface VisitBaseline {
  id: number;
  pv: number;
  uv: number;
  period_start: string;
  period_end: string;
  source: string;
  note: string;
  depth: number;
  created_at: string;
}

/** 站内实时统计 + 基线合并口径 */
export interface VisitStats {
  totals: VisitTotals;
  today: { pv: number; uv: number };
  daily: DailyPoint[];
  top_paths: PathCount[];
  top_ips: IpCount[];
  devices: NameValue[];
  browsers: NameValue[];
  recent: RecentVisit[];
  baselines: VisitBaseline[];
  combined: {
    pv: number;
    uv: number;
    baseline_pv: number;
    baseline_uv: number;
    live_pv: number;
    live_uv: number;
  };
  generated_at: string;
}

/** 空态兜底：所有列表一律 []，避免页面拿到 undefined 后崩溃 */
export const EMPTY_VISIT_STATS: VisitStats = {
  totals: { pv: 0, uv: 0, depth: 0, days: 30 },
  today: { pv: 0, uv: 0 },
  daily: [],
  top_paths: [],
  top_ips: [],
  devices: [],
  browsers: [],
  recent: [],
  baselines: [],
  combined: {
    pv: 0,
    uv: 0,
    baseline_pv: 0,
    baseline_uv: 0,
    live_pv: 0,
    live_uv: 0,
  },
  generated_at: '',
};

/** 拉取访问统计（PV / UV / 趋势 / 热门页面 / 来源分布 / 基线） */
export async function fetchVisitStats(days = 30): Promise<VisitStats> {
  const { data } = await client.get('/stats/visits', { params: { days } });
  return unwrapOr<VisitStats>(data, EMPTY_VISIT_STATS);
}

/** 登记一条外部统计口径基线 */
export async function createVisitBaseline(payload: {
  pv: number;
  uv: number;
  period_start: string;
  period_end: string;
  source: string;
  note: string;
}): Promise<void> {
  await client.post('/stats/baselines', payload);
}
