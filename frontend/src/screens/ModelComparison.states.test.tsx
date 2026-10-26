import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import ModelComparison from "./ModelComparison";

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

describe("ModelComparison states", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading state while the analysis is loading", async () => {
    // No runs yet -> the component shows "Loading analysis…".
    vi.mocked(api.listAnalysisRuns).mockResolvedValue([]);
    renderAt("/projects/p1/models");
    expect(screen.getByText("Loading analysis…")).toBeInTheDocument();
  });

  it("shows an empty state when there are no AI components with recommendations", async () => {
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
    vi.mocked(api.getAnalysisRun).mockResolvedValue({
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
        application_summary: "x",
        confirmed_requirements: [],
        remaining_uncertainties: [],
        components: [
          {
            component_id: "C-001",
            name: "Auth",
            purpose: "p",
            ai_required: false,
            recommended_approach: "deterministic",
            classification: null,
            decision_rationale: "",
            evidence: [],
            alternatives: [],
            risks: [],
            requirement_ids: [],
            confidence: null,
            unresolved_questions: [],
            model_recommendations: [],
          },
        ],
        risks: [],
        validation_plan: {},
        consistency_checks: [],
        implementation_roadmap: [],
      },
    });
    renderAt("/projects/p1/models");
    // The header renders; no candidate cards are shown for non-AI components.
    expect(screen.getByText("Model comparison")).toBeInTheDocument();
    expect(screen.queryByText("Llama 3.1 8B")).not.toBeInTheDocument();
  });

  it("handles an error from the API without crashing", async () => {
    vi.mocked(api.listAnalysisRuns).mockRejectedValue(
      new Error("network down")
    );
    renderAt("/projects/p1/models");
    // The component still renders its header (graceful degradation).
    expect(screen.getByText("Model comparison")).toBeInTheDocument();
  });
});
