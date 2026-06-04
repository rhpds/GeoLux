import { useParams, NavLink } from 'react-router-dom';
import { useMPCCycle } from '../api/hooks';
import MetricCard from '../components/MetricCard';
import SectionHeader from '../components/SectionHeader';
import Badge from '../components/Badge';
import LoadingState from '../components/LoadingState';

export default function MPCCycleDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: cycle, isLoading } = useMPCCycle(id ?? '');

  if (isLoading) return <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8"><LoadingState message="Loading MPC cycle..." /></div>;

  if (!cycle) return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
      <NavLink to="/mpc" className="text-brand-muted hover:text-white text-sm transition-colors">&larr; MPC Cycles</NavLink>
      <p className="text-brand-muted mt-6">Cycle not found.</p>
    </div>
  );

  const c = cycle as unknown as Record<string, unknown>;
  const state = c['current_state'] as Record<string, unknown> | undefined;
  const predictions = (c['predictions'] as Array<Record<string, unknown>>) || [];
  const candidates = (c['candidate_actions'] as Array<Record<string, unknown>>) || [];
  const selectedId = c['selected_action_id'] as string | null;
  const profile = (c['geometric_stability_profile'] as Record<string, unknown>) || {};
  const scores = (profile['scores'] as number[]) || [];

  const cluster = (state?.['cluster_name'] as string) || cycle.cluster_id;
  const outcome = (state?.['outcome'] as string) || '';
  const failureClass = (state?.['failure_class'] as string) || '';
  const message = (state?.['message'] as string) || '';
  const crossSystem = state?.['cross_system'] as Record<string, unknown> | undefined;
  const deepfield = crossSystem?.['deepfield'] as Record<string, unknown> | undefined;

  const selectedAction = candidates.find(a => (a['action_id'] as string) === selectedId);
  const actionType = (selectedAction?.['action_type'] as string) || (candidates[0]?.['action_type'] as string) || 'no_action';

  const summary = buildSummary(cluster, outcome, failureClass, actionType, cycle.horizon, predictions.length);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <NavLink to="/mpc" className="text-brand-muted hover:text-white text-sm transition-colors">&larr; MPC Cycles</NavLink>

      <div className="flex items-start gap-4">
        <h1 className="text-2xl font-bold text-white flex-1" style={{ fontFamily: 'Red Hat Display' }}>{cluster}</h1>
        {cycle.suspended ? <Badge variant="fail">suspended</Badge> : <Badge variant="pass">active</Badge>}
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <p className="text-sm text-white leading-relaxed">{summary}</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Horizon" value={`${cycle.horizon} steps`} />
        <MetricCard label="Optimization Score" value={cycle.optimization_score.toFixed(2)} />
        <MetricCard label="Stability Mean" value={(Number(profile['mean']) || 0).toFixed(3)} />
        <MetricCard label="Created At" value={new Date(cycle.created_at).toLocaleString(undefined, { month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit' })} />
      </div>

      {(outcome || failureClass || message) && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Cluster State at Planning Time</SectionHeader>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            {outcome && (
              <div>
                <div className="text-brand-muted text-xs uppercase tracking-wider">Outcome</div>
                <Badge variant={outcome === 'pass' ? 'pass' : outcome === 'warn' ? 'unstable_pass' : 'fail'}>{outcome}</Badge>
              </div>
            )}
            {failureClass && (
              <div>
                <div className="text-brand-muted text-xs uppercase tracking-wider">Failure Class</div>
                <Badge variant="fail">{failureClass}</Badge>
              </div>
            )}
            {state?.['lab_code'] != null && (
              <div>
                <div className="text-brand-muted text-xs uppercase tracking-wider">Lab / Namespace</div>
                <div className="text-white font-medium mt-0.5">{String(state['lab_code'])}</div>
              </div>
            )}
            {state?.['stage_id'] != null && (
              <div>
                <div className="text-brand-muted text-xs uppercase tracking-wider">Stage</div>
                <div className="text-white font-medium mt-0.5">{String(state['stage_id'])}</div>
              </div>
            )}
          </div>
          {message && (
            <div className="mt-3 pt-3 border-t border-brand-border">
              <div className="text-brand-muted text-xs uppercase tracking-wider mb-1">Message</div>
              <div className="text-sm text-white bg-brand-surface rounded p-2 font-mono break-all">{message}</div>
            </div>
          )}
        </div>
      )}

      {predictions.length > 0 && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Predicted Trajectory ({predictions.length} steps)</SectionHeader>
          <div className="space-y-3">
            {predictions.map((p, i) => {
              const pState = (p['predicted_state'] as Record<string, unknown>) || {};
              const pOutcome = (pState['outcome'] as string) || '';
              const pFailure = (pState['failure_class'] as string) || '';
              const pMessage = (pState['message'] as string) || '';
              const pCross = (pState['cross_system'] as Record<string, unknown>)?.['deepfield'] as Record<string, unknown> | undefined;
              const confidence = (p['confidence'] as number) || 0;

              return (
                <div key={i} className="bg-brand-surface border border-brand-border rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="w-6 h-6 rounded bg-brand-dark flex items-center justify-center text-xs text-white font-bold">
                        {(p['step'] as number) || i + 1}
                      </span>
                      <Badge variant={pOutcome === 'pass' ? 'pass' : pOutcome === 'warn' ? 'unstable_pass' : 'fail'}>{pOutcome || 'unknown'}</Badge>
                      {pFailure && <Badge variant="fail">{pFailure}</Badge>}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-brand-muted">confidence</span>
                      <div className="w-16 h-2 bg-brand-dark rounded-full overflow-hidden">
                        <div className="h-full bg-green-500 rounded-full" style={{ width: `${confidence * 100}%` }} />
                      </div>
                      <span className="text-xs text-white w-10 text-right">{(confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  {pMessage && <p className="text-xs text-brand-muted">{pMessage}</p>}
                  {pCross && Number(pCross['recent_events']) > 0 && (
                    <div className="text-xs text-brand-muted mt-1">DeepField: {String(pCross['recent_events'])} recent events</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Recommended Action</SectionHeader>
        <div className="space-y-2">
          {candidates.map((a, i) => {
            const isSelected = (a['action_id'] as string) === selectedId || candidates.length === 1;
            const aType = (a['action_type'] as string) || '';
            const aParams = (a['parameters'] as Record<string, unknown>) || {};
            return (
              <div key={i} className={`p-3 rounded-lg border ${isSelected ? 'border-green-600 bg-green-900/20' : 'border-brand-border bg-brand-surface'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {isSelected && <span className="w-2 h-2 rounded-full bg-green-500" />}
                    <span className="text-sm text-white font-medium">{formatActionType(aType)}</span>
                  </div>
                  <span className="text-xs text-brand-muted">score: {String(a['score'] || 0)}</span>
                </div>
                {Object.keys(aParams).length > 0 && (
                  <div className="mt-1 text-xs text-brand-muted">
                    {Object.entries(aParams).map(([k, v]) => `${k}: ${String(v)}`).join(', ')}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {deepfield && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Cross-System Intelligence (DeepField)</SectionHeader>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-brand-muted text-xs uppercase tracking-wider">Recent Events</div>
              <div className="text-xl font-bold text-white mt-1">{String(deepfield['recent_events'] ?? 0)}</div>
            </div>
            <div>
              <div className="text-brand-muted text-xs uppercase tracking-wider">Signal Types</div>
              <div className="mt-1">
                {Array.isArray(deepfield['signal_types']) && (deepfield['signal_types'] as string[]).length > 0
                  ? (deepfield['signal_types'] as string[]).map((s, j) => <Badge key={j} variant="minor">{s}</Badge>)
                  : <span className="text-brand-muted text-xs">None detected</span>}
              </div>
            </div>
            <div>
              <div className="text-brand-muted text-xs uppercase tracking-wider">RCA Categories</div>
              <div className="mt-1">
                {Array.isArray(deepfield['rca_categories']) && (deepfield['rca_categories'] as string[]).length > 0
                  ? (deepfield['rca_categories'] as string[]).map((s, j) => <Badge key={j} variant="major">{s}</Badge>)
                  : <span className="text-brand-muted text-xs">None identified</span>}
              </div>
            </div>
          </div>
        </div>
      )}

      {scores.length > 0 && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Stability Profile</SectionHeader>
          <div className="flex items-end gap-1 h-12">
            {scores.map((s, i) => (
              <div key={i} className="flex-1 bg-green-500 rounded-t-sm" style={{ height: `${Math.max(4, s * 48)}px` }}
                title={`Score: ${s.toFixed(3)}`} />
            ))}
          </div>
          <div className="flex gap-4 mt-2 text-xs text-brand-muted">
            <span>Mean: {Number(profile['mean'] || 0).toFixed(3)}</span>
            <span>Min: {Number(profile['min'] || 0).toFixed(3)}</span>
            <span>Samples: {scores.length}</span>
          </div>
        </div>
      )}

      {cycle.horizon_adjusted && (
        <div className="bg-amber-900/20 border border-amber-700 rounded-lg p-3 text-sm text-amber-200">
          Horizon was auto-adjusted from the default due to geometric stability conditions.
        </div>
      )}
    </div>
  );
}

function buildSummary(cluster: string, outcome: string, failureClass: string, action: string, horizon: number, steps: number): string {
  const parts: string[] = [];
  parts.push(`MPC evaluated cluster "${cluster}" with a ${horizon}-step prediction horizon.`);
  if (outcome === 'pass') parts.push('The cluster is healthy — no issues detected.');
  else if (outcome === 'warn') parts.push(`A warning was detected${failureClass ? ` (${failureClass})` : ''} — this is a non-critical condition.`);
  else if (outcome === 'fail') parts.push(`A failure was detected${failureClass ? `: ${failureClass}` : ''}.`);
  if (steps > 0) parts.push(`The LLM predicted ${steps} future steps to evaluate the trajectory.`);
  if (action === 'no_action') parts.push('Conclusion: no intervention required at this time.');
  else if (action === 'scale_replicas') parts.push('Conclusion: scaling recommended to address the issue.');
  else if (action === 'execute_remediation') parts.push('Conclusion: remediation action recommended.');
  return parts.join(' ');
}

function formatActionType(type: string): string {
  const map: Record<string, string> = { no_action: 'No Action Required', scale_replicas: 'Scale Replicas', execute_remediation: 'Execute Remediation' };
  return map[type] || type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}
