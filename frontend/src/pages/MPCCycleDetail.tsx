import { useParams, NavLink } from 'react-router-dom';
import { useMPCCycle } from '../api/hooks';
import MetricCard from '../components/MetricCard';
import SectionHeader from '../components/SectionHeader';
import Badge from '../components/Badge';
import LoadingState from '../components/LoadingState';

export default function MPCCycleDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: cycle, isLoading } = useMPCCycle(id ?? '');

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
        <LoadingState message="Loading MPC cycle..." />
      </div>
    );
  }

  if (!cycle) {
    return (
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
        <NavLink to="/mpc" className="text-brand-muted hover:text-white text-sm transition-colors">
          &larr; MPC Cycles
        </NavLink>
        <p className="text-brand-muted mt-6">MPC cycle not found.</p>
      </div>
    );
  }

  const profile = cycle.geometric_stability_profile;
  const maxScore = profile?.scores?.length ? Math.max(...profile.scores, 0.01) : 1;

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <NavLink to="/mpc" className="text-brand-muted hover:text-white text-sm transition-colors">
        &larr; MPC Cycles
      </NavLink>

      <div className="flex items-start gap-4">
        <h1 className="text-3xl font-bold text-white flex-1" style={{ fontFamily: 'Red Hat Display' }}>
          {cycle.cluster_id}
        </h1>
        {cycle.suspended ? <Badge variant="fail">suspended</Badge> : <Badge variant="pass">active</Badge>}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Horizon" value={cycle.horizon} />
        <MetricCard label="Optimization Score" value={cycle.optimization_score.toFixed(2)} />
        <MetricCard label="Stability Mean" value={profile?.mean?.toFixed(3) ?? 'N/A'} />
        <MetricCard label="Created At" value={new Date(cycle.created_at).toLocaleString()} />
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Current State</SectionHeader>
        {Object.keys(cycle.current_state).length === 0 ? (
          <p className="text-brand-muted text-sm">No state data available.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <tbody>
                {Object.entries(cycle.current_state).map(([key, val]) => (
                  <tr key={key} className="border-b border-brand-surface">
                    <td className="py-2 text-brand-muted font-medium w-1/3">{key}</td>
                    <td className="py-2 text-white">{typeof val === 'object' ? JSON.stringify(val) : String(val)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Predictions</SectionHeader>
        {cycle.predictions.length === 0 ? (
          <p className="text-brand-muted text-sm">No predictions available.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-brand-muted uppercase tracking-wider border-b border-brand-border">
                  <th className="text-left py-2">Step</th>
                  <th className="text-left py-2">Predicted State</th>
                  <th className="text-right py-2">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {cycle.predictions.map((p) => (
                  <tr key={p.step} className="border-b border-brand-surface">
                    <td className="py-2 text-white">{p.step}</td>
                    <td className="py-2 text-white font-mono text-xs">{JSON.stringify(p.predicted_state)}</td>
                    <td className="py-2 text-right text-white">{p.confidence.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Candidate Actions</SectionHeader>
        {cycle.candidate_actions.length === 0 ? (
          <p className="text-brand-muted text-sm">No candidate actions.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-brand-muted uppercase tracking-wider border-b border-brand-border">
                  <th className="text-left py-2">Action Type</th>
                  <th className="text-left py-2">Parameters</th>
                  <th className="text-right py-2">Score</th>
                </tr>
              </thead>
              <tbody>
                {cycle.candidate_actions.map((a) => (
                  <tr
                    key={a.action_id}
                    className={`border-b border-brand-surface ${a.action_id === cycle.selected_action_id ? 'border-l-2 border-l-green-500' : ''}`}
                  >
                    <td className="py-2 text-white">{a.action_type}</td>
                    <td className="py-2 text-white font-mono text-xs">{JSON.stringify(a.parameters)}</td>
                    <td className="py-2 text-right text-white">{a.score.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {profile?.scores?.length > 0 && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Stability Profile</SectionHeader>
          <div className="flex items-end gap-1 h-24">
            {profile.scores.map((s, i) => (
              <div
                key={i}
                className="flex-1 rounded-t"
                style={{
                  height: `${(s / maxScore) * 100}%`,
                  backgroundColor: s >= (profile.mean ?? 0) ? 'var(--color-brand-primary)' : 'var(--color-brand-secondary)',
                  minWidth: '4px',
                }}
                title={`Score: ${s.toFixed(3)}`}
              />
            ))}
          </div>
          <div className="flex justify-between text-xs text-brand-muted mt-2">
            <span>Mean: {profile.mean.toFixed(3)}</span>
            <span>Min: {profile.min.toFixed(3)}</span>
            <span>Samples: {profile.scores.length}</span>
          </div>
        </div>
      )}
    </div>
  );
}
