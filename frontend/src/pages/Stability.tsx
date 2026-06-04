import { useState } from 'react';
import { useStabilityScores, useStabilityThresholds, useUpdateThreshold } from '../api/hooks';
import SectionHeader from '../components/SectionHeader';
import MetricCard from '../components/MetricCard';
import Badge from '../components/Badge';
import LoadingState from '../components/LoadingState';

export default function Stability() {
  const { data: scores, isLoading } = useStabilityScores(undefined, 50);
  const { data: thresholds } = useStabilityThresholds();
  const updateThreshold = useUpdateThreshold();
  const [newThreshold, setNewThreshold] = useState('');
  const [expandedEndpoint, setExpandedEndpoint] = useState<string | null>(null);

  const records = scores ?? [];
  const threshold = thresholds?.stability_threshold ?? 0.7;

  const avgScore = records.length > 0
    ? records.reduce((sum, r) => sum + r.stability_score, 0) / records.length
    : 0;

  const stateDistribution = records.reduce((acc, r) => {
    acc[r.stability_state] = (acc[r.stability_state] ?? 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const endpoints = [...new Set(records.map(r => r.endpoint))];
  const endpointStats = endpoints.map(ep => {
    const epRecords = records.filter(r => r.endpoint === ep);
    const avg = epRecords.reduce((s, r) => s + r.stability_score, 0) / epRecords.length;
    const recent = epRecords.slice(0, 5);
    const first = recent[0];
    const last = recent[recent.length - 1];
    const trend = (recent.length >= 2 && first && last)
      ? first.stability_score > last.stability_score ? 'improving' : first.stability_score < last.stability_score ? 'degrading' : 'stable'
      : 'stable';
    return { endpoint: ep, count: epRecords.length, avg, trend, records: epRecords };
  });

  const sustainedUnstable = records.length >= 5 &&
    records.slice(0, 5).every(r => r.stability_score < threshold);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Stability</h1>
          <p className="text-brand-muted">Geometric stability measurement across all LLM call sites</p>
        </div>
        {sustainedUnstable && (
          <div className="bg-red-900 border border-red-700 rounded-lg px-4 py-2">
            <span className="text-red-200 text-sm font-bold">Sustained instability detected</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Avg Score" value={avgScore.toFixed(3)} />
        <MetricCard label="Threshold" value={threshold.toString()} />
        <MetricCard label="Total Calls" value={records.length} />
        <MetricCard label="Endpoints" value={endpoints.length} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Score Distribution (last {records.length})</SectionHeader>
          {isLoading ? <LoadingState /> : (
            <div className="flex gap-0.5 items-end h-24">
              {records.map((r, i) => (
                <div
                  key={i}
                  className={`flex-1 rounded-t-sm ${r.stability_score >= threshold ? 'bg-green-500' : 'bg-red-500'}`}
                  style={{ height: `${Math.max(4, r.stability_score * 96)}px` }}
                  title={`${r.endpoint}: ${r.stability_score.toFixed(3)} (${r.stability_state})`}
                />
              ))}
            </div>
          )}
        </div>

        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>State Distribution</SectionHeader>
          <div className="space-y-2">
            {Object.entries(stateDistribution).map(([state, count]) => (
              <div key={state} className="flex items-center justify-between">
                <Badge variant={state} />
                <div className="flex-1 mx-3">
                  <div className="h-2 bg-brand-surface rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${state.startsWith('stable') ? 'bg-green-500' : 'bg-red-500'}`}
                      style={{ width: `${(count / Math.max(records.length, 1)) * 100}%` }}
                    />
                  </div>
                </div>
                <span className="text-sm text-white w-8 text-right">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Per-Endpoint Breakdown</SectionHeader>
        <div className="space-y-1">
          {endpointStats.map(ep => (
            <div key={ep.endpoint}>
              <div
                className={`flex items-center justify-between text-sm px-3 py-2 rounded cursor-pointer transition-colors ${expandedEndpoint === ep.endpoint ? 'bg-brand-surface border border-white/10' : 'hover:bg-brand-surface border border-transparent'}`}
                onClick={() => setExpandedEndpoint(expandedEndpoint === ep.endpoint ? null : ep.endpoint)}
              >
                <span className="text-white">{ep.endpoint}</span>
                <div className="flex items-center gap-4">
                  <span className="text-brand-muted">{ep.count} calls</span>
                  <span className="text-white">{ep.avg.toFixed(3)}</span>
                  <Badge variant={ep.avg >= threshold ? 'stable_pass' : 'unstable_pass'}>
                    {ep.trend}
                  </Badge>
                  <span className="text-brand-muted text-xs">{expandedEndpoint === ep.endpoint ? '▲' : '▼'}</span>
                </div>
              </div>

              {expandedEndpoint === ep.endpoint && (
                <div className="ml-4 mt-1 mb-3 p-3 bg-brand-dark border border-brand-border rounded">
                  <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">Recent Calls</div>
                  <div className="space-y-1">
                    {ep.records.slice(0, 10).map((r, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <div
                            className={`w-2 h-2 rounded-full ${r.stability_score >= threshold ? 'bg-green-500' : 'bg-red-500'}`}
                          />
                          <span className="text-white">{r.stability_score.toFixed(3)}</span>
                          <Badge variant={r.stability_state} />
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-brand-muted">{r.model}</span>
                          <span className="text-brand-muted">{new Date(r.created_at).toLocaleString()}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-2 pt-2 border-t border-brand-border flex gap-4 text-xs text-brand-muted">
                    <span>Method: {ep.records[0]?.stability_method}</span>
                    <span>Threshold: {ep.records[0]?.stability_threshold}</span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Threshold Configuration</SectionHeader>
        <div className="flex items-center gap-4">
          <span className="text-sm text-brand-muted">Current: {threshold}</span>
          <input
            type="number"
            step="0.05"
            min="0"
            max="1"
            value={newThreshold}
            onChange={e => setNewThreshold(e.target.value)}
            placeholder="New threshold"
            className="bg-brand-surface border border-brand-border rounded px-3 py-1.5 text-sm text-white w-32"
          />
          <button
            onClick={() => {
              const val = parseFloat(newThreshold);
              if (!isNaN(val) && val >= 0 && val <= 1) {
                updateThreshold.mutate(val);
                setNewThreshold('');
              }
            }}
            disabled={updateThreshold.isPending}
            className="px-4 py-1.5 bg-brand-primary text-white rounded text-sm hover:opacity-90 disabled:opacity-50"
          >
            Update
          </button>
        </div>
      </div>
    </div>
  );
}
