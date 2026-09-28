import { useState, useRef, useEffect } from 'react';
import { Plus, Trash, ArrowClockwise, Rss, Globe, DownloadSimple, UploadSimple, PencilSimple, Check, X, Lightning, MagnifyingGlass, ShieldCheck } from '@phosphor-icons/react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQueryClient } from '@tanstack/react-query';
import client from '../api/client';
import { useSources, useCreateSource, useDeleteSource, useFetchSource, useUpdateSource } from '../hooks/useSources';
import { useCheckAchievement } from '../hooks/useAchievements';
import { ClickRippleWrapper } from '../components/effects/ClickRipple';

type HealthStatus = 'ok' | 'warning' | 'error' | 'unknown';

function HealthDot({ status }: { status: HealthStatus }) {
  const colors: Record<HealthStatus, string> = {
    ok: 'bg-green-400', warning: 'bg-amber-400', error: 'bg-red-400', unknown: 'bg-gray-300',
  };
  const labels: Record<HealthStatus, string> = {
    ok: '正常', warning: '警告', error: '异常', unknown: '未知',
  };
  return (
    <span className="inline-flex items-center gap-1 font-cute text-[10px]">
      <span className={`w-2 h-2 rounded-full ${colors[status]} animate-pulse`} />
      {labels[status]}
    </span>
  );
}

export default function SourcesPage() {
  const { data: sources, isLoading, isPlaceholderData } = useSources();
  const safeSources = sources ?? [];
  const showLoading = isLoading || isPlaceholderData;
  const createSource = useCreateSource();
  const deleteSource = useDeleteSource();
  const updateSource = useUpdateSource();
  const fetchSource = useFetchSource();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<{ name: string; url: string; source_type: 'rss' | 'web'; folder: string }>({ name: '', url: '', source_type: 'rss', folder: '' });
  const [importMsg, setImportMsg] = useState('');
  const [validateAllLoading, setValidateAllLoading] = useState(false);
  const [validateResults, setValidateResults] = useState<any[] | null>(null);
  const [fetchAllLoading, setFetchAllLoading] = useState(false);
  const [rssPreviewUrl, setRssPreviewUrl] = useState('');
  const [rssPreviewResult, setRssPreviewResult] = useState<any>(null);
  const [rssPreviewLoading, setRssPreviewLoading] = useState(false);
  const qc = useQueryClient();

  const handleValidateAll = async () => {
    setValidateAllLoading(true);
    setValidateResults(null);
    try {
      const { data } = await client.post('/sources/validate-all');
      setValidateResults(data.results);
      setImportMsg(`验证完成：${data.total} 个源，${data.unhealthy} 个异常`);
    } catch (err: any) {
      setImportMsg(err?.response?.data?.detail || '批量验证失败');
    } finally {
      setValidateAllLoading(false);
    }
  };

  const handlePreviewRss = async () => {
    if (!rssPreviewUrl.trim()) return;
    setRssPreviewLoading(true);
    setRssPreviewResult(null);
    try {
      const { data } = await client.post('/sources/validate', { url: rssPreviewUrl.trim() });
      setRssPreviewResult(data);
    } catch {
      setRssPreviewResult({ status: 'error', issues: [{ detail: '请求失败' }] });
    } finally {
      setRssPreviewLoading(false);
    }
  };

  const handleFetchAll = async () => {
    setFetchAllLoading(true);
    try {
      const { data } = await client.post('/sources/fetch-all');
      setImportMsg(data.message || '全量爬取已触发');
      qc.invalidateQueries({ queryKey: ['sources'] });
      qc.invalidateQueries({ queryKey: ['articles'] });
    } catch (err: any) {
      setImportMsg(err?.response?.data?.detail || '全量爬取失败');
    } finally {
      setFetchAllLoading(false);
    }
  };

  const categoryIcons: Record<string, { icon: string; color: string }> = {
    '动漫': { icon: '🌸', color: '#00e5ff' },
    '二次元': { icon: '💫', color: '#E5A8E1' },
    '娱乐': { icon: '🎵', color: '#FFB5C5' },
    '游戏': { icon: '🎮', color: '#A8F1D3' },
    '科技': { icon: '💻', color: '#C4E4F5' },
    'Cosplay': { icon: '🎀', color: '#39c5bb' },
    '科普': { icon: '🔬', color: '#B8D8F0' },
    '综合': { icon: '📰', color: '#D0C8E0' },
    '趣味': { icon: '🎲', color: '#FFE8C0' },
    '文化': { icon: '📚', color: '#E8D4D0' },
  };
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ name: '', url: '', source_type: 'rss' as 'rss' | 'web', folder: '' });
  const fileRef = useRef<HTMLInputElement>(null);
  const checkAchievement = useCheckAchievement();

  useEffect(() => {
    if (safeSources.length >= 5) checkAchievement.mutate({ key: 'source_5' });
    if (safeSources.length >= 10) checkAchievement.mutate({ key: 'source_10' });
  }, [safeSources]);

  const handleExport = async () => {
    try {
      const { data } = await client.post('/sources/opml-export');
      const blob = new Blob([data.xml], { type: 'text/xml' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'fufu-subscriptions.opml';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      setImportMsg('导出失败，请稍后再试～');
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const xml = await file.text();
      const { data } = await client.post('/sources/opml-import', { xml });
      setImportMsg(`成功导入 ${data.imported} 个源${data.skipped > 0 ? `，跳过 ${data.skipped} 个重复` : ''}`);
      qc.invalidateQueries({ queryKey: ['sources'] });
    } catch (err: any) {
      setImportMsg(err?.response?.data?.detail || '导入失败，文件格式可能不对哦～');
    }
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await createSource.mutateAsync(form);
    setForm({ name: '', url: '', source_type: 'rss', folder: '' });
    setShowForm(false);
  };

  const startEdit = (s: NonNullable<typeof sources>[number]) => {
    setEditingId(s.id);
    setEditForm({ name: s.name, url: s.url, source_type: s.source_type as 'rss' | 'web', folder: s.folder || '' });
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  const saveEdit = async () => {
    if (!editingId) return;
    await updateSource.mutateAsync({ id: editingId, ...editForm });
    setEditingId(null);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="font-cute text-3xl text-fufu-text">📡 订阅源</h2>
          <p className="font-body text-sm text-fufu-text/50 mt-1">
            管理你的新闻来源～
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".opml,.xml"
            className="hidden"
            onChange={handleImport}
          />
          <button
            className="fufu-btn bg-fufu-cream text-fufu-text/60 flex items-center gap-1.5 text-sm"
            onClick={() => fileRef.current?.click()}
            title="从别的地方搬来订阅列表？"
          >
            <UploadSimple size={18} /> 导入
          </button>
          {(safeSources.length ?? 0) > 0 && (
            <button
              className="fufu-btn bg-fufu-cream text-fufu-text/60 flex items-center gap-1.5 text-sm"
              onClick={handleExport}
              title="导出订阅列表"
            >
              <DownloadSimple size={18} /> 导出
            </button>
          )}
          <button
            className="fufu-btn bg-fufu-teal-soft/30 text-fufu-teal-deep flex items-center gap-1.5 text-sm"
            onClick={handleValidateAll}
            disabled={validateAllLoading}
          >
            <ShieldCheck size={18} className={validateAllLoading ? 'animate-spin' : ''} />
            {validateAllLoading ? '检测中...' : '健康检测'}
          </button>
          <button
            className="fufu-btn bg-fufu-pink-soft/30 text-fufu-pink flex items-center gap-1.5 text-sm"
            onClick={handleFetchAll}
            disabled={fetchAllLoading}
          >
            <Lightning size={18} className={fetchAllLoading ? 'animate-spin' : ''} />
            {fetchAllLoading ? '爬取中...' : '全量爬取'}
          </button>
          <button
            className="fufu-btn-primary flex items-center gap-2"
            onClick={() => setShowForm(!showForm)}
          >
            <Plus size={20} /> 添加订阅
          </button>
        </div>
      </div>

      {importMsg && (
        <div className="mb-4 p-3 rounded-fufu-card bg-fufu-soft-yellow/50 font-body text-sm text-fufu-text/70">
          {importMsg}
        </div>
      )}

      {/* 批量验证结果 */}
      {validateResults && (
        <div className="mb-4 p-4 rounded-fufu-card bg-white border max-h-64 overflow-y-auto">
          <p className="font-cute text-sm text-fufu-text mb-2">📊 健康检测结果</p>
          <div className="space-y-1">
            {validateResults.map((r: any) => (
              <div key={r.id} className="flex items-center gap-2 text-xs font-body">
                <HealthDot status={r.status === 'ok' ? 'ok' : r.status === 'error' ? 'error' : 'warning'} />
                <span className="text-fufu-text truncate flex-1">{r.name}</span>
                <span className="text-fufu-text-muted">{r.latency}s</span>
                {r.health?.success_rate !== undefined && (
                  <span className="text-fufu-text-muted">成功率 {r.health.success_rate}%</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* RSS 预览 */}
      <div className="mb-4 p-4 rounded-fufu-card bg-white border">
        <p className="font-cute text-sm text-fufu-text mb-2 flex items-center gap-1">
          <MagnifyingGlass size={14} /> RSS 链接预览
        </p>
        <div className="flex gap-2">
          <input
            className="fufu-input text-sm flex-1"
            value={rssPreviewUrl}
            onChange={(e) => setRssPreviewUrl(e.target.value)}
            placeholder="粘贴 RSS 链接，实时检测可用性..."
          />
          <button
            className="fufu-btn-primary text-sm py-2"
            onClick={handlePreviewRss}
            disabled={rssPreviewLoading || !rssPreviewUrl.trim()}
          >
            {rssPreviewLoading ? '检测中...' : '检测'}
          </button>
        </div>
        {rssPreviewResult && (
          <div className={`mt-2 p-3 rounded-fufu text-xs font-body ${
            rssPreviewResult.status === 'ok' ? 'bg-green-50 text-green-700' :
            rssPreviewResult.status === 'warning' ? 'bg-amber-50 text-amber-700' :
            'bg-red-50 text-red-700'
          }`}>
            <p>状态: {rssPreviewResult.status} | 条目数: {rssPreviewResult.entry_count ?? 0} | 延迟: {rssPreviewResult.latency ?? '?'}s</p>
            {rssPreviewResult.issues?.map((iss: any, i: number) => (
              <p key={i} className="mt-1">• [{iss.type}] {iss.detail}</p>
            ))}
          </div>
        )}
      </div>

      {/* Add form */}
      <AnimatePresence>
        {showForm && (
          <motion.form
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="fufu-card p-6 mb-6 overflow-hidden"
            onSubmit={handleSubmit}
          >
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="font-cute text-sm text-fufu-text/60 block mb-1">
                  名称
                </label>
                <input
                  className="fufu-input"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="给订阅源起个名字吧～"
                  required
                />
              </div>
              <div>
                <label className="font-cute text-sm text-fufu-text/60 block mb-1">
                  类型
                </label>
                <select
                  className="fufu-input"
                  value={form.source_type}
                  onChange={(e) =>
                    setForm({ ...form, source_type: e.target.value as 'rss' | 'web' })
                  }
                >
                  <option value="rss">RSS 订阅</option>
                  <option value="web">网页抓取</option>
                </select>
              </div>
              <div className="col-span-2">
                <label className="font-cute text-sm text-fufu-text/60 block mb-1">
                  URL 地址
                </label>
                <input
                  className="fufu-input"
                  type="url"
                  value={form.url}
                  onChange={(e) => setForm({ ...form, url: e.target.value })}
                  placeholder="https://example.com/rss"
                  required
                />
              </div>
              <div>
                <label className="font-cute text-sm text-fufu-text/60 block mb-1">
                  分组（可选）
                </label>
                <input
                  className="fufu-input"
                  value={form.folder}
                  onChange={(e) => setForm({ ...form, folder: e.target.value })}
                  placeholder="如：科技、设计..."
                />
              </div>
            </div>
            <div className="flex gap-3 mt-4">
              <button type="submit" className="fufu-btn-primary" disabled={createSource.isPending}>
                {createSource.isPending ? '添加中...' : '✨ 添加'}
              </button>
              <button
                type="button"
                className="fufu-btn bg-fufu-cream text-fufu-text/50"
                onClick={() => setShowForm(false)}
              >
                取消
              </button>
            </div>
          </motion.form>
        )}
      </AnimatePresence>

      {/* Sources list */}
      {showLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="fufu-card p-5">
              <div className="skeleton h-5 w-48 rounded mb-2" />
              <div className="skeleton h-4 w-80 rounded" />
            </div>
          ))}
        </div>
      ) : safeSources.length === 0 ? (
        <div className="text-center py-20">
          <p className="font-cute text-6xl mb-4">📭</p>
          <p className="font-cute text-xl text-fufu-text/60">
            还没有订阅源哦～
          </p>
          <p className="font-body text-sm text-fufu-text/40 mt-2">
            点击「添加订阅」开始你的阅读之旅吧！
          </p>
        </div>
      ) : (
        <AnimatePresence mode="popLayout">
          <div className="space-y-3">
            {safeSources.map((s) => (
              <motion.div
                key={s.id}
                layout
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: 0.25 }}
              >
                {editingId === s.id ? (
                  /* ---- Edit mode ---- */
                  <div className="fufu-card p-5 space-y-3 border-2 border-fufu-peach/40">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="font-cute text-xs text-fufu-text/50 block mb-1">名称</label>
                        <input
                          className="fufu-input text-sm py-2"
                          value={editForm.name}
                          onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                        />
                      </div>
                      <div>
                        <label className="font-cute text-xs text-fufu-text/50 block mb-1">类型</label>
                        <select
                          className="fufu-input text-sm py-2"
                          value={editForm.source_type}
                          onChange={(e) => setEditForm({ ...editForm, source_type: e.target.value as 'rss' | 'web' })}
                        >
                          <option value="rss">RSS 订阅</option>
                          <option value="web">网页抓取</option>
                        </select>
                      </div>
                      <div className="col-span-2">
                        <label className="font-cute text-xs text-fufu-text/50 block mb-1">URL 地址</label>
                        <input
                          className="fufu-input text-sm py-2"
                          value={editForm.url}
                          onChange={(e) => setEditForm({ ...editForm, url: e.target.value })}
                        />
                      </div>
                      <div>
                        <label className="font-cute text-xs text-fufu-text/50 block mb-1">分组</label>
                        <input
                          className="fufu-input text-sm py-2"
                          value={editForm.folder}
                          onChange={(e) => setEditForm({ ...editForm, folder: e.target.value })}
                          placeholder="默认分组"
                        />
                      </div>
                    </div>
                    <div className="flex items-center gap-2 pt-2 border-t border-fufu-pink-soft/20">
                      <button
                        onClick={saveEdit}
                        disabled={updateSource.isPending}
                        className="fufu-btn-primary text-sm py-2 px-4 flex items-center gap-1.5"
                      >
                        <Check size={16} /> {updateSource.isPending ? '保存中...' : '保存'}
                      </button>
                      <button
                        onClick={cancelEdit}
                        className="fufu-btn bg-fufu-cream text-fufu-text/50 text-sm py-2 px-4 flex items-center gap-1.5"
                      >
                        <X size={16} /> 取消
                      </button>
                    </div>
                  </div>
                ) : (
                  /* ---- View mode ---- */
                  <ClickRippleWrapper className="fufu-card p-5 flex items-center gap-4">
                    <div className="p-3 rounded-fufu bg-fufu-pink-soft/30">
                      {s.source_type === 'rss' ? (
                        <Rss size={24} className="text-fufu-peach" />
                      ) : (
                        <Globe size={24} className="text-fufu-peach" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-cute text-base text-fufu-text">
                        {s.name}
                      </h3>
                      <p className="font-body text-xs text-fufu-text/60 truncate">
                        {s.url}
                      </p>
                      {s.folder && (() => {
                        const cat = categoryIcons[s.folder] || { icon: '📁', color: '#D0C8E0' };
                        return (
                          <span className="fufu-tag mt-1 font-cute text-xs"
                            style={{ backgroundColor: cat.color + '20', color: cat.color }}>
                            {cat.icon} {s.folder}
                          </span>
                        );
                      })()}
                      <div className="flex items-center gap-2 mt-1">
                        <HealthDot status="unknown" />
                        {s.last_fetched_at && (
                          <span className="text-xs text-fufu-text/50">
                            上次: {new Date(s.last_fetched_at).toLocaleString('zh-CN')}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        className="p-2 rounded-full hover:bg-fufu-pink-soft/20 text-fufu-text/40 hover:text-fufu-peach transition-all"
                        onClick={() => startEdit(s)}
                        title="编辑"
                      >
                        <PencilSimple size={18} />
                      </button>
                      <button
                        className="p-2 rounded-full hover:bg-fufu-pink-soft/20 text-fufu-text/40 hover:text-fufu-peach transition-all"
                        onClick={() => fetchSource.mutate(s.id)}
                        disabled={fetchSource.isPending}
                        title="立即抓取"
                      >
                        <ArrowClockwise
                          size={20}
                          className={fetchSource.variables === s.id ? 'animate-spin' : ''}
                        />
                      </button>
                      <button
                        className="p-2 rounded-full hover:bg-red-50 text-fufu-text/30 hover:text-red-400 transition-all"
                        onClick={() => {
                          if (window.confirm(`确定要删除「${s.name}」吗？`)) {
                            deleteSource.mutate(s.id);
                          }
                        }}
                      >
                        <Trash size={20} />
                      </button>
                    </div>
                  </ClickRippleWrapper>
                )}
              </motion.div>
            ))}
          </div>
        </AnimatePresence>
      )}
    </div>
  );
}
