export interface StabilityScore {
  call_id: string;
  endpoint: string;
  model: string;
  stability_score: number;
  stability_method: string;
  stability_threshold: number;
  stability_state: string;
  created_at: string;
}

export interface Hypothesis {
  hypothesis_id: string;
  claim: string;
  testable_conditions: TestableCondition[];
  confidence_score: number;
  geometric_stability_score: number;
  geometric_stability_state: string;
  validation_outcome: string | null;
  created_at: string;
}

export interface TestableCondition {
  field: string;
  operator: string;
  value: unknown;
}

export interface HypothesisQueue {
  hypotheses: Hypothesis[];
  total: number;
}

export interface ConstraintSummary {
  constraint_id: string;
  constraint_name: string;
  stage: string;
  assertion_type: string;
  severity: string;
  version: number;
}

export interface ClassificationResult {
  classification_id: string;
  constraint_id: string;
  result: string;
  confidence_score: number;
  geometric_stability_score: number | null;
  evidence_chain: Record<string, unknown>;
  llm_interpretation_used: boolean;
}

export interface MPCCycle {
  cycle_id: string;
  cluster_id: string;
  horizon: number;
  optimization_score: number;
  horizon_adjusted: boolean;
  suspended: boolean;
  created_at: string;
}

export interface RoutingDecision {
  routing_id: string;
  workload_id: string;
  tier_assignment: string;
  substrate: string;
  confidence_score: number;
  override: boolean;
  created_at: string;
}

export interface TierDefinition {
  name: string;
  substrate: string;
  agent_type: string;
  governance_surface: string;
}

export interface ModeInfo {
  mode: string;
  valid_modes: string[];
}

export interface HealthStatus {
  status: string;
  mode: string;
  service: string;
}

export interface IntelligenceRecord {
  intelligence_id: string;
  intelligence_type: string;
  data_payload: unknown;
  time_window_start: string;
  time_window_end: string;
  confidence: number | null;
  created_at: string;
}

export interface ScenarioInfo {
  name: string;
  description: string;
}
