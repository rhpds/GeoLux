import { useDemandSignals, useCostAttribution, useUtilization } from '../api/hooks';
import SectionHeader from '../components/SectionHeader';
import EmptyState from '../components/EmptyState';

export default function LaunchpadIntelligence() {
  const { data: demand } = useDemandSignals();
  const { data: cost } = useCostAttribution();
  const { data: utilization } = useUtilization();

  const demandData = (demand?.demand_signals ?? []) as Array<Record<string, unknown>>;
  const costData = (cost?.cost_attribution ?? []) as Array<Record<string, unknown>>;
  const utilData = (utilization?.utilization_patterns ?? []) as Array<Record<string, unknown>>;

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Launchpad Intelligence</h1>
        <p className="text-brand-muted">Provisioning patterns mined from RHDP ecosystem</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Demand Signals</SectionHeader>
          {demandData.length === 0 ? <EmptyState message="No demand data yet." /> : (
            <div className="space-y-3">
              {demandData.map((signal, i) => (
                <div key={i} className="space-y-2">
                  {renderIntelligenceSection("Most Requested", signal, "most_requested_demos", ["demo_id", "count"])}
                  {renderIntelligenceSection("Failing Configs", signal, "highest_failure_configs", ["config", "count"])}
                  {renderList("Returning Partners", signal, "returning_partners")}
                  {signal.total_sessions != null && (
                    <div className="text-xs text-brand-muted pt-1 border-t border-brand-border">
                      Total sessions: <span className="text-white">{String(signal.total_sessions)}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Cost Attribution</SectionHeader>
          {costData.length === 0 ? <EmptyState message="No cost data yet." /> : (
            <div className="space-y-3">
              {costData.map((c, i) => (
                <div key={i} className="space-y-2">
                  {renderIntelligenceSection("Per Lab", c, "per_lab_session", ["lab_code", "total_cost"])}
                  {renderIntelligenceSection("Per SA", c, "per_sa", ["sa_id", "total_cost"])}
                  {renderIntelligenceSection("Per Hardware", c, "per_hardware_config", ["config", "total_cost"])}
                  {c.total_cost != null && (
                    <div className="text-xs text-brand-muted pt-1 border-t border-brand-border">
                      Total cost: <span className="text-white font-bold">${String(c.total_cost)}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Utilization</SectionHeader>
          {utilData.length === 0 ? <EmptyState message="No utilization data yet." /> : (
            <div className="space-y-3">
              {utilData.map((u, i) => (
                <div key={i} className="space-y-2">
                  {renderIntelligenceSection("Peak Hours", u, "peak_demand_windows", ["hour", "count"])}
                  {renderList("Underutilized", u, "underutilized_configs")}
                  {u.idle_time_hours != null && (
                    <div className="text-xs text-brand-muted pt-1 border-t border-brand-border">
                      Idle hours: <span className="text-white">{String(u.idle_time_hours)}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function renderIntelligenceSection(label: string, data: Record<string, unknown>, key: string, columns: [string, string]) {
  const items = data[key];
  if (!Array.isArray(items) || items.length === 0) return null;
  return (
    <div>
      <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-1">{label}</div>
      <div className="space-y-0.5">
        {(items as Array<Record<string, unknown>>).slice(0, 5).map((item, i) => (
          <div key={i} className="flex justify-between text-xs">
            <span className="text-white truncate max-w-[120px]">{String(item[columns[0]] ?? '')}</span>
            <span className="text-brand-muted">{String(item[columns[1]] ?? '')}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function renderList(label: string, data: Record<string, unknown>, key: string) {
  const items = data[key];
  if (!Array.isArray(items) || items.length === 0) return null;
  return (
    <div>
      <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-1">{label}</div>
      <div className="flex flex-wrap gap-1">
        {(items as string[]).slice(0, 8).map((item, i) => (
          <span key={i} className="text-xs bg-brand-surface px-1.5 py-0.5 rounded text-white">{item}</span>
        ))}
      </div>
    </div>
  );
}
