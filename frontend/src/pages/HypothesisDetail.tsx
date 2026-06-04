import { useParams, NavLink } from 'react-router-dom';
import { useHypothesis } from '../api/hooks';
import MetricCard from '../components/MetricCard';
import SectionHeader from '../components/SectionHeader';
import Badge from '../components/Badge';
import LoadingState from '../components/LoadingState';

export default function HypothesisDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: hypothesis, isLoading } = useHypothesis(id ?? '');

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
        <LoadingState message="Loading hypothesis..." />
      </div>
    );
  }

  if (!hypothesis) {
    return (
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
        <NavLink to="/hypotheses" className="text-brand-muted hover:text-white text-sm transition-colors">
          &larr; Hypotheses
        </NavLink>
        <p className="text-brand-muted mt-6">Hypothesis not found.</p>
      </div>
    );
  }

  const h = hypothesis as unknown as Record<string, unknown>;
  const evidence = h['evidence_snapshot'] as Record<string, unknown> | undefined;
  const bundleId = h['evidence_bundle_id'] as string | undefined;
  const crossSystem = evidence?.cross_system as Record<string, unknown> | undefined;
  const deepfield = crossSystem?.deepfield as Record<string, unknown> | undefined;

  const cluster = evidence?.cluster_name as string || '';
  const labCode = evidence?.lab_code as string || '';
  const failureClass = evidence?.failure_class as string || '';
  const message = evidence?.message as string || '';

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <NavLink to="/hypotheses" className="text-brand-muted hover:text-white text-sm transition-colors">
        &larr; Hypotheses
      </NavLink>

      <div className="flex items-start gap-4">
        <h1 className="text-2xl font-bold text-white flex-1" style={{ fontFamily: 'Red Hat Display' }}>
          {hypothesis.claim}
        </h1>
        <Badge variant={hypothesis.geometric_stability_state} />
      </div>

      {(cluster || labCode || failureClass) && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Context</SectionHeader>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            {cluster && (
              <div>
                <div className="text-brand-muted text-xs uppercase tracking-wider">Cluster</div>
                <div className="text-white font-medium mt-0.5">{cluster}</div>
              </div>
            )}
            {labCode && (
              <div>
                <div className="text-brand-muted text-xs uppercase tracking-wider">Lab / Namespace</div>
                <div className="text-white font-medium mt-0.5">{labCode}</div>
              </div>
            )}
            {failureClass && (
              <div>
                <div className="text-brand-muted text-xs uppercase tracking-wider">Failure Class</div>
                <Badge variant="fail">{failureClass}</Badge>
              </div>
            )}
            {evidence?.['stage_id'] != null && (
              <div>
                <div className="text-brand-muted text-xs uppercase tracking-wider">Stage</div>
                <div className="text-white font-medium mt-0.5">{String(evidence['stage_id'])}</div>
              </div>
            )}
          </div>
          {message && (
            <div className="mt-3 pt-3 border-t border-brand-border">
              <div className="text-brand-muted text-xs uppercase tracking-wider mb-1">Error Message</div>
              <div className="text-sm text-white bg-brand-surface rounded p-2 font-mono break-all">{message}</div>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Confidence" value={hypothesis.confidence_score.toFixed(2)} />
        <MetricCard label="Stability Score" value={hypothesis.geometric_stability_score.toFixed(3)} />
        <MetricCard label="Stability State" value={hypothesis.geometric_stability_state} />
        <MetricCard label="Created At" value={new Date(hypothesis.created_at).toLocaleString()} />
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>What this hypothesis tests</SectionHeader>
        {hypothesis.testable_conditions.length === 0 ? (
          <p className="text-brand-muted text-sm">No testable conditions defined.</p>
        ) : (
          <div className="space-y-2">
            {hypothesis.testable_conditions.map((c, i) => (
              <div key={i} className="flex items-center gap-3 text-sm bg-brand-surface rounded p-2">
                <span className="text-white font-mono">{c.field}</span>
                <Badge variant="minor">{c.operator}</Badge>
                <span className="text-white font-mono">{String(c.value)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {deepfield && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Cross-System Intelligence (DeepField)</SectionHeader>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-brand-muted text-xs uppercase tracking-wider">Recent Events</div>
              <div className="text-xl font-bold text-white mt-1">{String(deepfield.recent_events ?? 0)}</div>
            </div>
            <div>
              <div className="text-brand-muted text-xs uppercase tracking-wider">Signal Types</div>
              <div className="mt-1">
                {Array.isArray(deepfield.signal_types) && deepfield.signal_types.length > 0
                  ? (deepfield.signal_types as string[]).map((s, i) => <Badge key={i} variant="minor">{s}</Badge>)
                  : <span className="text-brand-muted text-xs">None detected</span>}
              </div>
            </div>
            <div>
              <div className="text-brand-muted text-xs uppercase tracking-wider">RCA Categories</div>
              <div className="mt-1">
                {Array.isArray(deepfield.rca_categories) && deepfield.rca_categories.length > 0
                  ? (deepfield.rca_categories as string[]).map((s, i) => <Badge key={i} variant="major">{s}</Badge>)
                  : <span className="text-brand-muted text-xs">None identified</span>}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Validation Status</SectionHeader>
        <div className="flex items-center gap-4">
          {hypothesis.validation_outcome ? (
            <Badge variant={hypothesis.validation_outcome} />
          ) : (
            <div>
              <Badge variant="inconclusive">Awaiting Validation</Badge>
              <p className="text-xs text-brand-muted mt-2">
                This hypothesis has not been validated against subsequent evidence.
                It will be automatically validated when a follow-up evaluation for this
                cluster confirms or contradicts the hypothesis.
              </p>
            </div>
          )}
        </div>
      </div>

      {bundleId && (
        <div className="text-xs text-brand-muted">
          Evidence bundle: <span className="font-mono">{bundleId}</span>
        </div>
      )}
    </div>
  );
}
