import { useGovernancePipeline } from '../api/hooks';
import SectionHeader from '../components/SectionHeader';
import Badge from '../components/Badge';
import LoadingState from '../components/LoadingState';

export default function Governance() {
  const { data, isLoading } = useGovernancePipeline();

  if (isLoading || !data) return <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8"><LoadingState message="Loading governance pipeline..." /></div>;

  const ev = data.evidence;
  const cls = data.classifications;
  const hyp = data.hypotheses;
  const app = data.approvals;
  const act = data.actions;

  const totalCls = (cls['total'] as number) || Object.values(cls).reduce((a: number, b) => a + (typeof b === 'number' ? b : 0), 0);
  const passCount = (cls['pass'] as number) || 0;
  const failCount = (cls['fail'] as number) || 0;
  const incCount = (cls['inconclusive'] as number) || 0;

  const totalHyp = (hyp['total'] as number) || 0;
  const pendingHyp = (hyp['pending'] as number) || 0;
  const validatedHyp = (hyp['validated'] as number) || 0;
  const falsifiedHyp = (hyp['falsified'] as number) || 0;

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Governance Pipeline</h1>
        <p className="text-brand-muted">End-to-end lifecycle: what's being evaluated, what's failing, what's governed</p>
      </div>

      <div className="grid grid-cols-5 gap-3">
        <StageCard name="Evidence" count={ev.total} color="blue"
          detail={`${(ev.by_outcome['fail'] || 0).toLocaleString()} failures across ${ev.labs_monitored} labs`}
          items={[
            { label: 'fail', value: ev.by_outcome['fail'] || 0, variant: 'fail' },
            { label: 'pass', value: ev.by_outcome['pass'] || 0, variant: 'pass' },
            { label: 'warn', value: ev.by_outcome['warn'] || 0, variant: 'unstable_pass' },
          ]} />
        <Arrow />
        <StageCard name="Classification" count={totalCls} color="purple"
          detail={`${passCount} pass, ${failCount} fail — constraints evaluating real evidence`}
          items={[
            { label: 'pass', value: passCount, variant: 'pass' },
            { label: 'fail', value: failCount, variant: 'fail' },
            { label: 'inconclusive', value: incCount, variant: 'inconclusive' },
          ]} />
        <Arrow />
        <StageCard name="Hypotheses" count={totalHyp} color="amber"
          detail={`${validatedHyp + falsifiedHyp} resolved, ${pendingHyp} awaiting validation`}
          items={[
            { label: 'pending', value: pendingHyp, variant: 'inconclusive' },
            { label: 'validated', value: validatedHyp, variant: 'pass' },
            { label: 'falsified', value: falsifiedHyp, variant: 'fail' },
          ]} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className={`rounded-lg border p-4 ${app.pending > 0 ? 'border-amber-600 bg-amber-900/10' : 'border-brand-border bg-brand-card'}`}>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm text-white font-bold uppercase tracking-wider">Approval Queue</h3>
            {app.pending > 0 && <Badge variant="unstable_pass">{app.pending} pending review</Badge>}
          </div>
          <p className="text-xs text-brand-muted mb-3">
            LLM-proposed failure classifications awaiting human review in Stargate.
            Approved proposals become deterministic rules — no more LLM needed for that pattern.
          </p>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div><div className="text-xl font-bold text-amber-400">{app.pending}</div><div className="text-xs text-brand-muted">Pending</div></div>
            <div><div className="text-xl font-bold text-green-400">{app.approved}</div><div className="text-xs text-brand-muted">Approved</div></div>
            <div><div className="text-xl font-bold text-red-400">{app.rejected}</div><div className="text-xs text-brand-muted">Rejected</div></div>
          </div>
        </div>

        <div className="rounded-lg border border-brand-border bg-brand-card p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm text-white font-bold uppercase tracking-wider">Actions</h3>
            <Badge variant={act.remediations_applied > 0 ? 'pass' : 'inconclusive'}>
              {act.remediations_applied} remediated
            </Badge>
          </div>
          <p className="text-xs text-brand-muted mb-3">
            MPC planning cycles and remediation actions.
            Actions require governance approval before execution.
          </p>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div><div className="text-xl font-bold text-white">{act.mpc_cycles}</div><div className="text-xs text-brand-muted">MPC Cycles</div></div>
            <div><div className="text-xl font-bold text-white">{act.pending_actions}</div><div className="text-xs text-brand-muted">Pending</div></div>
            <div><div className="text-xl font-bold text-white">{act.remediations_applied}</div><div className="text-xs text-brand-muted">Remediated</div></div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Top Failure Classes</SectionHeader>
          <div className="space-y-2">
            {data.top_failure_classes.map(f => {
              const pct = (f.count / Math.max(ev.total, 1)) * 100;
              return (
                <div key={f.class} className="flex items-center gap-3">
                  <div className="w-36 text-xs text-white truncate font-mono">{f.class}</div>
                  <div className="flex-1 h-3 bg-brand-surface rounded-full overflow-hidden">
                    <div className="h-full bg-red-500/60 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
                  </div>
                  <div className="w-20 text-right text-xs text-brand-muted">{f.count.toLocaleString()}</div>
                  <div className="w-16 text-right text-xs text-brand-muted">{f.clusters}c / {f.labs}l</div>
                </div>
              );
            })}
          </div>
        </div>

        {app.top_pending.length > 0 && (
          <div className="bg-brand-card border border-brand-border rounded-lg p-4">
            <SectionHeader>Pending Proposals (Stargate)</SectionHeader>
            <p className="text-xs text-brand-muted mb-3">
              These LLM-proposed classifications need human review in Stargate's admin UI.
              Once approved, they become deterministic rules.
            </p>
            <div className="space-y-1">
              {app.top_pending.map(p => (
                <div key={p.class} className="flex items-center justify-between text-sm px-2 py-1.5 bg-brand-surface rounded">
                  <span className="text-white font-mono text-xs">{p.class}</span>
                  <span className="text-brand-muted text-xs">{p.count} proposals</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Cluster Health</SectionHeader>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {data.clusters.map(c => {
            const healthColor = c.health_rate >= 50 ? 'text-green-400' : c.health_rate >= 10 ? 'text-amber-400' : 'text-red-400';
            return (
              <div key={c.name} className="bg-brand-surface border border-brand-border rounded-lg p-3">
                <div className="text-sm text-white font-medium">{c.name}</div>
                <div className={`text-xl font-bold ${healthColor}`}>{c.health_rate.toFixed(1)}%</div>
                <div className="text-xs text-brand-muted">
                  {c.evaluations.toLocaleString()} evals &middot; {c.labs_seen} labs
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StageCard({ name, count, color, detail, items }: {
  name: string; count: number; color: string; detail: string;
  items: Array<{ label: string; value: number; variant: string }>;
}) {
  const borderColor = color === 'blue' ? 'border-blue-600' : color === 'purple' ? 'border-purple-600' : 'border-amber-600';
  return (
    <div className={`rounded-lg border ${borderColor} bg-brand-card p-4`}>
      <div className="text-xs text-brand-muted uppercase tracking-wider font-bold">{name}</div>
      <div className="text-2xl font-bold text-white mt-1" style={{ fontFamily: 'Red Hat Display' }}>{count.toLocaleString()}</div>
      <p className="text-xs text-brand-muted mt-1 leading-relaxed">{detail}</p>
      <div className="flex gap-2 mt-2">
        {items.filter(i => i.value > 0).map(i => (
          <Badge key={i.label} variant={i.variant}>{`${i.label}: ${i.value.toLocaleString()}`}</Badge>
        ))}
      </div>
    </div>
  );
}

function Arrow() {
  return <div className="flex items-center justify-center text-brand-muted text-xl">→</div>;
}
