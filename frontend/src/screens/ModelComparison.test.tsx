import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import ModelComparison from "./ModelComparison";

// Deterministic mock of the API. This is NOT live integration.
vi.mock("../api", () => ({
  api: {
    listAnalysisRuns: vi.fn(),
    getAnalysisRun: vi.fn(),
  },
}));

import { api } from "../api";

function renderAt(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <ModelComparison />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const sampleResult = {
  run: {
    id: "run-1",
    project_id: "p1",
    status: "completed",
    correlation_id: "c1",
    error: null,
    created_at: "2026-10-20T00:00:00Z",
  },
  result: {
    schema_version: "1.0",
    application_summary: "Support assistant",
    confirmed_requirements: [],
    remaining_uncertainties: [],
    components: [
      {
        component_id: "C-001",
        name: "Intent classification",
        purpose: "Classify intent",
        ai_required: true,
        recommended_approach: "slm",
        classification: "SLM",
        decision_rationale: "Routine classification",
        evidence: [],
        alternatives: [],
        risks: [],
        requirement_ids: [],
        confidence: 0.7,
        unresolved_questions: [],
        model_recommendations: [
          {
            rank: 1,
            model_name: "Llama 3.1 8B",
            provider: "Meta",
            total_params: 8_000_000_000,
            classification: "SLM",
            deployment_option: "self_hosted",
            rationale: "Small and fast",
            evidence: ["Official model card"],
            strengths: ["Low latency"],
            weaknesses: ["Limited reasoning"],
            cost: null,
            confidence: 0.7,
            unverified: [],
            source_links: ["https://ai.meta.com/llama/llama3_1/"],
            verified: true,
          },
          {
            rank: 2,
            model_name: "Mistral 7B",
            provider: "Mistral AI",
            total_params: 7_000_000_000,
            classification: "SLM",
            deployment_option: "self_hosted",
            rationale: "Permissive license",
            evidence: [],
            strengths: [],
            weaknesses: [],
            cost: null,
            confidence: 0.6,
            unverified: [],
            source_links: [],
            verified: true,
          },
          {
            rank: 3,
            model_name: "Llama 3.1 70B",
            provider: "Meta",
            total_params: 70_000_000_000,
            classification: "SLM",
            deployment_option: "self_hosted",
            rationale: "Larger SLM",
            evidence: [],
            strengths: [],
            weaknesses: [],
            cost: null,
            confidence: 0.5,
            unverified: ["benchmark not measured"],
            source_links: [],
            verified: false,
          },
        ],
      },
    ],
    risks: [],
    validation_plan: {},
    consistency_checks: [],
    implementation_roadmap: [],
  },
};

beforeEach(() => {
  vi.mocked(api.listAnalysisRuns).mockResolvedValue([
    {
      id: "run-1",
      project_id: "p1",
      status: "completed",
      correlation_id: "c1",
      error: null,
      created_at: "2026-10-20T00:00:00Z",
    },
  ]);
  vi.mocked(api.getAnalysisRun).mockResolvedValue(sampleResult);
});

describe("ModelComparison", () => {
  it("renders three ranked recommendations", async () => {
    renderAt("/projects/p1/models");
    // Rank badges.
    expect(await screen.findByText("#1")).toBeInTheDocument();
    expect(screen.getByText("#2")).toBeInTheDocument();
    expect(screen.getByText("#3")).toBeInTheDocument();
  });

  it("renders the model names", async () => {
    renderAt("/projects/p1/models");
    expect(await screen.findByText("Llama 3.1 8B")).toBeInTheDocument();
    expect(screen.getByText("Mistral 7B")).toBeInTheDocument();
    expect(screen.getByText("Llama 3.1 70B")).toBeInTheDocument();
  });

  it("shows SLM classification", async () => {
    renderAt("/projects/p1/models");
    await screen.findByText("Llama 3.1 8B");
    // "SLM" appears as a classification value for each candidate.
    expect(screen.getAllByText("SLM").length).toBeGreaterThanOrEqual(3);
  });

  it("distinguishes verified from unverified candidates", async () => {
    renderAt("/projects/p1/models");
    await screen.findByText("Llama 3.1 8B");
    // Two verified, one unverified.
    expect(screen.getAllByText("verified").length).toBe(2);
    expect(screen.getByText("unverified")).toBeInTheDocument();
  });

  it("shows unverified items distinctly", async () => {
    renderAt("/projects/p1/models");
    expect(await screen.findByText("benchmark not measured")).toBeInTheDocument();
  });
});
