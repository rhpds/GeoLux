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
    return { endpoint: ep, count: epRecords.length, avg };
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
        <MetricCard label="Methods" value={[...new Set(records.map(r => r.stability_method))].join(', ') || '--'} />
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
                  title={`${r.endpoint}: ${r.stability_score.toFixed(3)}`}
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
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-brand-muted uppercase tracking-wider border-b border-brand-border">
                <th className="text-left py-2">Endpoint</th>
                <th className="text-right py-2">Calls</th>
                <th className="text-right py-2">Avg Score</th>
                <th className="text-center py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {endpointStats.map(ep => (
                <tr key={ep.endpoint} className="border-b border-brand-surface">
                  <td className="py-2 text-white">{ep.endpoint}</td>
                  <td className="py-2 text-right text-white">{ep.count}</td>
                  <td className="py-2 text-right text-white">{ep.avg.toFixed(3)}</td>
                  <td className="py-2 text-center">
                    <Badge variant={ep.avg >= threshold ? 'stable_pass' : 'unstable_pass'}>
                      {ep.avg >= threshold ? 'stable' : 'unstable'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
