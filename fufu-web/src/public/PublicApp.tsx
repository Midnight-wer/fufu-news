import { useEffect, useState } from 'react';
import { HashRouter, Route, Routes, useLocation } from 'react-router-dom';
import { loadNewsSnapshot, type NewsSnapshot } from './data';
import {
  ErrorScreen,
  LoadingScreen,
  MobileNavigation,
  PublicFooter,
  PublicHeader,
} from './components';
import { ArticlePage, HomePage, HotPage, NotFoundPage, SearchPage } from './pages';
import './public.css';

function ScrollToTop() {
  const location = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, [location.pathname, location.search]);
  return null;
}

function PublicSite({ snapshot }: { snapshot: NewsSnapshot }) {
  return (
    <HashRouter>
      <ScrollToTop />
      <div className="public-shell">
        <button
          type="button"
          className="public-skip-link"
          onClick={() => document.getElementById('public-content')?.focus()}
        >
          跳至正文
        </button>
        <PublicHeader snapshot={snapshot} />
        <div id="public-content" className="public-container public-route-content" tabIndex={-1}>
          <Routes>
            <Route path="/" element={<HomePage snapshot={snapshot} />} />
            <Route path="/category/:category" element={<HomePage snapshot={snapshot} />} />
            <Route path="/article/:id" element={<ArticlePage snapshot={snapshot} />} />
            <Route path="/hot" element={<HotPage snapshot={snapshot} />} />
            <Route path="/search" element={<SearchPage snapshot={snapshot} />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </div>
        <PublicFooter snapshot={snapshot} />
        <MobileNavigation />
      </div>
    </HashRouter>
  );
}

export default function PublicApp() {
  const [snapshot, setSnapshot] = useState<NewsSnapshot | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    loadNewsSnapshot()
      .then((data) => {
        if (active) setSnapshot(data);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : '请检查网络连接后重试。');
      });
    return () => {
      active = false;
    };
  }, []);

  if (error) return <ErrorScreen message={error} />;
  if (!snapshot) return <LoadingScreen />;
  return <PublicSite snapshot={snapshot} />;
}
