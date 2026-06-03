import { useStabilityScores, useStabilityThresholds } from '../api/hooks';
import SectionHeader from './SectionHeader';
import Badge from './Badge';

export default function StabilityMonitor() {
  const { data: scores } = useStabilityScores(undefined, 20);
  const { data: thresholds } = useStabilityThresholds();

  const threshold = thresholds?.stability_threshold ?? 0.7;
  const records = scores ?? [];

  const stateDistribution = records.reduce((acc, r) => {
    acc[r.stability_state] = (acc[r.stability_state] ?? 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const avgScore = records.length > 0
    ? records.reduce((sum, r) => sum + r.stability_score, 0) / records.length
    : 0;

  return (
    <div className="bg-brand-card border border-brand-border rounded-lg p-4">
      <SectionHeader>Geometric Stability</SectionHeader>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <div>
          <div className={`text-xl font-bold ${avgScore >= threshold ? 'text-green-400' : 'text-red-400'}`}>
            {avgScore.toFixed(3)}
          </div>
          <div className="text-xs text-brand-muted">Avg Score</div>
        </div>
        <div>
          <div className="text-xl font-bold text-white">{threshold}</div>
          <div className="text-xs text-brand-muted">Threshold</div>
        </div>
        <div>
          <div className="text-xl font-bold text-white">{records.length}</div>
          <div className="text-xs text-brand-muted">Recent Calls</div>
        </div>
      </div>

      <div className="flex gap-2 mb-3">
        {Object.entries(stateDistribution).map(([state, count]) => (
          <Badge key={state} variant={state}>{`${state}: ${count}`}</Badge>
        ))}
      </div>

      {records.length > 0 && (
        <div className="flex gap-0.5 items-end h-6">
          {records.map((r, i) => (
            <div
              key={i}
              className={`flex-1 rounded-t-sm ${r.stability_score >= threshold ? 'bg-green-500' : 'bg-red-500'}`}
              style={{ height: `${Math.max(2, r.stability_score * 24)}px` }}
              title={`${r.endpoint}: ${r.stability_score.toFixed(3)}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
