import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import ModeIndicator from './components/ModeIndicator';

import Overview from './pages/Overview';
import Hypotheses from './pages/Hypotheses';
import Classification from './pages/Classification';
import MPC from './pages/MPC';
import Hardware from './pages/Hardware';
import LaunchpadIntelligence from './pages/LaunchpadIntelligence';
import Stability from './pages/Stability';
import Admin from './pages/Admin';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

const NAV_ITEMS = [
  { to: '/', label: 'Overview' },
  { to: '/hypotheses', label: 'Hypotheses' },
  { to: '/classification', label: 'Classification' },
  { to: '/mpc', label: 'MPC' },
  { to: '/hardware', label: 'Hardware' },
  { to: '/launchpad', label: 'Launchpad' },
  { to: '/stability', label: 'Stability' },
  { to: '/admin', label: 'Admin' },
];

function navClass({ isActive }: { isActive: boolean }) {
  const base = 'px-3 py-2 text-sm font-medium transition-colors';
  return isActive
    ? `${base} text-white border-b-2 border-brand-primary`
    : `${base} text-brand-muted hover:text-white`;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary>
          <div className="min-h-screen bg-brand-dark flex flex-col">
            <header className="bg-brand-dark border-b border-brand-border">
              <div className="max-w-7xl mx-auto px-6 lg:px-8">
                <div className="flex items-center justify-between h-14">
                  <div className="flex items-center gap-4">
                    <h1 className="text-lg font-bold text-white" style={{ fontFamily: 'Red Hat Display' }}>
                      GeoLux
                    </h1>
                    <ModeIndicator />
                  </div>
                </div>
                <nav className="flex gap-1 -mb-px">
                  {NAV_ITEMS.map(({ to, label }) => (
                    <NavLink key={to} to={to} end={to === '/'} className={navClass}>
                      {label}
                    </NavLink>
                  ))}
                </nav>
              </div>
            </header>

            <main className="flex-1">
              <Routes>
                <Route path="/" element={<Overview />} />
                <Route path="/hypotheses" element={<Hypotheses />} />
                <Route path="/classification" element={<Classification />} />
                <Route path="/mpc" element={<MPC />} />
                <Route path="/hardware" element={<Hardware />} />
                <Route path="/launchpad" element={<LaunchpadIntelligence />} />
                <Route path="/stability" element={<Stability />} />
                <Route path="/admin" element={<Admin />} />
              </Routes>
            </main>

            <footer className="border-t border-brand-border py-4">
              <div className="max-w-7xl mx-auto px-6 lg:px-8 flex items-center justify-between">
                <span className="text-xs text-brand-muted">GeoLux — Governed Agentic Inference Platform</span>
                <span className="text-xs text-brand-muted">Red Hat Intel AI Platform</span>
              </div>
            </footer>
          </div>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
