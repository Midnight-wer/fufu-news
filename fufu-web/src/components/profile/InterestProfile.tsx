import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowsClockwise } from '@phosphor-icons/react';
import { fetchInterests, resetInterests, type InterestItem } from '../../api/profile';

/**
 * 我的兴趣画像 —— 自学习机制的用户可见呈现。
 *
 * 展示后端学习出的「标签 → 兴趣强度」，让用户直观看到
 * 「AI 慢慢学会了我的偏好」。权重条按 score 相对最大值的比例渲染。
 */
export default function InterestProfile() {
  const qc = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['profile', 'interests'],
    queryFn: fetchInterests,
    staleTime: 30_000,
  });

  const reset = useMutation({
    mutationFn: resetInterests,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile', 'interests'] });
    },
  });

  const items = data?.interests ?? [];
  const maxScore = items.reduce((m, it) => Math.max(m, it.score), 0) || 1;

  return (
    <div>
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-6 rounded-fufu bg-fufu-cream/60 animate-pulse" />
          ))}
        </div>
      ) : isError ? (
        <p className="font-body text-sm text-fufu-text-muted">画像读取失败，请稍后再试～</p>
      ) : items.length === 0 ? (
        <div className="text-center py-6">
          <p className="font-cute text-2xl mb-2">🧠</p>
          <p className="font-body text-sm text-fufu-text-muted">
            还没有积累兴趣数据呢～
            <br />
            多读几篇文章、收藏喜欢的内容，fufu 就能慢慢懂你啦
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.slice(0, 10).map((it: InterestItem) => (
            <div key={it.tag} className="flex items-center gap-3">
              <span className="font-cute text-sm text-fufu-text w-16 shrink-0">{it.tag}</span>
              <div className="flex-1 h-3 rounded-full bg-fufu-cream/60 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.max((it.score / maxScore) * 100, 4)}%`,
                    background:
                      'linear-gradient(to right, rgb(var(--fufu-teal)), rgb(var(--fufu-teal-deep)))',
                  }}
                />
              </div>
              <span className="font-body text-xs text-fufu-text-muted w-10 text-right shrink-0">
                {it.score.toFixed(1)}
              </span>
            </div>
          ))}
          <div className="pt-2 border-t border-fufu-pink-soft/20 flex items-center justify-between">
            <span className="font-body text-xs text-fufu-text-muted">
              共 {data?.count ?? items.length} 个兴趣标签
            </span>
            <button
              onClick={() => {
                if (window.confirm('确定要重置兴趣画像吗？fufu 会重新开始学习你的偏好～')) {
                  reset.mutate();
                }
              }}
              disabled={reset.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-fufu-btn font-cute text-xs text-fufu-text-muted hover:text-fufu-pink hover:bg-fufu-pink-soft/10 transition-all"
            >
              <ArrowsClockwise size={14} className={reset.isPending ? 'animate-spin' : ''} />
              {reset.isPending ? '重置中...' : '重置画像'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
