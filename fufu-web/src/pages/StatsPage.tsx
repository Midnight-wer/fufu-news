import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ChartBar,
  Users,
  Eye,
  Pulse,
  ListBullets,
  GlobeHemisphereWest,
  DeviceMobile,
  Clock,
  Plus,
  CaretRight,
} from '@phosphor-icons/react';
import {
  fetchVisitStats,
  createVisitBaseline,
  EMPTY_VISIT_STATS,
  type VisitStats,
} from '../api/stats';

const RANGES = [
  { days: 7, label: '近 7 天' },
  { days: 30, label: '近 30 天' },
  { days: 90, label: '近 90 天' },
];

/** 数字千分位 */
function fmt(n: number): string {
  return (n ?? 0).toLocaleString('zh-CN');
}

/** 指标卡 */
function StatCard({
  icon: Icon,
  label,
  value,
  unit,
  note,
  accent = 'teal',
}: {
  icon: typeof Eye;
  label: string;
  value: string;
  unit?: string;
  note?: string;
  accent?: 'teal' | 'pink' | 'lavender' | 'mint';
}) {
  const accentClass = {
    teal: 'text-fufu-teal-deep bg-fufu-teal-soft/25',
    pink: 'text-fufu-pink bg-fufu-pink-soft/30',
    lavender: 'text-fufu-lavender bg-fufu-lavender-light/40',
    mint: 'text-fufu-mint bg-fufu-mint-light/35',
  }[accent];

  return (
    <div className="fufu-card rounded-fufu-card p-4 sm:p-5 flex items-start gap-3">
      <div className={`w-10 h-10 rounded-fufu flex items-center justify-center shrink-0 ${accentClass}`}>
        <Icon size={20} weight="duotone" />
      </div>
      <div className="min-w-0">
        <div className="font-body text-[11px] sm:text-xs text-fufu-text-light">{label}</div>
        <div className="font-cute text-2xl sm:text-3xl text-fufu-text leading-tight mt-0.5">
          {value}
          {unit && <span className="font-body text-xs text-fufu-text-muted ml-1">{unit}</span>}
        </div>
        {note && <div className="font-body text-[10px] sm:text-[11px] text-fufu-text-muted mt-1">{note}</div>}
      </div>
    </div>
  );
}

/** 横向条形（热门页面 / 来源 IP） */
function BarRow({
  label,
  value,
  max,
  sub,
}: {
  label: string;
  value: number;
  max: number;
  sub?: string;
}) {
  const width = max > 0 ? Math.max((value / max) * 100, 3) : 0;
  return (
    <div className="px-3 sm:px-4 py-2.5">
      <div className="flex items-center justify-between gap-3 mb-1">
        <span className="font-body text-xs sm:text-sm text-fufu-text truncate" title={label}>
          {label}
        </span>
        <span className="font-cute text-xs sm:text-sm text-fufu-teal-deep shrink-0">
          {fmt(value)}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-fufu-teal-soft/20 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${width}%`,
            background: 'linear-gradient(90deg, rgb(var(--fufu-teal)), rgb(var(--fufu-pink)))',
          }}
        />
      </div>
      {sub && <div className="font-body text-[10px] text-fufu-text-muted mt-1">{sub}</div>}
    </div>
  );
}

/** 每日趋势柱状图 */
function TrendChart({ data }: { data: VisitStats['daily'] }) {
  const max = useMemo(() => Math.max(...data.map((d) => d.pv), 1), [data]);
  if (data.length === 0) {
    return (
      <p className="font-body text-xs text-fufu-text-light text-center py-10">
        这段时间还没有访问记录哦～
      </p>
    );
  }
  return (
    <div className="flex items-end gap-1 sm:gap-1.5 h-32 sm:h-40 px-3 sm:px-4 pb-2">
      {data.map((d) => (
        <div key={d.date} className="flex-1 flex flex-col items-center gap-1 group min-w-0">
          <div className="relative w-full flex items-end justify-center" style={{ height: '100%' }}>
            <div
              className="w-full rounded-t-sm transition-all duration-500"
              style={{
                height: `${Math.max((d.pv / max) * 100, 2)}%`,
                background: 'linear-gradient(180deg, rgb(var(--fufu-teal)), rgb(var(--fufu-teal-soft)))',
              }}
              title={`${d.date}｜PV ${d.pv}｜UV ${d.uv}`}
            />
          </div>
          <span className="font-body text-[9px] text-fufu-text-muted truncate w-full text-center">
            {d.date.slice(5)}
          </span>
        </div>
      ))}
    </div>
  );
}

/** 外部统计口径基线登记表单 */
function BaselineForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const [pv, setPv] = useState('3234');
  const [uv, setUv] = useState('1200');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [source, setSource] = useState('托管平台访问统计');
  const [note, setNote] = useState('');

  const mutation = useMutation({
    mutationFn: () =>
      createVisitBaseline({
        pv: Number(pv) || 0,
        uv: Number(uv) || 0,
        period_start: start,
        period_end: end,
        source,
        note,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['visit-stats'] });
      onDone();
    },
  });

  const inputClass =
    'w-full px-3 py-2 rounded-fufu-input border border-fufu-teal-soft/25 bg-white/70 font-body text-xs text-fufu-text focus:outline-none focus:border-fufu-teal/50 transition-colors';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 sm:p-4">
      <div>
        <label className="font-body text-[11px] text-fufu-text-light">访问量 PV</label>
        <input className={`${inputClass} mt-1`} value={pv} onChange={(e) => setPv(e.target.value)} />
      </div>
      <div>
        <label className="font-body text-[11px] text-fufu-text-light">独立访客 UV</label>
        <input className={`${inputClass} mt-1`} value={uv} onChange={(e) => setUv(e.target.value)} />
      </div>
      <div>
        <label className="font-body text-[11px] text-fufu-text-light">统计周期起</label>
        <input
          className={`${inputClass} mt-1`}
          placeholder="YYYY-MM-DD"
          value={start}
          onChange={(e) => setStart(e.target.value)}
        />
      </div>
      <div>
        <label className="font-body text-[11px] text-fufu-text-light">统计周期止</label>
        <input
          className={`${inputClass} mt-1`}
          placeholder="YYYY-MM-DD"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
        />
      </div>
      <div className="sm:col-span-2">
        <label className="font-body text-[11px] text-fufu-text-light">数据来源</label>
        <input
          className={`${inputClass} mt-1`}
          value={source}
          onChange={(e) => setSource(e.target.value)}
        />
      </div>
      <div className="sm:col-span-2">
        <label className="font-body text-[11px] text-fufu-text-light">口径备注</label>
        <input
          className={`${inputClass} mt-1`}
          placeholder="如：独立访客按客户端 IP 去重，剔除爬虫与内网地址"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      <div className="sm:col-span-2">
        <button
          className="fufu-btn-primary text-xs sm:text-sm w-full sm:w-auto"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          <Plus size={14} weight="bold" className="mr-1 inline" />
          {mutation.isPending ? '登记中…' : '登记为统计基线'}
        </button>
      </div>
    </div>
  );
}

export default function StatsPage() {
  const [days, setDays] = useState(30);
  const [showForm, setShowForm] = useState(false);

  const query = useQuery<VisitStats>({
    queryKey: ['visit-stats', days],
    queryFn: () => fetchVisitStats(days),
    placeholderData: EMPTY_VISIT_STATS,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });

  const stats = query.data ?? EMPTY_VISIT_STATS;
  const { totals, combined, baselines } = stats;
  const maxPathPv = Math.max(...stats.top_paths.map((p) => p.pv), 1);
  const maxIpPv = Math.max(...stats.top_ips.map((p) => p.pv), 1);
  const deviceTotal = stats.devices.reduce((sum, d) => sum + d.value, 0) || 1;

  return (
    <div>
      {/* 页面标题 */}
      <div className="mb-4 sm:mb-6">
        <h2 className="font-cute text-2xl sm:text-3xl text-fufu-text flex items-center gap-2">
          <ChartBar size={24} weight="fill" className="text-fufu-teal animate-pulse-soft" />
          访问统计
        </h2>
        <p className="font-body text-xs sm:text-sm text-fufu-text-light mt-1">
          每一笔访问都来自服务端访问日志（access_log 表 · logs/access.log），可逐条追溯 📊
        </p>
      </div>

      {/* 统计区间切换 */}
      <div className="relative w-full rounded-fufu-card border border-fufu-teal-soft/20 bg-white/40 p-1 overflow-hidden mb-4 sm:mb-6">
        <div
          className="absolute top-1 bottom-1 rounded-fufu bg-white shadow-fufu-sm transition-all duration-300 ease-out z-0"
          style={{
            width: `calc((100% - 8px) / ${RANGES.length})`,
            left: `calc((100% - 8px) / ${RANGES.length} * ${RANGES.findIndex((r) => r.days === days)} + 4px)`,
          }}
        />
        <div className="relative z-10 flex">
          {RANGES.map((range) => {
            const isActive = range.days === days;
            return (
              <button
                key={range.days}
                onClick={() => setDays(range.days)}
                className={[
                  'flex-1 flex items-center justify-center py-2.5 sm:py-3',
                  'font-cute text-xs sm:text-sm transition-colors duration-200 touch-target',
                  isActive ? 'text-fufu-teal-deep font-medium' : 'text-fufu-text-light hover:text-fufu-text',
                ].join(' ')}
              >
                {range.label}
              </button>
            );
          })}
        </div>
      </div>

      {query.isError ? (
        <div className="fufu-card rounded-fufu-card text-center py-16">
          <p className="text-5xl mb-4 animate-float">😿</p>
          <p className="font-cute text-lg text-fufu-text">访问统计加载失败啦～</p>
          <p className="font-body text-xs text-fufu-text-light mt-2">
            检查一下后端服务是不是还在运行呢？
          </p>
          <button className="fufu-btn-primary mt-4 text-sm" onClick={() => query.refetch()}>
            重新加载
          </button>
        </div>
      ) : (
        <div className="space-y-4 sm:space-y-5">
          {/* 外部统计口径基线 */}
          <div className="fufu-card rounded-fufu-card overflow-hidden">
            <div className="flex items-center justify-between px-4 sm:px-5 py-3 border-b border-fufu-teal-soft/10">
              <h3 className="font-cute text-sm sm:text-base text-fufu-text flex items-center gap-2">
                <GlobeHemisphereWest size={18} weight="duotone" className="text-fufu-lavender" />
                平台统计基线
              </h3>
              <button
                className="font-body text-[11px] text-fufu-teal-deep hover:text-fufu-pink transition-colors flex items-center gap-1"
                onClick={() => setShowForm((v) => !v)}
              >
                <Plus size={12} weight="bold" />
                {showForm ? '收起' : '登记'}
              </button>
            </div>

            {baselines.length === 0 ? (
              <p className="font-body text-xs text-fufu-text-light text-center py-8">
                还没有登记统计基线～
              </p>
            ) : (
              <div className="divide-y divide-fufu-teal-soft/8">
                {baselines.map((b) => (
                  <div key={b.id} className="px-4 sm:px-5 py-3">
                    <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                      <span className="font-cute text-lg text-fufu-teal-deep">
                        {fmt(b.pv)}
                        <span className="font-body text-[11px] text-fufu-text-muted ml-1">PV</span>
                      </span>
                      <span className="font-cute text-lg text-fufu-pink">
                        {fmt(b.uv)}
                        <span className="font-body text-[11px] text-fufu-text-muted ml-1">UV</span>
                      </span>
                      <span className="font-body text-[11px] text-fufu-text-light">
                        人均 {b.depth} 次
                      </span>
                      {b.period_start && b.period_end && (
                        <span className="font-body text-[11px] text-fufu-text-muted">
                          {b.period_start} ~ {b.period_end}
                        </span>
                      )}
                    </div>
                    <div className="font-body text-[11px] text-fufu-text-muted mt-1">
                      来源：{b.source || '未标注'}
                      {b.note ? ` · ${b.note}` : ''}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {showForm && <BaselineForm onDone={() => setShowForm(false)} />}
          </div>

          {/* 核心指标 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 sm:gap-4">
            <StatCard
              icon={Eye}
              label="总访问量 PV"
              value={fmt(combined.pv)}
              unit="次"
              note={`平台统计 ${fmt(combined.baseline_pv)} + 站内日志 ${fmt(combined.live_pv)}`}
            />
            <StatCard
              icon={Users}
              label="独立访客 UV"
              value={fmt(combined.uv)}
              unit="人"
              note={`平台统计 ${fmt(combined.baseline_uv)} + 站内日志 ${fmt(combined.live_uv)}`}
              accent="pink"
            />
            <StatCard
              icon={Pulse}
              label="人均访问深度"
              value={
                combined.uv > 0 ? (combined.pv / combined.uv).toFixed(2) : '0.00'
              }
              unit="次/人"
              note="总访问量 ÷ 独立访客数"
              accent="lavender"
            />
            <StatCard
              icon={Clock}
              label="今日访问"
              value={fmt(stats.today.pv)}
              unit="次"
              note={`今日独立访客 ${fmt(stats.today.uv)} 人`}
              accent="mint"
            />
          </div>

          {/* 每日趋势 */}
          <div className="fufu-card rounded-fufu-card overflow-hidden">
            <div className="px-4 sm:px-5 py-3 border-b border-fufu-teal-soft/10">
              <h3 className="font-cute text-sm sm:text-base text-fufu-text">
                每日访问趋势
                <span className="font-body text-[11px] text-fufu-text-muted ml-2">
                  站内日志 · 近 {totals.days} 天
                </span>
              </h3>
            </div>
            <TrendChart data={stats.daily} />
          </div>

          {/* 热门页面 + 来源 IP */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="fufu-card rounded-fufu-card overflow-hidden">
              <div className="px-4 sm:px-5 py-3 border-b border-fufu-teal-soft/10">
                <h3 className="font-cute text-sm sm:text-base text-fufu-text flex items-center gap-2">
                  <ListBullets size={16} weight="duotone" className="text-fufu-teal" />
                  热门页面
                </h3>
              </div>
              {stats.top_paths.length === 0 ? (
                <p className="font-body text-xs text-fufu-text-light text-center py-8">
                  暂无访问记录～
                </p>
              ) : (
                <div className="divide-y divide-fufu-teal-soft/5">
                  {stats.top_paths.map((p) => (
                    <BarRow key={p.path} label={p.path} value={p.pv} max={maxPathPv} />
                  ))}
                </div>
              )}
            </div>

            <div className="fufu-card rounded-fufu-card overflow-hidden">
              <div className="px-4 sm:px-5 py-3 border-b border-fufu-teal-soft/10">
                <h3 className="font-cute text-sm sm:text-base text-fufu-text flex items-center gap-2">
                  <GlobeHemisphereWest size={16} weight="duotone" className="text-fufu-lavender" />
                  来源 IP 分布
                  <span className="font-body text-[11px] text-fufu-text-muted">（已脱敏）</span>
                </h3>
              </div>
              {stats.top_ips.length === 0 ? (
                <p className="font-body text-xs text-fufu-text-light text-center py-8">
                  暂无访问记录～
                </p>
              ) : (
                <div className="divide-y divide-fufu-teal-soft/5">
                  {stats.top_ips.map((p) => (
                    <BarRow key={p.ip} label={p.ip} value={p.pv} max={maxIpPv} />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 设备分布 + 最近访问 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="fufu-card rounded-fufu-card overflow-hidden">
              <div className="px-4 sm:px-5 py-3 border-b border-fufu-teal-soft/10">
                <h3 className="font-cute text-sm sm:text-base text-fufu-text flex items-center gap-2">
                  <DeviceMobile size={16} weight="duotone" className="text-fufu-mint" />
                  访问设备分布
                </h3>
              </div>
              {stats.devices.length === 0 ? (
                <p className="font-body text-xs text-fufu-text-light text-center py-8">
                  暂无访问记录～
                </p>
              ) : (
                <div className="p-3 sm:p-4 space-y-2.5">
                  {stats.devices.map((d) => (
                    <div key={d.name}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-body text-xs text-fufu-text">{d.name}</span>
                        <span className="font-body text-[11px] text-fufu-text-muted">
                          {fmt(d.value)} 次 · {Math.round((d.value / deviceTotal) * 100)}%
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-fufu-teal-soft/20 overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.max((d.value / deviceTotal) * 100, 2)}%`,
                            background: 'linear-gradient(90deg, rgb(var(--fufu-mint)), rgb(var(--fufu-teal)))',
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="fufu-card rounded-fufu-card overflow-hidden">
              <div className="px-4 sm:px-5 py-3 border-b border-fufu-teal-soft/10">
                <h3 className="font-cute text-sm sm:text-base text-fufu-text">
                  最近访问记录
                  <span className="font-body text-[11px] text-fufu-text-muted ml-2">最新 20 条</span>
                </h3>
              </div>
              {stats.recent.length === 0 ? (
                <p className="font-body text-xs text-fufu-text-light text-center py-8">
                  还没有访问记录，等人来看看～
                </p>
              ) : (
                <div className="max-h-80 overflow-y-auto">
                  {stats.recent.map((r, i) => (
                    <div
                      key={`${r.time}-${i}`}
                      className="flex items-center gap-2 px-4 sm:px-5 py-2 border-b border-fufu-teal-soft/5 last:border-b-0"
                    >
                      <span className="font-body text-[10px] text-fufu-text-muted shrink-0 tabular-nums">
                        {r.time ? new Date(r.time).toLocaleTimeString('zh-CN') : '--:--:--'}
                      </span>
                      <span
                        className={`font-body text-[10px] px-1.5 py-0.5 rounded shrink-0 ${
                          r.status < 400
                            ? 'bg-fufu-mint-light/30 text-fufu-mint'
                            : 'bg-fufu-error-light/25 text-fufu-error'
                        }`}
                      >
                        {r.status}
                      </span>
                      <span className="font-body text-[11px] text-fufu-text truncate flex-1 min-w-0">
                        {r.method} {r.path}
                      </span>
                      <span className="font-body text-[10px] text-fufu-text-muted shrink-0">
                        {r.ip}
                      </span>
                      <CaretRight size={10} className="text-fufu-text-muted/30 shrink-0" />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
