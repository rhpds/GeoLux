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
import Governance from './pages/Governance';
import Admin from './pages/Admin';
import HypothesisDetail from './pages/HypothesisDetail';
import MPCCycleDetail from './pages/MPCCycleDetail';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

const NAV_ITEMS = [
  { to: '/', label: 'Overview', end: true },
  { to: '/hypotheses', label: 'Hypotheses' },
  { to: '/governance', label: 'Governance' },
  { to: '/classification', label: 'Classification' },
  { to: '/mpc', label: 'MPC' },
  { to: '/hardware', label: 'Hardware' },
  { to: '/launchpad', label: 'Launchpad' },
  { to: '/stability', label: 'Stability' },
  { to: '/admin', label: 'Admin' },
];

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <div className="min-h-screen flex flex-col" style={{ backgroundColor: 'var(--color-brand-dark)' }}>
            <header style={{ backgroundColor: 'var(--color-brand-dark)' }} className="text-white">
              <div className="max-w-7xl mx-auto px-6 lg:px-8">
                <div className="flex items-center h-14 gap-6">
                  <div className="flex items-center gap-3 shrink-0">
                    <img src="/logos/redhat.svg" alt="Red Hat" style={{ height: '28px' }} />
                    <span className="text-brand-muted">|</span>
                    <span className="text-lg font-semibold tracking-tight" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>GeoLux</span>
                  </div>
                  <nav className="flex gap-1">
                    {NAV_ITEMS.map(({ to, label, end }) => (
                      <NavLink key={to} to={to} end={end}
                        className={({ isActive }) =>
                          `px-3 py-1.5 rounded text-sm font-medium transition ${isActive ? 'bg-white/15 text-white' : 'text-brand-muted hover:text-white hover:bg-white/10'}`
                        }>
                        {label}
                      </NavLink>
                    ))}
                  </nav>
                  <div className="ml-auto">
                    <ModeIndicator />
                  </div>
                </div>
              </div>
            </header>

            <div className="h-0.5 flex">
              <div className="flex-1" style={{ backgroundColor: 'var(--color-brand-primary)' }} />
              <div className="flex-1" style={{ backgroundColor: 'var(--color-brand-secondary)' }} />
            </div>

            <main className="flex-1">
              <Routes>
                <Route path="/" element={<Overview />} />
                <Route path="/hypotheses/:id" element={<HypothesisDetail />} />
                <Route path="/hypotheses" element={<Hypotheses />} />
                <Route path="/classification" element={<Classification />} />
                <Route path="/mpc/cycles/:id" element={<MPCCycleDetail />} />
                <Route path="/mpc" element={<MPC />} />
                <Route path="/hardware" element={<Hardware />} />
                <Route path="/launchpad" element={<LaunchpadIntelligence />} />
                <Route path="/governance" element={<Governance />} />
                <Route path="/stability" element={<Stability />} />
                <Route path="/admin" element={<Admin />} />
              </Routes>
            </main>

            <footer style={{ backgroundColor: 'var(--color-brand-dark)' }} className="border-t border-brand-border text-brand-muted text-sm py-5">
              <div className="max-w-7xl mx-auto px-6 lg:px-8 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <img src="/logos/redhat.svg" alt="" style={{ height: '16px', opacity: 0.6 }} />
                </div>
                <span>Governed Agentic Inference on Red Hat OpenShift</span>
              </div>
            </footer>
          </div>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
