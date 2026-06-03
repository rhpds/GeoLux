import { useState } from 'react';
import { useMode, useSetMode, useHealth, useStabilityThresholds, useUpdateThreshold, useConstraints, useScenarios, useRunScenario } from '../api/hooks';
import SectionHeader from '../components/SectionHeader';
import MetricCard from '../components/MetricCard';

export default function Admin() {
  const health = useHealth();
  const mode = useMode();
  const setMode = useSetMode();
  const thresholds = useStabilityThresholds();
  const updateThreshold = useUpdateThreshold();
  const constraints = useConstraints();
  const scenarios = useScenarios();
  const runScenario = useRunScenario();

  const [newThreshold, setNewThreshold] = useState('');
  const [scenarioResult, setScenarioResult] = useState<Record<string, unknown> | null>(null);

  const currentMode = mode.data?.mode ?? 'live';
  const validModes = mode.data?.valid_modes ?? ['live', 'synthetic', 'replay'];

  const stageGroups = (constraints.data ?? []).reduce((acc, c) => {
    const arr = acc[c.stage] ?? [];
    arr.push(c);
    acc[c.stage] = arr;
    return acc;
  }, {} as Record<string, typeof constraints.data>);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: 'Red Hat Display' }}>Admin</h1>
        <p className="text-brand-muted">Platform configuration, mode switching, and scenario management</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Status" value={health.data?.status ?? '--'} />
        <MetricCard label="Mode" value={currentMode} />
        <MetricCard label="Threshold" value={thresholds.data?.stability_threshold?.toString() ?? '--'} />
        <MetricCard label="Constraints" value={constraints.data?.length ?? 0} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Mode Switching */}
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Operating Mode</SectionHeader>
          <div className="flex gap-2">
            {validModes.map(m => (
              <button
                key={m}
                onClick={() => setMode.mutate(m)}
                disabled={setMode.isPending}
                className={`px-4 py-2 rounded text-sm font-bold uppercase tracking-wider transition-colors ${
                  currentMode === m
                    ? 'bg-brand-primary text-white'
                    : 'bg-brand-surface text-brand-muted hover:text-white border border-brand-border'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          <p className="text-xs text-brand-muted mt-3">
            Mode switch is hot — no restart required. All components respect the current mode.
          </p>
        </div>

        {/* Stability Threshold */}
        <div className="bg-brand-card border border-brand-border rounded-lg p-4">
          <SectionHeader>Stability Threshold</SectionHeader>
          <div className="flex items-center gap-3">
            <span className="text-2xl font-bold text-white">{thresholds.data?.stability_threshold ?? '--'}</span>
            <input
              type="number"
              step="0.05"
              min="0"
              max="1"
              value={newThreshold}
              onChange={e => setNewThreshold(e.target.value)}
              placeholder="0.7"
              className="bg-brand-surface border border-brand-border rounded px-3 py-1.5 text-sm text-white w-24"
            />
            <button
              onClick={() => {
                const val = parseFloat(newThreshold);
                if (!isNaN(val) && val >= 0 && val <= 1) {
                  updateThreshold.mutate(val);
                  setNewThreshold('');
                }
              }}
              disabled={updateThreshold.isPending}
              className="px-3 py-1.5 bg-brand-green text-white rounded text-sm hover:opacity-90 disabled:opacity-50"
            >
              Set
            </button>
          </div>
        </div>
      </div>

      {/* Constraints by Stage */}
      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Constraints by Stage ({Object.keys(stageGroups).length} stages)</SectionHeader>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {Object.entries(stageGroups).sort().map(([stage, items]) => (
            <div key={stage} className="bg-brand-surface border border-brand-border rounded p-3">
              <div className="text-xs text-brand-muted font-bold uppercase">{stage}</div>
              <div className="text-lg font-bold text-white mt-1">{items!.length}</div>
              <div className="text-xs text-brand-muted">constraints</div>
            </div>
          ))}
        </div>
      </div>

      {/* Scenario Runner */}
      <div className="bg-brand-card border border-brand-border rounded-lg p-4">
        <SectionHeader>Scenario Runner</SectionHeader>
        <div className="space-y-3">
          {(scenarios.data?.scenarios ?? []).map(s => (
            <div key={s.name} className="flex items-center justify-between bg-brand-surface border border-brand-border rounded p-3">
              <div>
                <span className="text-sm text-white font-medium">{s.name}</span>
                <p className="text-xs text-brand-muted mt-0.5">{s.description}</p>
              </div>
              <button
                onClick={async () => {
                  const result = await runScenario.mutateAsync({ name: s.name });
                  setScenarioResult(result);
                }}
                disabled={runScenario.isPending}
                className="px-3 py-1.5 bg-brand-secondary text-white rounded text-sm hover:opacity-90 disabled:opacity-50"
              >
                Run
              </button>
            </div>
          ))}
        </div>
        {scenarioResult && (
          <div className="mt-4 bg-brand-surface border border-brand-border rounded p-3">
            <SectionHeader>Result</SectionHeader>
            <pre className="text-xs text-white overflow-auto max-h-48">{JSON.stringify(scenarioResult, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
