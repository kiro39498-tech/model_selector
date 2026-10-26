// Typed API client for the backend. All requests go through /api/v1.
// No secrets are ever placed in the frontend bundle.

export interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
  initial_description: string;
  created_at: string;
}

export interface Requirement {
  id: string;
  code: string;
  description: string;
  category: string;
  source: string;
  status: string;
  confidence: number | null;
  criticality: string;
  dependencies: string[];
  acceptance_criteria: string[];
}

export interface CompletenessAssessment {
  by_category: Record<string, number>;
  critical_unresolved: string[];
  missing: string[];
  ready_for_approval: boolean;
}

export interface ModelRecommendation {
  rank: number;
  model_name: string;
  provider: string;
  total_params: number | null;
  classification: string | null;
  deployment_option: string | null;
  rationale: string;
  evidence: string[];
  strengths: string[];
  weaknesses: string[];
  cost: Record<string, unknown> | null;
  confidence: number | null;
  unverified: string[];
  source_links: string[];
  verified: boolean;
}

export interface ComponentAnalysis {
  component_id: string;
  name: string;
  purpose: string;
  ai_required: boolean;
  recommended_approach: string;
  classification: string | null;
  model_recommendations: ModelRecommendation[];
  decision_rationale: string;
  evidence: string[];
  alternatives: string[];
  risks: string[];
  requirement_ids: string[];
  confidence: number | null;
  unresolved_questions: string[];
}

export interface AnalysisResponse {
  schema_version: string;
  application_summary: string;
  confirmed_requirements: string[];
  remaining_uncertainties: string[];
  components: ComponentAnalysis[];
  risks: string[];
  validation_plan: Record<string, unknown>;
  consistency_checks: string[];
  implementation_roadmap: string[];
}

export interface AnalysisRun {
  id: string;
  project_id: string;
  status: string;
  correlation_id: string | null;
  error: string | null;
  created_at: string;
}

export interface AnalysisResult {
  run: AnalysisRun;
  result: AnalysisResponse | null;
}

export interface Health {
  status: string;
  ai_configured: boolean;
  db_configured: boolean;
  classification_threshold_billions: number;
}

// ---------------------------------------------------------------------------
// Orchestrator (AI-driven, conversational SLM vs LLM decision)
// ---------------------------------------------------------------------------
export interface OrchestratorMessage {
  role: "user" | "assistant";
  content: string;
}

export interface OrchestratorRequest {
  prompt: string;
  // Prior conversation turns (the client maintains the conversation).
  conversation?: OrchestratorMessage[];
  // Optional constraints the caller cares about (e.g. "low latency").
  constraints?: string[];
}

export interface DecisionFactor {
  name: string;
  signal: string;
  weight: number;
  direction: "slm" | "llm" | "neutral";
  explanation: string;
}

export interface OrchestratorDecision {
  recommendation: "SLM" | "LLM" | "unknown";
  confidence: number;
  use_case: string;
  rationale: string;
  factors: DecisionFactor[];
  suggested_slm: string | null;
  suggested_llm: string | null;
}

export interface ClarificationQuestion {
  question: string;
  why: string;
  options: string[];
}

// The orchestrator's response: either a decision or a follow-up question.
export interface OrchestratorResponse {
  status: "decision" | "clarify";
  decision: OrchestratorDecision | null;
  question: ClarificationQuestion | null;
}

export interface OrchestratorRun {
  id: string;
  status: string;
  correlation_id: string | null;
  error: string | null;
  created_at: string;
}

export interface OrchestratorResult {
  run: OrchestratorRun;
  response: OrchestratorResponse | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      detail = body.detail || body.error || detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => request<Health>("/health"),
  createProject: (name: string, initial_description: string) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify({ name, initial_description }),
    }),
  listProjects: () => request<Project[]>("/projects"),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  listRequirements: (projectId: string) =>
    request<Requirement[]>(`/projects/${projectId}/requirements`),
  discovery: (projectId: string, message: string) =>
    request<{
      questions: string[];
      requirements: Requirement[];
      outstanding_categories: string[];
      ambiguities: string[];
    }>(`/projects/${projectId}/requirements/discovery`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  completeness: (projectId: string) =>
    request<CompletenessAssessment>(`/projects/${projectId}/requirements/completeness`),
  updateRequirement: (
    projectId: string,
    code: string,
    status: string
  ) =>
    request<Requirement>(
      `/projects/${projectId}/requirements/${code}`,
      { method: "PATCH", body: JSON.stringify({ status }) }
    ),
  approve: (projectId: string) =>
    request<{ id: string; version: number; status: string }>(
      `/projects/${projectId}/requirements/approve`,
      { method: "POST" }
    ),
  // POST /analysis returns 202 immediately with a "running" run. The client
  // then polls GET /analysis/{runId} until the run completes or fails.
  runAnalysis: (projectId: string) =>
    request<AnalysisRun>(`/projects/${projectId}/analysis`, { method: "POST" }),
  listAnalysisRuns: (projectId: string) =>
    request<AnalysisRun[]>(`/projects/${projectId}/analysis`),
  getAnalysisRun: (projectId: string, runId: string) =>
    request<AnalysisResult>(`/projects/${projectId}/analysis/${runId}`),
  listModels: () => request<unknown[]>("/models"),
  listEvaluations: (projectId: string) =>
    request<
      {
        id: string;
        status: string;
        metrics: Record<string, unknown>;
        executed: boolean;
        approved: boolean;
        dataset_version: string | null;
      }[]
    >(`/projects/${projectId}/evaluations`),
  // Orchestrator: AI-driven, conversational SLM vs LLM decision.
  // Start a decision (202); poll getDecisionRun for the result. The result
  // is either a decision or a clarification question.
  decide: (req: OrchestratorRequest) =>
    request<OrchestratorRun>("/orchestrator/decide", {
      method: "POST",
      body: JSON.stringify(req),
    }),
  getDecisionRun: (runId: string) =>
    request<OrchestratorResult>(`/orchestrator/decide/${runId}`),
  listDecisionRuns: () =>
    request<OrchestratorRun[]>("/orchestrator/decide"),
};
