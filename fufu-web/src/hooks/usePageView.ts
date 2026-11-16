import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { reportPageView } from '../api/stats';

/**
 * 页面访问上报——路由每次切换时记录一次浏览。
 *
 * 上报失败静默忽略：统计是辅助能力，不能影响正常浏览。
 */
export function usePageViewTracking() {
  const location = useLocation();
  const lastPath = useRef<string>('');

  useEffect(() => {
    const path = location.pathname;
    if (!path || path === lastPath.current) return;
    lastPath.current = path;
    reportPageView(path).catch(() => {
      /* 上报失败不影响浏览 */
    });
  }, [location.pathname]);
}
