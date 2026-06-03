import { useRoutingHistory, useTiers } from '../api/hooks';
import SectionHeader from '../components/SectionHeader';
import Badge from '../components/Badge';
import LoadingState from '../components/LoadingState';
import EmptyState from '../components/EmptyState';

export default function Hardware() {
  const { data: tiers } = useTiers();
  const { data: history, isLoading } = useRoutingHistory(50);
  const records = history ?? [];
  const tierDefs = tiers?.tiers ?? [];

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Hardware — Deepfield</h1>
        <p className="text-brand-muted">Workload routing decisions and tier distribution</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {tierDefs.map(t => (
          <div key={t.name} className="bg-brand-card border border-brand-border rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Badge variant={t.name} />
              <span className="text-xs text-brand-muted">{t.substrate}</span>
            </div>
            <p className="text-xs text-brand-muted">{t.agent_type}</p>
            <div className="mt-2 text-2xl font-bold text-white" style={{ fontFamily: 'Red Hat Display' }}>
              {records.filter(r => r.tier_assignment === t.name).length}
            </div>
            <div className="text-xs text-brand-muted">routed</div>
          </div>
        ))}
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Recent Routing Decisions</SectionHeader>
        {isLoading ? <LoadingState /> : records.length === 0 ? <EmptyState message="No routing decisions." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-brand-muted uppercase tracking-wider border-b border-brand-border">
                  <th className="text-left py-2">Workload</th>
                  <th className="text-center py-2">Tier</th>
                  <th className="text-center py-2">Substrate</th>
                  <th className="text-right py-2">Confidence</th>
                  <th className="text-center py-2">Override</th>
                  <th className="text-right py-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {records.map(r => (
                  <tr key={r.routing_id} className="border-b border-brand-surface hover:bg-brand-surface">
                    <td className="py-2 text-white text-xs font-mono">{r.workload_id.slice(0, 12)}...</td>
                    <td className="py-2 text-center"><Badge variant={r.tier_assignment} /></td>
                    <td className="py-2 text-center text-white">{r.substrate}</td>
                    <td className="py-2 text-right text-white">{r.confidence_score.toFixed(2)}</td>
                    <td className="py-2 text-center">{r.override ? <Badge variant="unstable_pass">yes</Badge> : <span className="text-brand-muted">-</span>}</td>
                    <td className="py-2 text-right text-brand-muted">{new Date(r.created_at).toLocaleString()}</td>
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
