import { useQuery } from '@tanstack/react-query';
import { geolux } from '../api/geolux';
import SectionHeader from '../components/SectionHeader';
import EmptyState from '../components/EmptyState';
import Badge from '../components/Badge';

export default function LaunchpadIntelligence() {
  const { data: summit } = useQuery({
    queryKey: ['summit'],
    queryFn: async () => { const r = await fetch('/governance/summit'); return r.ok ? r.json() : null; },
    refetchInterval: 60_000,
  });
  const { data: intel } = useQuery({
    queryKey: ['launchpad-catalog'],
    queryFn: () => geolux.getIntelligence('catalog_analysis'),
    refetchInterval: 60_000,
  });

  const catalog = intel?.[0]?.data_payload as Record<string, unknown> | undefined;
  const summitData = summit as Record<string, unknown> | undefined;
  const summitOverview = summitData?.['overview'] as Record<string, unknown> | undefined;
  const summitSessions = summitData?.['sandbox_sessions'] as Record<string, unknown> | undefined;
  const summitFailures = summitData?.['failure_profile'] as Array<Record<string, unknown>> | undefined;
  void summitData?.['demo_performance'];

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Launchpad Intelligence</h1>
        <p className="text-brand-muted">Provisioning patterns from RHDP ecosystem and Summit event</p>
      </div>

      {summitData && summitOverview && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <div className="flex items-center gap-3 mb-3">
            <SectionHeader>Red Hat Summit 2026</SectionHeader>
            <Badge variant="live">{String(summitData?.['dates'] ?? '')}</Badge>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Stat label="Evaluations" value={Number(summitOverview['total_evals'] || 0).toLocaleString()} />
            <Stat label="Labs" value={Number(summitOverview['total_labs'] || 0).toLocaleString()} />
            <Stat label="Clusters" value={Number(summitOverview['total_clusters'] || 0)} />
            <Stat label="Sandbox Sessions" value={Number(summitSessions?.['total'] || 0).toLocaleString()} />
            <Stat label="Pass Rate" value={`${(Number(summitOverview['passed'] || 0) / Math.max(Number(summitOverview['total_evals'] || 1), 1) * 100).toFixed(2)}%`} />
          </div>

          {Array.isArray(summitSessions?.['by_day']) && (
            <div className="mt-3 pt-3 border-t border-brand-border">
              <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">Sessions by Day</div>
              <div className="flex gap-2">
                {(summitSessions['by_day'] as Array<Record<string, unknown>>).map((d, i) => (
                  <div key={i} className="bg-brand-surface rounded p-2 text-center flex-1">
                    <div className="text-xs text-brand-muted">{String(d['date'] || '')}</div>
                    <div className="text-lg font-bold text-white">{Number(d['sessions'] || 0).toLocaleString()}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {summitFailures && summitFailures.length > 0 && (
            <div className="mt-3 pt-3 border-t border-brand-border">
              <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">Top Failures During Summit</div>
              <div className="space-y-1">
                {summitFailures.slice(0, 5).map((f, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-white font-mono">{String(f['class'] || '')}</span>
                    <span className="text-brand-muted">{Number(f['count'] || 0).toLocaleString()} across {String(f['clusters'] || 0)} clusters</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {catalog && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Catalog Analysis ({Number(catalog['total_items'] || 0)} items)</SectionHeader>
          <p className="text-xs text-brand-muted mb-3">From Launchpad catalog — demo types and hardware profile distribution</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">Categories</div>
              {catalog['categories'] != null && Object.entries(catalog['categories'] as Record<string, number>).slice(0, 5).map(([k, v]) => (
                <div key={k} className="flex justify-between text-xs mb-1">
                  <span className="text-white">{k}</span>
                  <span className="text-brand-muted">{String(v)}</span>
                </div>
              ))}
            </div>
            <div>
              <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">Hardware Tier Distribution</div>
              <div className="space-y-1">
                <TierBar label="Gaudi (macro)" count={Number(catalog['gaudi_workloads'] || 0)} total={Number(catalog['total_items'] || 1)} color="bg-orange-500" />
                <TierBar label="Xeon6 (micro)" count={Number(catalog['xeon_workloads'] || 0)} total={Number(catalog['total_items'] || 1)} color="bg-purple-500" />
                <TierBar label="CPU (nano)" count={Number(catalog['cpu_workloads'] || 0)} total={Number(catalog['total_items'] || 1)} color="bg-blue-500" />
              </div>
            </div>
            <div>
              <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">Hardware Profiles</div>
              {catalog['hardware_profiles'] != null && Object.entries(catalog['hardware_profiles'] as Record<string, number>).slice(0, 5).map(([k, v]) => (
                <div key={k} className="flex justify-between text-xs mb-1">
                  <span className="text-white">{k}</span>
                  <span className="text-brand-muted">{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {!summitData && !catalog && (
        <EmptyState message="No intelligence data available. Launchpad catalog miner runs hourly. Summit data mines on first request to /governance/summit." />
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-brand-surface rounded p-2">
      <div className="text-xl font-bold text-white" style={{ fontFamily: 'Red Hat Display' }}>{value}</div>
      <div className="text-xs text-brand-muted">{label}</div>
    </div>
  );
}

function TierBar({ label, count, total, color }: { label: string; count: number; total: number; color: string }) {
  const pct = (count / Math.max(total, 1)) * 100;
  return (
    <div>
      <div className="flex justify-between text-xs mb-0.5">
        <span className="text-white">{label}</span>
        <span className="text-brand-muted">{count}</span>
      </div>
      <div className="h-2 bg-brand-surface rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
