import { useDemandSignals, useCostAttribution, useUtilization } from '../api/hooks';
import SectionHeader from '../components/SectionHeader';
import EmptyState from '../components/EmptyState';

export default function LaunchpadIntelligence() {
  const { data: demand } = useDemandSignals();
  const { data: cost } = useCostAttribution();
  const { data: utilization } = useUtilization();

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Launchpad Intelligence</h1>
        <p className="text-brand-muted">Provisioning patterns mined from RHDP ecosystem</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Demand Signals</SectionHeader>
          {(demand?.demand_signals ?? []).length === 0 ? <EmptyState message="No demand data yet." /> : (
            <pre className="text-xs text-white overflow-auto max-h-64">{JSON.stringify(demand?.demand_signals, null, 2)}</pre>
          )}
        </div>

        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Cost Attribution</SectionHeader>
          {(cost?.cost_attribution ?? []).length === 0 ? <EmptyState message="No cost data yet." /> : (
            <pre className="text-xs text-white overflow-auto max-h-64">{JSON.stringify(cost?.cost_attribution, null, 2)}</pre>
          )}
        </div>

        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Utilization</SectionHeader>
          {(utilization?.utilization_patterns ?? []).length === 0 ? <EmptyState message="No utilization data yet." /> : (
            <pre className="text-xs text-white overflow-auto max-h-64">{JSON.stringify(utilization?.utilization_patterns, null, 2)}</pre>
          )}
        </div>
      </div>
    </div>
  );
}
