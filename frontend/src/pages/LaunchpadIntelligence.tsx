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
  const s = summit as Record<string, unknown> | undefined;
  const overview = s?.['overview'] as Record<string, unknown> | undefined;
  const labs = s?.['labs'] as Record<string, unknown> | undefined;
  const evals = s?.['evaluations'] as Record<string, unknown> | undefined;
  const aap = s?.['aap'] as Record<string, unknown> | undefined;
  const clusters = s?.['clusters'] as Array<Record<string, unknown>> | undefined;
  const failureBreakdown = s?.['failure_breakdown'] as Record<string, unknown> | undefined;
  const correlation = s?.['correlation'] as Array<Record<string, unknown>> | undefined;
  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Launchpad Intelligence</h1>
        <p className="text-brand-muted">Summit lab inventory and GeoLux classification governance</p>
      </div>

      {s && overview && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <div className="flex items-center gap-3 mb-3">
            <SectionHeader>{String(s['event'] || 'Red Hat Summit 2026')}</SectionHeader>
            <Badge variant="live">{String(s['dates'] ?? '')}</Badge>
            {s['location'] ? <span className="text-xs text-brand-muted">{String(s['location'])}</span> : null}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Labs (Labagator)" value={Number(overview['total_labs'] || 0)} />
            <Stat label="AAP Jobs" value={Number(overview['total_aap_jobs'] || 0).toLocaleString()} />
            <Stat label="AAP Success" value={`${Number(overview['aap_success_rate'] || 0)}%`} />
            <Stat label="Evaluations" value={Number(overview['total_evals'] || 0).toLocaleString()} />
          </div>
        </div>
      )}

      {aap && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>AAP Provisioning ({Number(aap['total_jobs'] || 0).toLocaleString()} jobs)</SectionHeader>
          <p className="text-xs text-brand-muted mb-3">Ansible Automation Platform — provision + destroy jobs across Summit week</p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Stat label="Total Jobs" value={Number(aap['total_jobs'] || 0).toLocaleString()} />
            <Stat label="Failed" value={Number(aap['total_failed'] || 0).toLocaleString()} />
            <Stat label="Success Rate" value={`${Number(aap['overall_success_rate'] || 0)}%`} />
            <Stat
              label="Destroy Failures"
              value={Number((failureBreakdown?.['by_type'] as Record<string, number> | undefined)?.['destroy'] || 0).toLocaleString()}
            />
          </div>

          {aap['by_day'] && typeof aap['by_day'] === 'object' ? (
            <div className="mb-4">
              <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">Daily Breakdown</div>
              <div className="flex gap-2">
                {Object.entries(aap['by_day'] as Record<string, Record<string, unknown>>).map(([date, info]) => (
                  <div key={date} className="bg-brand-surface rounded p-3 text-center flex-1">
                    <div className="text-xs text-brand-muted">{date}</div>
                    <div className="text-lg font-bold text-white">{Number(info['success_rate'] || 0)}%</div>
                    <div className="text-xs text-brand-muted">{Number(info['total'] || 0).toLocaleString()} jobs</div>
                    <div className="text-xs text-red-400">{Number(info['failed'] || 0).toLocaleString()} failed</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {failureBreakdown?.['by_type'] ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">Failure by Type</div>
                {Object.entries(failureBreakdown['by_type'] as Record<string, number>).map(([type, count]) => (
                  <div key={type} className="flex justify-between text-xs mb-1">
                    <span className={`font-mono ${type === 'destroy' ? 'text-red-400' : type === 'provision' ? 'text-yellow-400' : 'text-brand-muted'}`}>{type}</span>
                    <span className="text-white">{count.toLocaleString()}</span>
                  </div>
                ))}
                {failureBreakdown['avg_duration_minutes'] ? (
                  <div className="mt-2 text-xs text-brand-muted">
                    Avg duration: {String(failureBreakdown['avg_duration_minutes'])}min | Max: {String(failureBreakdown['max_duration_minutes'])}min
                  </div>
                ) : null}
              </div>
              {aap['top_playbooks'] && typeof aap['top_playbooks'] === 'object' ? (
                <div>
                  <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">Failing Playbooks</div>
                  {Object.entries(aap['top_playbooks'] as Record<string, number>).map(([pb, count]) => (
                    <div key={pb} className="flex justify-between text-xs mb-1">
                      <span className="text-white font-mono">{pb}</span>
                      <span className="text-red-400">{count}</span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {aap['top_failing_labs'] && typeof aap['top_failing_labs'] === 'object' ? (
            <div>
              <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">Top Failing Labs (AAP)</div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-brand-muted border-b border-brand-border">
                      <th className="pb-2 pr-4">Lab</th>
                      <th className="pb-2 pr-4 text-right">Failed</th>
                      <th className="pb-2 pr-4 text-right">Provision</th>
                      <th className="pb-2 text-right">Destroy</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(aap['top_failing_labs'] as Record<string, Record<string, unknown>>).slice(0, 15).map(([lab, info]) => (
                      <tr key={lab} className="border-b border-brand-border/50">
                        <td className="py-1.5 pr-4 font-mono text-white">{lab}</td>
                        <td className="py-1.5 pr-4 text-right text-red-400">{Number(info['failed'] || 0)}</td>
                        <td className="py-1.5 pr-4 text-right text-yellow-400">{Number(info['provision_failures'] || 0)}</td>
                        <td className="py-1.5 text-right text-red-400">{Number(info['destroy_failures'] || 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {evals && Number(evals['total'] || 0) > 0 && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Evaluations ({Number(evals['total'] || 0).toLocaleString()})</SectionHeader>
          <p className="text-xs text-brand-muted mb-3">Stargate evaluations during Summit week — {Number(evals['pass_rate'] || 0)}% pass rate</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {evals['outcomes'] ? (
              <div>
                <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">Outcomes</div>
                {Object.entries(evals['outcomes'] as Record<string, number>).map(([outcome, count]) => (
                  <div key={outcome} className="flex justify-between text-xs mb-1">
                    <span className={`font-mono ${outcome === 'pass' ? 'text-green-400' : outcome === 'fail' ? 'text-red-400' : 'text-yellow-400'}`}>{outcome}</span>
                    <span className="text-white">{count.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            ) : null}
            {evals['failure_classes'] ? (
              <div>
                <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">Failure Classes</div>
                {Object.entries(evals['failure_classes'] as Record<string, number>).slice(0, 8).map(([cls, count]) => (
                  <div key={cls} className="flex justify-between text-xs mb-1">
                    <span className="text-white font-mono">{cls}</span>
                    <span className="text-red-400">{count}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      )}

      {clusters && clusters.length > 0 && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Cluster Performance</SectionHeader>
          <div className="flex flex-wrap gap-2">
            {clusters.map((c, i) => {
              const rate = Number(c['pass_rate'] || 0);
              return (
                <div key={i} className="bg-brand-surface rounded-lg p-3 min-w-[140px]">
                  <div className="text-sm font-mono text-white">{String(c['cluster'] || '')}</div>
                  <div className={`text-lg font-bold ${rate >= 50 ? 'text-green-400' : rate >= 30 ? 'text-yellow-400' : 'text-red-400'}`}>{rate}%</div>
                  <div className="text-xs text-brand-muted">{Number(c['total_evals'] || 0).toLocaleString()} evals</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {correlation && correlation.length > 0 && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>AAP / Evaluation Cross-Reference</SectionHeader>
          <p className="text-xs text-brand-muted mb-3">Labs with failures in both AAP provisioning and Stargate evaluation</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-brand-muted border-b border-brand-border">
                  <th className="pb-2 pr-4">Lab Type</th>
                  <th className="pb-2 pr-4 text-right">AAP Failed</th>
                  <th className="pb-2 pr-4 text-right">Provision</th>
                  <th className="pb-2 pr-4 text-right">Destroy</th>
                  <th className="pb-2 pr-4 text-right">Eval Failed</th>
                  <th className="pb-2 text-right">Eval Total</th>
                </tr>
              </thead>
              <tbody>
                {correlation.map((c, i) => (
                  <tr key={i} className="border-b border-brand-border/50">
                    <td className="py-1.5 pr-4 font-mono text-white">
                      {String(c['lab_type'] || c['catalog_prefix'] || '')}
                      {c['correlated'] ? <span className="ml-1 text-yellow-400 text-[10px]">CORRELATED</span> : null}
                    </td>
                    <td className="py-1.5 pr-4 text-right text-red-400">{Number(c['aap_failed'] || 0)}</td>
                    <td className="py-1.5 pr-4 text-right text-yellow-400">{Number(c['aap_provision'] || c['provision_failures'] || 0)}</td>
                    <td className="py-1.5 pr-4 text-right text-red-400">{Number(c['aap_destroy'] || c['destroy_failures'] || 0)}</td>
                    <td className="py-1.5 pr-4 text-right text-red-400">{Number(c['eval_failed'] || 0)}</td>
                    <td className="py-1.5 text-right text-brand-muted">{Number(c['eval_total'] || 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {labs && (
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Summit Labs ({Number(labs['total'] || 0)})</SectionHeader>
          <p className="text-xs text-brand-muted mb-3">Lab inventory from Labagator</p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            {labs['by_status'] ? (
              <div>
                <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">By Status</div>
                {Object.entries(labs['by_status'] as Record<string, number>).map(([k, v]) => (
                  <div key={k} className="flex justify-between text-xs mb-1">
                    <span className="text-white">{k}</span><span className="text-brand-muted">{v}</span>
                  </div>
                ))}
              </div>
            ) : null}
            {labs['by_cloud'] ? (
              <div>
                <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">By Cloud</div>
                {Object.entries(labs['by_cloud'] as Record<string, number>).map(([k, v]) => (
                  <div key={k} className="flex justify-between text-xs mb-1">
                    <span className="text-white">{k}</span><span className="text-brand-muted">{v}</span>
                  </div>
                ))}
              </div>
            ) : null}
            {labs['by_env_type'] ? (
              <div>
                <div className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-2">By Environment</div>
                {Object.entries(labs['by_env_type'] as Record<string, number>).map(([k, v]) => (
                  <div key={k} className="flex justify-between text-xs mb-1">
                    <span className="text-white">{k}</span><span className="text-brand-muted">{v}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          {Array.isArray(labs['lab_list']) && (
            <details>
              <summary className="text-xs text-brand-muted cursor-pointer mb-2">Show all {Number(labs['total'] || 0)} labs</summary>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-brand-muted border-b border-brand-border">
                      <th className="pb-2 pr-4">Code</th>
                      <th className="pb-2 pr-4">Title</th>
                      <th className="pb-2 pr-4">Status</th>
                      <th className="pb-2">Cloud</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(labs['lab_list'] as Array<Record<string, unknown>>).map((lab, i) => (
                      <tr key={i} className="border-b border-brand-border/50">
                        <td className="py-1.5 pr-4 font-mono text-blue-400">{String(lab['lab_code'] || '')}</td>
                        <td className="py-1.5 pr-4 text-white max-w-md truncate">{String(lab['title'] || '')}</td>
                        <td className="py-1.5 pr-4">
                          <span className={`px-1.5 py-0.5 rounded text-xs ${
                            lab['status'] === 'ready' ? 'bg-green-500/20 text-green-400' :
                            lab['status'] === 'in_development' ? 'bg-blue-500/20 text-blue-400' :
                            'bg-yellow-500/20 text-yellow-400'
                          }`}>{String(lab['status'] || '')}</span>
                        </td>
                        <td className="py-1.5 text-brand-muted">{String(lab['cloud'] || '')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
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
                  <span className="text-white">{k}</span><span className="text-brand-muted">{String(v)}</span>
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
                  <span className="text-white">{k}</span><span className="text-brand-muted">{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {!s && !catalog && (
        <EmptyState message="No intelligence data available. Summit data mines on first request to /governance/summit." />
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
