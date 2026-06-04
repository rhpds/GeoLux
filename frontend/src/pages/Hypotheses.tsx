import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { geolux } from '../api/geolux';
import SectionHeader from '../components/SectionHeader';
import Badge from '../components/Badge';
import MetricCard from '../components/MetricCard';
import LoadingState from '../components/LoadingState';
import EmptyState from '../components/EmptyState';

export default function Hypotheses() {
  const navigate = useNavigate();
  const [cluster, setCluster] = useState('');
  const [failureClass, setFailureClass] = useState('');
  const [validation, setValidation] = useState('');
  const [search, setSearch] = useState('');

  const { data: stats } = useQuery({
    queryKey: ['hypothesis-stats'],
    queryFn: geolux.getHypothesisStats,
    refetchInterval: 30_000,
  });

  const hasFilters = !!(cluster || failureClass || validation || search);

  const { data, isLoading } = useQuery({
    queryKey: ['hypotheses-search', cluster, failureClass, validation, search],
    queryFn: () => hasFilters
      ? geolux.searchHypotheses({ cluster: cluster || undefined, failure_class: failureClass || undefined, validation: validation || undefined, q: search || undefined, limit: 50 })
      : geolux.getHypothesisQueue(50),
    refetchInterval: 15_000,
  });

  const hypotheses = data?.hypotheses ?? [];

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Hypotheses</h1>
        <p className="text-brand-muted">Structured falsifiable hypotheses about observed system state</p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="Total" value={stats.total.toLocaleString()} />
          <MetricCard label="Pending" value={stats.pending.toLocaleString()} sub={`${((stats.pending / Math.max(stats.total, 1)) * 100).toFixed(0)}%`} />
          <MetricCard label="Validated" value={stats.validated} />
          <MetricCard label="Falsified" value={stats.falsified} />
        </div>
      )}

      {stats && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-brand-card border border-brand-border rounded-lg p-4">
            <SectionHeader>By Cluster</SectionHeader>
            <div className="flex flex-wrap gap-1">
              {stats.clusters.slice(0, 10).map(c => (
                <button key={c.name} onClick={() => setCluster(cluster === c.name ? '' : c.name)}
                  className={`text-xs px-2 py-1 rounded transition-colors ${cluster === c.name ? 'bg-brand-primary text-white' : 'bg-brand-surface text-brand-muted hover:text-white'}`}>
                  {c.name} <span className="opacity-60">({c.count})</span>
                </button>
              ))}
            </div>
          </div>
          <div className="bg-brand-card border border-brand-border rounded-lg p-4">
            <SectionHeader>By Failure Class</SectionHeader>
            <div className="flex flex-wrap gap-1">
              {stats.failure_classes.slice(0, 10).map(f => (
                <button key={f.name} onClick={() => setFailureClass(failureClass === f.name ? '' : f.name)}
                  className={`text-xs px-2 py-1 rounded transition-colors ${failureClass === f.name ? 'bg-brand-primary text-white' : 'bg-brand-surface text-brand-muted hover:text-white'}`}>
                  {f.name} <span className="opacity-60">({f.count})</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center gap-3">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search claims..."
          className="bg-brand-card border border-brand-border rounded px-3 py-1.5 text-sm text-white flex-1 max-w-md"
        />
        <select value={validation} onChange={e => setValidation(e.target.value)}
          className="bg-brand-card border border-brand-border rounded px-3 py-1.5 text-sm text-white">
          <option value="">All status</option>
          <option value="pending">Pending</option>
          <option value="validated">Validated</option>
          <option value="falsified">Falsified</option>
        </select>
        {hasFilters && (
          <button onClick={() => { setCluster(''); setFailureClass(''); setValidation(''); setSearch(''); }}
            className="text-xs text-brand-muted hover:text-white transition-colors px-2 py-1">
            Clear filters
          </button>
        )}
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>
          {hasFilters ? `Filtered Results (${data?.total ?? 0})` : `Queue (${data?.total ?? 0} unresolved)`}
        </SectionHeader>

        {isLoading ? <LoadingState /> : hypotheses.length === 0 ? <EmptyState message="No hypotheses match the filters." /> : (
          <div className="space-y-2">
            {hypotheses.map(h => {
              const hAny = h as unknown as Record<string, unknown>;
              const hCluster = (hAny['cluster'] as string) || '';
              const hFailure = (hAny['failure_class'] as string) || '';

              return (
                <div key={h.hypothesis_id}
                  className="bg-brand-surface border border-brand-border rounded-lg p-3 cursor-pointer hover:border-white/20 transition-colors"
                  onClick={() => navigate(`/hypotheses/${h.hypothesis_id}`)}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-sm font-medium truncate">{h.claim}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-1.5">
                        {hCluster && <span className="text-xs bg-brand-dark px-1.5 py-0.5 rounded text-brand-muted">{hCluster}</span>}
                        {hFailure && <Badge variant="fail">{hFailure}</Badge>}
                        <Badge variant={h.geometric_stability_state} />
                        {h.validation_outcome && <Badge variant={h.validation_outcome} />}
                        <span className="text-xs text-brand-muted">conf: {h.confidence_score.toFixed(1)}</span>
                      </div>
                    </div>
                    <div className="text-xs text-brand-muted whitespace-nowrap shrink-0">
                      {new Date(h.created_at).toLocaleString(undefined, { month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
