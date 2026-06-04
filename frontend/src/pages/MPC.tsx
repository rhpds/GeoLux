import { useNavigate } from 'react-router-dom';
import { useMPCCycles } from '../api/hooks';
import SectionHeader from '../components/SectionHeader';
import Badge from '../components/Badge';
import LoadingState from '../components/LoadingState';
import EmptyState from '../components/EmptyState';

export default function MPC() {
  const navigate = useNavigate();
  const { data: cycles, isLoading } = useMPCCycles(undefined, 20);
  const records = cycles ?? [];

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>LLM-MPC Controller</h1>
        <p className="text-brand-muted">Model Predictive Control — prediction trace and optimization history</p>
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Recent Cycles</SectionHeader>
        {isLoading ? <LoadingState /> : records.length === 0 ? <EmptyState message="No MPC cycles recorded." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-brand-muted uppercase tracking-wider border-b border-brand-border">
                  <th className="text-left py-2">Cluster</th>
                  <th className="text-right py-2">Horizon</th>
                  <th className="text-right py-2">Score</th>
                  <th className="text-center py-2">Adjusted</th>
                  <th className="text-center py-2">Status</th>
                  <th className="text-right py-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {records.map(c => (
                  <tr key={c.cycle_id} className="border-b border-brand-surface hover:bg-brand-surface cursor-pointer" onClick={() => navigate(`/mpc/cycles/${c.cycle_id}`)}>
                    <td className="py-2 text-white">{c.cluster_id}</td>
                    <td className="py-2 text-right text-white">{c.horizon}</td>
                    <td className="py-2 text-right text-white">{c.optimization_score.toFixed(2)}</td>
                    <td className="py-2 text-center">
                      {c.horizon_adjusted ? <Badge variant="unstable_pass">adjusted</Badge> : <span className="text-brand-muted">-</span>}
                    </td>
                    <td className="py-2 text-center">
                      {c.suspended ? <Badge variant="fail">suspended</Badge> : <Badge variant="pass">active</Badge>}
                    </td>
                    <td className="py-2 text-right text-brand-muted">{new Date(c.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
