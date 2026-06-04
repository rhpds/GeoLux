import type {
  StabilityScore,
  Hypothesis,
  HypothesisQueue,
  ConstraintSummary,
  ClassificationDetail,
  MPCCycle,
  MPCCycleDetail,
  RoutingDecision,
  TierDefinition,
  ModeInfo,
  HealthStatus,
  IntelligenceRecord,
  ScenarioInfo,
  GovernancePipeline,
} from './types';

const GEOLUX_BASE = import.meta.env.VITE_GEOLUX_URL || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(options?.body ? { 'Content-Type': 'application/json' } : {}),
    ...(options?.headers as Record<string, string> || {}),
  };
  const response = await fetch(`${GEOLUX_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body.detail) detail = body.detail;
    } catch { /* ignore */ }
    throw new Error(`GeoLux API error: ${response.status} ${detail}`);
  }
  return response.json();
}

export const geolux = {
  getHealth: () => request<HealthStatus>('/health'),
  getMode: () => request<ModeInfo>('/mode'),
  setMode: (mode: string) =>
    request<{ mode: string }>('/mode', { method: 'PUT', body: JSON.stringify({ mode }) }),

  getStabilityScores: (endpoint?: string, limit = 100) => {
    const params = new URLSearchParams();
    if (endpoint) params.set('endpoint', endpoint);
    params.set('limit', String(limit));
    return request<StabilityScore[]>(`/stability/scores?${params}`);
  },
  getStabilityThresholds: () =>
    request<{ stability_threshold: number }>('/stability/thresholds'),
  updateStabilityThreshold: (threshold: number) =>
    request<{ stability_threshold: number }>('/stability/thresholds', {
      method: 'PUT', body: JSON.stringify({ threshold }),
    }),

  getHypothesisQueue: (limit = 50) =>
    request<HypothesisQueue>(`/hypotheses/queue?limit=${limit}`),
  getHypothesis: (id: string) => request<Hypothesis>(`/hypotheses/${id}`),
  searchHypotheses: (params: { cluster?: string; failure_class?: string; validation?: string; q?: string; limit?: number }) => {
    const p = new URLSearchParams();
    if (params.cluster) p.set('cluster', params.cluster);
    if (params.failure_class) p.set('failure_class', params.failure_class);
    if (params.validation) p.set('validation', params.validation);
    if (params.q) p.set('q', params.q);
    p.set('limit', String(params.limit ?? 50));
    return request<HypothesisQueue & { filtered: boolean }>(`/hypotheses/search?${p}`);
  },
  getHypothesisStats: () => request<{
    total: number; pending: number; validated: number; falsified: number;
    clusters: Array<{ name: string; count: number }>;
    failure_classes: Array<{ name: string; count: number }>;
  }>('/hypotheses/stats'),

  getConstraints: (stage?: string) => {
    const params = stage ? `?stage=${encodeURIComponent(stage)}` : '';
    return request<ConstraintSummary[]>(`/classify/constraints${params}`);
  },

  getMPCCycles: (clusterId?: string, limit = 50) => {
    const params = new URLSearchParams();
    if (clusterId) params.set('cluster_id', clusterId);
    params.set('limit', String(limit));
    return request<MPCCycle[]>(`/mpc/cycles?${params}`);
  },
  getMPCCycle: (cycleId: string) =>
    request<MPCCycleDetail>(`/mpc/cycles/${cycleId}`),

  getRecentClassifications: (stage?: string, limit = 20) => {
    const params = new URLSearchParams();
    if (stage) params.set('stage', stage);
    params.set('limit', String(limit));
    return request<ClassificationDetail[]>(`/classify/recent?${params}`);
  },

  getRoutingHistory: (limit = 100) =>
    request<RoutingDecision[]>(`/deepfield/routing-history?limit=${limit}`),
  getTiers: () =>
    request<{ tiers: TierDefinition[] }>('/deepfield/tiers'),

  getIntelligence: (type?: string, limit = 50) => {
    const params = new URLSearchParams();
    if (type) params.set('intelligence_type', type);
    params.set('limit', String(limit));
    return request<IntelligenceRecord[]>(`/launchpad/intelligence?${params}`);
  },
  getDemandSignals: () =>
    request<{ demand_signals: unknown[] }>('/launchpad/demand'),
  getCostAttribution: () =>
    request<{ cost_attribution: unknown[] }>('/launchpad/cost'),
  getUtilization: () =>
    request<{ utilization_patterns: unknown[] }>('/launchpad/utilization'),

  getGovernancePipeline: () => request<GovernancePipeline>('/governance/pipeline'),

  getScenarios: () =>
    request<{ scenarios: ScenarioInfo[] }>('/scenarios/list'),
  runScenario: (name: string, speed = 1.0) =>
    request<Record<string, unknown>>('/scenarios/run', {
      method: 'POST',
      body: JSON.stringify({ scenario_name: name, speed_multiplier: speed }),
    }),
};
