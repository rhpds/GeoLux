import { useState } from 'react';
import { useConstraints } from '../api/hooks';
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
  const { data: constraints, isLoading } = useConstraints(stage || undefined);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Classification</h1>
        <p className="text-brand-muted">Formal typed constraint definitions across 11 rubric stages</p>
      </div>

      <div className="flex items-center gap-4">
        <label className="text-xs text-brand-muted uppercase tracking-wider font-bold">Stage</label>
        <select
          value={stage}
          onChange={e => setStage(e.target.value)}
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
        {isLoading ? <LoadingState /> : !constraints?.length ? <EmptyState message="No constraints defined." /> : (
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
    </div>
  );
}
