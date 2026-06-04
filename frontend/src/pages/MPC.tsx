import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useMPCCycles } from '../api/hooks';
import SectionHeader from '../components/SectionHeader';
import Badge from '../components/Badge';
import MetricCard from '../components/MetricCard';
import LoadingState from '../components/LoadingState';
import EmptyState from '../components/EmptyState';

export default function MPC() {
  const navigate = useNavigate();
  const [selectedCluster, setSelectedCluster] = useState('');

  const { data: stats } = useQuery({
    queryKey: ['mpc-stats'],
    queryFn: async () => {
      const r = await fetch('/mpc/stats');
      return r.ok ? r.json() : null;
    },
    refetchInterval: 30_000,
  });

  const { data: cycles, isLoading } = useMPCCycles(selectedCluster || undefined, 30);
  const records = cycles ?? [];

  const clusterList: Array<{ cluster: string; cycles: number; avg_horizon: number; suspended: number; last_cycle: string }> = stats?.clusters ?? [];

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>LLM-MPC Controller</h1>
        <p className="text-brand-muted">Model Predictive Control — receding horizon planning per cluster</p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="Total Cycles" value={stats.total} />
          <MetricCard label="Active" value={stats.active} />
          <MetricCard label="Suspended" value={stats.suspended} />
          <MetricCard label="Horizon Adjusted" value={stats.horizon_adjusted} />
        </div>
      )}

      {clusterList.length > 0 && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Clusters with MPC Active ({clusterList.length})</SectionHeader>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
            {clusterList.map(c => (
              <button key={c.cluster}
                onClick={() => setSelectedCluster(selectedCluster === c.cluster ? '' : c.cluster)}
                className={`text-left p-3 rounded-lg border transition-colors ${selectedCluster === c.cluster ? 'border-brand-primary bg-brand-primary/10' : 'border-brand-border bg-brand-surface hover:border-white/20'}`}>
                <div className="text-sm text-white font-medium">{c.cluster}</div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-brand-muted">{c.cycles} cycles</span>
                  <span className="text-xs text-brand-muted">h={c.avg_horizon}</span>
                  {c.suspended > 0 && <Badge variant="fail">{c.suspended} suspended</Badge>}
                </div>
              </button>
            ))}
          </div>
          {selectedCluster && (
            <button onClick={() => setSelectedCluster('')}
              className="text-xs text-brand-muted hover:text-white mt-2 transition-colors">
              Clear filter
            </button>
          )}
        </div>
      )}

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>
          {selectedCluster ? `Cycles for ${selectedCluster}` : 'Recent Cycles'} ({records.length})
        </SectionHeader>
        {isLoading ? <LoadingState /> : records.length === 0 ? <EmptyState message="No MPC cycles." /> : (
          <div className="space-y-1">
            {records.map(c => (
              <div key={c.cycle_id}
                className="flex items-center justify-between text-sm px-3 py-2 rounded cursor-pointer bg-brand-surface/50 hover:bg-brand-surface border border-transparent hover:border-white/10 transition-colors"
                onClick={() => navigate(`/mpc/cycles/${c.cycle_id}`)}>
                <div className="flex items-center gap-3">
                  <span className="text-white font-medium">{c.cluster_id}</span>
                  <span className="text-brand-muted">h={c.horizon}</span>
                  {c.horizon_adjusted && <Badge variant="unstable_pass">adjusted</Badge>}
                  {c.suspended ? <Badge variant="fail">suspended</Badge> : <Badge variant="pass">active</Badge>}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-brand-muted text-xs">score: {c.optimization_score.toFixed(2)}</span>
                  <span className="text-brand-muted text-xs">
                    {new Date(c.created_at).toLocaleString(undefined, { month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
