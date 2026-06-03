import { useHypothesisQueue } from '../api/hooks';
import SectionHeader from '../components/SectionHeader';
import Badge from '../components/Badge';
import LoadingState from '../components/LoadingState';
import EmptyState from '../components/EmptyState';

export default function Hypotheses() {
  const { data, isLoading } = useHypothesisQueue(50);
  const hypotheses = data?.hypotheses ?? [];

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Hypotheses</h1>
        <p className="text-brand-muted">Structured falsifiable hypotheses about observed system state</p>
      </div>

      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Queue ({data?.total ?? 0} unresolved)</SectionHeader>

        {isLoading ? <LoadingState /> : hypotheses.length === 0 ? <EmptyState message="No hypotheses in queue." /> : (
          <div className="space-y-3">
            {hypotheses.map(h => (
              <div key={h.hypothesis_id} className="bg-brand-surface border border-brand-border rounded-lg p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <p className="text-white text-sm font-medium">{h.claim}</p>
                    <div className="flex flex-wrap gap-2 mt-2">
                      <Badge variant={h.geometric_stability_state} />
                      <span className="text-xs text-brand-muted">
                        stability: {h.geometric_stability_score.toFixed(3)}
                      </span>
                      <span className="text-xs text-brand-muted">
                        confidence: {h.confidence_score.toFixed(2)}
                      </span>
                      {h.validation_outcome && <Badge variant={h.validation_outcome} />}
                    </div>
                    {h.testable_conditions.length > 0 && (
                      <div className="mt-2 text-xs text-brand-muted">
                        {h.testable_conditions.map((c, i) => (
                          <span key={i} className="mr-2">{c.field} {c.operator} {String(c.value)}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="text-xs text-brand-muted whitespace-nowrap">
                    {new Date(h.created_at).toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
