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

  const evidence = (hypothesis as unknown as Record<string, unknown>).evidence_snapshot as Record<string, unknown> | undefined;

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <NavLink to="/hypotheses" className="text-brand-muted hover:text-white text-sm transition-colors">
        &larr; Hypotheses
      </NavLink>

      <div className="flex items-start gap-4">
        <h1 className="text-3xl font-bold text-white flex-1" style={{ fontFamily: 'Red Hat Display' }}>
          {hypothesis.claim}
        </h1>
        <Badge variant={hypothesis.geometric_stability_state} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Confidence" value={hypothesis.confidence_score.toFixed(2)} />
        <MetricCard label="Stability Score" value={hypothesis.geometric_stability_score.toFixed(3)} />
        <MetricCard label="Stability State" value={hypothesis.geometric_stability_state} />
        <MetricCard label="Created At" value={new Date(hypothesis.created_at).toLocaleString()} />
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Testable Conditions</SectionHeader>
        {hypothesis.testable_conditions.length === 0 ? (
          <p className="text-brand-muted text-sm">No testable conditions defined.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-brand-muted uppercase tracking-wider border-b border-brand-border">
                  <th className="text-left py-2">Field</th>
                  <th className="text-left py-2">Operator</th>
                  <th className="text-left py-2">Value</th>
                </tr>
              </thead>
              <tbody>
                {hypothesis.testable_conditions.map((c, i) => (
                  <tr key={i} className="border-b border-brand-surface">
                    <td className="py-2 text-white">{c.field}</td>
                    <td className="py-2 text-white">{c.operator}</td>
                    <td className="py-2 text-white">{String(c.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {evidence && Object.keys(evidence).length > 0 && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Evidence Snapshot</SectionHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <tbody>
                {Object.entries(evidence).map(([key, val]) => (
                  <tr key={key} className="border-b border-brand-surface">
                    <td className="py-2 text-brand-muted font-medium w-1/3">{key}</td>
                    <td className="py-2 text-white">{typeof val === 'object' ? JSON.stringify(val) : String(val)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Validation</SectionHeader>
        {hypothesis.validation_outcome ? (
          <Badge variant={hypothesis.validation_outcome} />
        ) : (
          <Badge variant="inconclusive">Pending</Badge>
        )}
      </div>
    </div>
  );
}
