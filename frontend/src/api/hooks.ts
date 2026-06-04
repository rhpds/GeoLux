import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { geolux } from './geolux';

export function useHealth() {
  return useQuery({ queryKey: ['health'], queryFn: geolux.getHealth, refetchInterval: 30_000 });
}

export function useMode() {
  return useQuery({ queryKey: ['mode'], queryFn: geolux.getMode, refetchInterval: 10_000 });
}

export function useSetMode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (mode: string) => geolux.setMode(mode),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['mode'] }); qc.invalidateQueries({ queryKey: ['health'] }); },
  });
}

export function useStabilityScores(endpoint?: string, limit = 50) {
  return useQuery({ queryKey: ['stability-scores', endpoint, limit], queryFn: () => geolux.getStabilityScores(endpoint, limit), refetchInterval: 15_000 });
}

export function useStabilityThresholds() {
  return useQuery({ queryKey: ['stability-thresholds'], queryFn: geolux.getStabilityThresholds });
}

export function useUpdateThreshold() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (threshold: number) => geolux.updateStabilityThreshold(threshold),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['stability-thresholds'] }),
  });
}

export function useHypothesisQueue(limit = 50) {
  return useQuery({ queryKey: ['hypothesis-queue', limit], queryFn: () => geolux.getHypothesisQueue(limit), refetchInterval: 15_000 });
}

export function useMPCCycle(cycleId: string) {
  return useQuery({ queryKey: ['mpc-cycle', cycleId], queryFn: () => geolux.getMPCCycle(cycleId), enabled: !!cycleId });
}

export function useRecentClassifications(stage?: string, limit = 20) {
  return useQuery({ queryKey: ['recent-classifications', stage, limit], queryFn: () => geolux.getRecentClassifications(stage, limit), refetchInterval: 15_000 });
}

export function useHypothesis(id: string) {
  return useQuery({ queryKey: ['hypothesis', id], queryFn: () => geolux.getHypothesis(id), enabled: !!id });
}

export function useConstraints(stage?: string) {
  return useQuery({ queryKey: ['constraints', stage], queryFn: () => geolux.getConstraints(stage) });
}

export function useMPCCycles(clusterId?: string, limit = 50) {
  return useQuery({ queryKey: ['mpc-cycles', clusterId, limit], queryFn: () => geolux.getMPCCycles(clusterId, limit), refetchInterval: 15_000 });
}

export function useRoutingHistory(limit = 100) {
  return useQuery({ queryKey: ['routing-history', limit], queryFn: () => geolux.getRoutingHistory(limit), refetchInterval: 15_000 });
}

export function useTiers() {
  return useQuery({ queryKey: ['tiers'], queryFn: geolux.getTiers });
}

export function useIntelligence(type?: string) {
  return useQuery({ queryKey: ['intelligence', type], queryFn: () => geolux.getIntelligence(type), refetchInterval: 60_000 });
}

export function useDemandSignals() {
  return useQuery({ queryKey: ['demand-signals'], queryFn: geolux.getDemandSignals, refetchInterval: 60_000 });
}

export function useCostAttribution() {
  return useQuery({ queryKey: ['cost-attribution'], queryFn: geolux.getCostAttribution, refetchInterval: 60_000 });
}

export function useUtilization() {
  return useQuery({ queryKey: ['utilization'], queryFn: geolux.getUtilization, refetchInterval: 60_000 });
}

export function useGovernancePipeline() {
  return useQuery({ queryKey: ['governance-pipeline'], queryFn: geolux.getGovernancePipeline, refetchInterval: 30_000 });
}

export function useScenarios() {
  return useQuery({ queryKey: ['scenarios'], queryFn: geolux.getScenarios });
}

export function useRunScenario() {
  return useMutation({ mutationFn: ({ name, speed }: { name: string; speed?: number }) => geolux.runScenario(name, speed) });
}
