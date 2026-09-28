import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { lazy, Suspense, useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import MainLayout from './components/layout/MainLayout';
import AuthGuard from './components/auth/AuthGuard';
import ErrorBoundary from './components/common/ErrorBoundary';
import MouseGlow from './components/effects/MouseGlow';
import MouseTrail from './components/effects/MouseTrail';
import SakuraPetals from './components/effects/SakuraPetals';
import FufuCompanion from './components/companion/FufuCompanion';
import MikuDecorations from './components/effects/MikuDecorations';
import AiChatDialog from './components/companion/AiChatDialog';
import AchievementToast from './components/achievements/AchievementToast';
import { runSelfCheck, getOfflineBanner, type CheckResult } from './lib/self-check';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const HomePage = lazy(() => import('./pages/HomePage'));
const ArticlePage = lazy(() => import('./pages/ArticlePage'));
const SourcesPage = lazy(() => import('./pages/SourcesPage'));
const FavoritesPage = lazy(() => import('./pages/FavoritesPage'));
const LaterPage = lazy(() => import('./pages/LaterPage'));
const SearchPage = lazy(() => import('./pages/SearchPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const RankingPage = lazy(() => import('./pages/RankingPage'));
const HistoryPage = lazy(() => import('./pages/HistoryPage'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
    },
  },
});

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="text-center">
        <p className="font-cute text-4xl animate-bounce">🎵</p>
        <p className="font-cute text-fufu-text-muted mt-3">正在加载来自未来的资讯哦～</p>
      </div>
    </div>
  );
}

const pageVariants = {
  initial: { opacity: 0, y: 16, scale: 0.98 },
  animate: { opacity: 1, y: 0, scale: 1 },
  exit: { opacity: 0, y: -12, scale: 0.98 },
};

function AnimatedRoutes() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        variants={pageVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={{ duration: 0.25, ease: 'easeOut' }}
      >
        <Suspense fallback={<LoadingFallback />}>
          <Routes location={location}>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<AuthGuard />}>
              <Route element={<MainLayout />}>
                <Route path="/" element={<Navigate to="/articles" replace />} />
                <Route path="/articles" element={<HomePage />} />
                <Route path="/articles/:id" element={<ArticlePage />} />
                <Route path="/sources" element={<SourcesPage />} />
                <Route path="/favorites" element={<FavoritesPage />} />
                <Route path="/later" element={<LaterPage />} />
                <Route path="/search" element={<SearchPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/ranking" element={<RankingPage />} />
                <Route path="/history" element={<HistoryPage />} />
              </Route>
            </Route>
          </Routes>
        </Suspense>
      </motion.div>
    </AnimatePresence>
  );
}

function StatusBanner({ text, type }: { text: string; type: string }) {
  const bg = type === 'error' ? 'bg-red-50 border-red-200 text-red-700' : 'bg-amber-50 border-amber-200 text-amber-700';
  return (
    <div className={`fixed top-0 left-0 right-0 z-[400] px-4 py-2 text-center font-body text-xs border-b ${bg}`}>
      {text}
    </div>
  );
}

function AppShell() {
  const [chatOpen, setChatOpen] = useState(false);
  const [banner, setBanner] = useState<{ show: boolean; text: string; type: 'warning' | 'error' | 'info' }>({ show: false, text: '', type: 'info' });

  useEffect(() => {
    runSelfCheck().then(() => setBanner(getOfflineBanner()));
  }, []);

  return (
    <>
      <SakuraPetals />
      <MikuDecorations />
      <MouseGlow />
      <MouseTrail />
      <FufuCompanion onChatOpen={() => setChatOpen(true)} />
      <AiChatDialog open={chatOpen} onClose={() => setChatOpen(false)} />
      <AchievementToast />
      {banner.show && <StatusBanner text={banner.text} type={banner.type} />}
      <ErrorBoundary>
        <AnimatedRoutes />
      </ErrorBoundary>
    </>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
