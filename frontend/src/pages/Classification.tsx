import { useState } from 'react';
import { useConstraints, useRecentClassifications } from '../api/hooks';
import SectionHeader from '../components/SectionHeader';
import Badge from '../components/Badge';
import LoadingState from '../components/LoadingState';
import EmptyState from '../components/EmptyState';

const STAGES = [
  '', 'cluster-health', 'namespace-ready', 'deployment-ready', 'route-ready',
  'vm-runtime-ready', 'run-created', 'provision-complete', 'storage-clone-ready',
  'smoke-test-ready', 'showroom-healthy', 'model-endpoint-ready',
];

export default function Classification() {
  const [stage, setStage] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { data: constraints, isLoading: loadingConstraints } = useConstraints(stage || undefined);
  const { data: recent, isLoading: loadingRecent } = useRecentClassifications(stage || undefined, 20);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Classification</h1>
        <p className="text-brand-muted">Formal typed constraint definitions and recent evaluation results</p>
      </div>

      <div className="flex items-center gap-4">
        <label className="text-xs text-brand-muted uppercase tracking-wider font-bold">Stage</label>
        <select
          value={stage}
          onChange={e => { setStage(e.target.value); setExpandedId(null); }}
          className="bg-brand-card border border-brand-border rounded px-3 py-1.5 text-sm text-white"
        >
          <option value="">All stages</option>
          {STAGES.filter(Boolean).map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Constraint Definitions ({constraints?.length ?? 0})</SectionHeader>
        {loadingConstraints ? <LoadingState /> : !constraints?.length ? <EmptyState message="No constraints defined." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-brand-muted uppercase tracking-wider border-b border-brand-border">
                  <th className="text-left py-2">ID</th>
                  <th className="text-left py-2">Name</th>
                  <th className="text-left py-2">Stage</th>
                  <th className="text-center py-2">Type</th>
                  <th className="text-center py-2">Severity</th>
                  <th className="text-right py-2">Version</th>
                </tr>
              </thead>
              <tbody>
                {constraints.map(c => (
                  <tr key={c.constraint_id} className="border-b border-brand-surface hover:bg-brand-surface">
                    <td className="py-2 text-white font-mono text-xs">{c.constraint_id}</td>
                    <td className="py-2 text-white">{c.constraint_name}</td>
                    <td className="py-2 text-brand-muted">{c.stage}</td>
                    <td className="py-2 text-center"><Badge variant={c.assertion_type}>{c.assertion_type}</Badge></td>
                    <td className="py-2 text-center"><Badge variant={c.severity} /></td>
                    <td className="py-2 text-right text-brand-muted">v{c.version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Recent Classifications ({recent?.length ?? 0})</SectionHeader>
        {loadingRecent ? <LoadingState /> : !recent?.length ? <EmptyState message="No recent classifications." /> : (
          <div className="space-y-1">
            {recent.map(r => (
              <div key={r.classification_id}>
                <div
                  className={`flex items-center justify-between text-sm px-3 py-2 rounded cursor-pointer transition-colors ${expandedId === r.classification_id ? 'bg-brand-surface border border-white/10' : 'bg-brand-surface/50 hover:bg-brand-surface border border-transparent'}`}
                  onClick={() => setExpandedId(expandedId === r.classification_id ? null : r.classification_id)}
                >
                  <div className="flex items-center gap-3">
                    <Badge variant={r.result} />
                    <span className="text-white font-mono text-xs">{r.constraint_id}</span>
                    <span className="text-brand-muted text-xs truncate max-w-[200px]">{r.evidence_bundle_id}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-brand-muted">{r.confidence_score.toFixed(2)}</span>
                    {r.llm_interpretation_used && <Badge variant="macro">LLM</Badge>}
                    <span className="text-xs text-brand-muted">{new Date(r.created_at).toLocaleString()}</span>
                    <span className="text-brand-muted text-xs">{expandedId === r.classification_id ? '▲' : '▼'}</span>
                  </div>
                </div>

                {expandedId === r.classification_id && (
                  <div className="ml-4 mt-1 mb-3 p-3 bg-brand-dark border border-brand-border rounded text-xs">
                    <div className="text-brand-muted uppercase tracking-wider font-bold mb-2">Evidence Chain</div>
                    <div className="space-y-1">
                      {Object.entries(r.evidence_chain).map(([key, value]) => (
                        <div key={key} className="flex gap-2">
                          <span className="text-brand-muted w-32 shrink-0 font-mono">{key}</span>
                          <span className="text-white">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</span>
                        </div>
                      ))}
                    </div>
                    {r.geometric_stability_score != null && (
                      <div className="mt-2 pt-2 border-t border-brand-border flex gap-4">
                        <span className="text-brand-muted">Stability: {r.geometric_stability_score.toFixed(3)}</span>
                        {r.geometric_stability_state && <Badge variant={r.geometric_stability_state} />}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
