import { useNavigate } from 'react-router-dom';
import MetricCard from '../components/MetricCard';
import SectionHeader from '../components/SectionHeader';
import StabilityMonitor from '../components/StabilityMonitor';
import { useHypothesisQueue, useMPCCycles, useRoutingHistory, useConstraints } from '../api/hooks';

export default function Overview() {
  const navigate = useNavigate();
  const hypotheses = useHypothesisQueue(10);
  const cycles = useMPCCycles(undefined, 10);
  const routing = useRoutingHistory(10);
  const constraints = useConstraints();

  const hypCount = hypotheses.data?.total ?? 0;
  const cycleCount = cycles.data?.length ?? 0;
  const routeCount = routing.data?.length ?? 0;
  const constraintCount = constraints.data?.length ?? 0;

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Overview</h1>
        <p className="text-brand-muted">Governed agentic inference platform dashboard</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="cursor-pointer hover:opacity-80 transition-opacity" onClick={() => navigate('/hypotheses')}>
          <MetricCard label="Hypotheses (queue)" value={hypCount} />
        </div>
        <div className="cursor-pointer hover:opacity-80 transition-opacity" onClick={() => navigate('/classification')}>
          <MetricCard label="Constraints" value={constraintCount} />
        </div>
        <div className="cursor-pointer hover:opacity-80 transition-opacity" onClick={() => navigate('/mpc')}>
          <MetricCard label="MPC Cycles" value={cycleCount} sub="recent" />
        </div>
        <div className="cursor-pointer hover:opacity-80 transition-opacity" onClick={() => navigate('/hardware')}>
          <MetricCard label="Routing Decisions" value={routeCount} sub="recent" />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <StabilityMonitor />

        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Recent Hypotheses</SectionHeader>
          {hypotheses.data?.hypotheses.length === 0 ? (
            <p className="text-brand-muted text-sm">No hypotheses in queue.</p>
          ) : (
            <div className="space-y-2">
              {hypotheses.data?.hypotheses.slice(0, 5).map(h => (
                <div key={h.hypothesis_id} className="text-sm text-white truncate cursor-pointer hover:text-white" onClick={() => navigate(`/hypotheses/${h.hypothesis_id}`)}>
                  {h.claim}
                  <span className="text-brand-muted ml-2">{h.geometric_stability_score.toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Recent MPC Cycles</SectionHeader>
          {(cycles.data ?? []).length === 0 ? (
            <p className="text-brand-muted text-sm">No MPC cycles.</p>
          ) : (
            <div className="space-y-2">
              {cycles.data?.slice(0, 5).map(c => (
                <div key={c.cycle_id} className="flex justify-between text-sm cursor-pointer hover:text-white" onClick={() => navigate(`/mpc/cycles/${c.cycle_id}`)}>
                  <span className="text-white">{c.cluster_id}</span>
                  <span className="text-brand-muted">H={c.horizon} {c.suspended ? '(suspended)' : ''}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Recent Routing</SectionHeader>
          {(routing.data ?? []).length === 0 ? (
            <p className="text-brand-muted text-sm">No routing decisions.</p>
          ) : (
            <div className="space-y-2">
              {routing.data?.slice(0, 5).map(r => (
                <div key={r.routing_id} className="flex justify-between text-sm">
                  <span className="text-white">{r.tier_assignment}</span>
                  <span className="text-brand-muted">{r.substrate} ({r.confidence_score.toFixed(2)})</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
