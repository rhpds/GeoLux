import { useGovernancePipeline } from '../api/hooks';
import SectionHeader from '../components/SectionHeader';
import Badge from '../components/Badge';
import LoadingState from '../components/LoadingState';

function sumValues(obj: Record<string, number>): number {
  return Object.values(obj).reduce((a, b) => a + b, 0);
}

function StageCard({ name, total, breakdowns, color }: {
  name: string;
  total: number;
  breakdowns: Array<{ label: string; value: number; variant: string }>;
  color: 'green' | 'amber' | 'red';
}) {
  const borderColor = color === 'green' ? 'border-green-600' : color === 'amber' ? 'border-amber-500' : 'border-red-600';
  const glowColor = color === 'green' ? 'bg-green-900/30' : color === 'amber' ? 'bg-amber-900/30' : 'bg-red-900/30';

  return (
    <div className={`${glowColor} border ${borderColor} rounded-lg p-4 min-w-[160px] flex-1`}>
      <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">{name}</div>
      <div className="text-3xl font-bold text-white mb-3" style={{ fontFamily: 'Red Hat Display' }}>{total}</div>
      <div className="flex flex-wrap gap-1">
        {breakdowns.map(b => (
          <Badge key={b.label} variant={b.variant}>{b.label}: {b.value}</Badge>
        ))}
      </div>
    </div>
  );
}

function Arrow() {
  return (
    <div className="flex items-center text-brand-muted text-2xl px-1 shrink-0 self-center">
      &rarr;
    </div>
  );
}

export default function Governance() {
  const { data, isLoading } = useGovernancePipeline();

  if (isLoading || !data) {
    return (
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Governance Pipeline</h1>
        <LoadingState />
      </div>
    );
  }

  const classTotal = sumValues(data.classifications);
  const classPass = data.classifications['pass'] ?? 0;
  const classFail = data.classifications['fail'] ?? 0;
  const classInconclusive = classTotal - classPass - classFail;

  const hypTotal = sumValues(data.hypotheses);
  const hypPending = data.hypotheses['pending'] ?? 0;
  const hypValidated = data.hypotheses['validated'] ?? 0;
  const hypFalsified = data.hypotheses['falsified'] ?? 0;

  const actionsTotal = data.actions.mpc_cycles + data.actions.remediations_applied;

  const evidenceColor: 'green' | 'amber' | 'red' = data.evidence.total > 0 ? 'green' : 'amber';
  const classColor: 'green' | 'amber' | 'red' = classFail > 0 ? 'red' : classInconclusive > 0 ? 'amber' : 'green';
  const hypColor: 'green' | 'amber' | 'red' = hypPending > 0 ? 'amber' : hypFalsified > 0 ? 'red' : 'green';
  const approvalColor: 'green' | 'amber' | 'red' = data.approvals.pending > 0 ? 'amber' : data.approvals.rejected > 0 ? 'red' : 'green';
  const actionColor: 'green' | 'amber' | 'red' = data.actions.pending_actions > 0 ? 'amber' : data.actions.mpc_suspended > 0 ? 'red' : 'green';

  const evidenceBreakdowns = Object.entries(data.evidence.by_outcome).map(([k, v]) => ({
    label: k, value: v, variant: k === 'pass' ? 'pass' : k === 'fail' ? 'fail' : 'inconclusive',
  }));

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Governance Pipeline</h1>
        <p className="text-brand-muted">Evidence &rarr; Classification &rarr; Hypothesis &rarr; Approval &rarr; Action</p>
      </div>

      {/* Pipeline visualization */}
      <div className="bg-brand-card border border-brand-border rounded-lg p-6">
        <SectionHeader>Pipeline Stages</SectionHeader>
        <div className="flex items-stretch gap-0 overflow-x-auto">
          <StageCard
            name="Evidence"
            total={data.evidence.total}
            breakdowns={evidenceBreakdowns}
            color={evidenceColor}
          />
          <Arrow />
          <StageCard
            name="Classification"
            total={classTotal}
            breakdowns={[
              { label: 'pass', value: classPass, variant: 'pass' },
              { label: 'fail', value: classFail, variant: 'fail' },
              { label: 'inconclusive', value: classInconclusive, variant: 'inconclusive' },
            ]}
            color={classColor}
          />
          <Arrow />
          <StageCard
            name="Hypotheses"
            total={hypTotal}
            breakdowns={[
              { label: 'pending', value: hypPending, variant: 'inconclusive' },
              { label: 'validated', value: hypValidated, variant: 'validated' },
              { label: 'falsified', value: hypFalsified, variant: 'falsified' },
            ]}
            color={hypColor}
          />
          <Arrow />
          <StageCard
            name="Approvals"
            total={data.approvals.total}
            breakdowns={[
              { label: 'pending', value: data.approvals.pending, variant: 'unclassifiable' },
              { label: 'approved', value: data.approvals.approved, variant: 'pass' },
              { label: 'rejected', value: data.approvals.rejected, variant: 'fail' },
            ]}
            color={approvalColor}
          />
          <Arrow />
          <StageCard
            name="Actions"
            total={actionsTotal}
            breakdowns={[
              { label: 'pending', value: data.actions.pending_actions, variant: 'unclassifiable' },
              { label: 'mpc', value: data.actions.mpc_cycles, variant: 'nano' },
              { label: 'remediated', value: data.actions.remediations_applied, variant: 'pass' },
            ]}
            color={actionColor}
          />
        </div>
      </div>

      {/* Top Failure Classes */}
      {data.top_failure_classes.length > 0 && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Top Failure Classes</SectionHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-brand-muted uppercase tracking-wider border-b border-brand-border">
                  <th className="text-left py-2">Class</th>
                  <th className="text-right py-2">Count</th>
                  <th className="text-right py-2">Clusters</th>
                  <th className="text-right py-2">Labs</th>
                </tr>
              </thead>
              <tbody>
                {data.top_failure_classes.map(fc => (
                  <tr key={fc.class} className="border-b border-brand-surface hover:bg-brand-surface">
                    <td className="py-2 text-white font-mono text-xs">{fc.class}</td>
                    <td className="py-2 text-right text-white">{fc.count}</td>
                    <td className="py-2 text-right text-brand-muted">{fc.clusters}</td>
                    <td className="py-2 text-right text-brand-muted">{fc.labs}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Approval Queue */}
      {data.approvals.pending > 0 && data.approvals.top_pending.length > 0 && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Approval Queue ({data.approvals.pending} pending)</SectionHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-brand-muted uppercase tracking-wider border-b border-brand-border">
                  <th className="text-left py-2">Proposed Class</th>
                  <th className="text-right py-2">Count</th>
                  <th className="text-right py-2">Avg Confidence</th>
                </tr>
              </thead>
              <tbody>
                {data.approvals.top_pending.map(p => (
                  <tr key={p.class} className="border-b border-brand-surface hover:bg-brand-surface">
                    <td className="py-2 text-white font-mono text-xs">{p.class}</td>
                    <td className="py-2 text-right text-white">{p.count}</td>
                    <td className="py-2 text-right text-brand-muted">{p.avg_confidence.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Cluster Health */}
      {data.clusters.length > 0 && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Cluster Health ({data.clusters.length} clusters)</SectionHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-brand-muted uppercase tracking-wider border-b border-brand-border">
                  <th className="text-left py-2">Cluster</th>
                  <th className="text-right py-2">Evaluations</th>
                  <th className="text-right py-2">Health Rate</th>
                  <th className="text-right py-2">Labs Seen</th>
                  <th className="text-right py-2">Labs Failing</th>
                </tr>
              </thead>
              <tbody>
                {data.clusters.map(c => {
                  const healthVariant = c.health_rate >= 0.95 ? 'pass' : c.health_rate >= 0.8 ? 'unclassifiable' : 'fail';
                  return (
                    <tr key={c.name} className="border-b border-brand-surface hover:bg-brand-surface">
                      <td className="py-2 text-white font-medium">{c.name}</td>
                      <td className="py-2 text-right text-white">{c.evaluations}</td>
                      <td className="py-2 text-right">
                        <Badge variant={healthVariant}>{(c.health_rate * 100).toFixed(1)}%</Badge>
                      </td>
                      <td className="py-2 text-right text-brand-muted">{c.labs_seen}</td>
                      <td className="py-2 text-right text-brand-muted">{c.labs_failing}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
