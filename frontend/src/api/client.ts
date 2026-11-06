// API client for Person B backend
import axios from "axios";
import type {
  SituationRecord,
  Recommendation,
  MerchantTimeline,
  ExecutionState,
  CaseRecord,
  ScenarioLoadResponse,
  Scenario,
} from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8765";

const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
});

// Situation
export const getSituation = (merchantId: string): Promise<SituationRecord> =>
  api.get(`/api/merchants/${merchantId}/situation`).then((r) => r.data);

// Recommendation
export const getRecommendation = (situationId: string): Promise<Recommendation> =>
  api.get(`/api/situations/${situationId}/recommendation`).then((r) => r.data);

// Approval
export const approveAction = (actionId: string): Promise<{ status: string; new_state: string }> =>
  api.post(`/api/actions/${actionId}/approve`).then((r) => r.data);

export const rejectAction = (actionId: string): Promise<{ status: string; new_state: string }> =>
  api.post(`/api/actions/${actionId}/reject`).then((r) => r.data);

// Timeline
export const getTimeline = (merchantId: string): Promise<MerchantTimeline> =>
  api.get(`/api/merchants/${merchantId}/timeline`).then((r) => r.data);

// Simulated clock
export const advanceSimulation = (days: number): Promise<{ simulated_days: number; label: string }> =>
  api.post("/api/sim/advance", { days }).then((r) => r.data);

// Cases
export const getCase = (caseId: string): Promise<CaseRecord> =>
  api.get(`/api/cases/${caseId}`).then((r) => r.data);

// Scenario loading
export const loadScenario = (
  merchantId: string,
  scenario: Scenario
): Promise<ScenarioLoadResponse> =>
  api.post(`/api/merchants/${merchantId}/scenario`, { scenario }).then((r) => r.data);

// Health check
export const healthCheck = (): Promise<{ status: string }> =>
  api.get("/health").then((r) => r.data);

export default api;