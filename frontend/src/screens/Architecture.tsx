import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import ReactFlow, { Background, type Node, type Edge } from "reactflow";
import "reactflow/dist/style.css";
import { api, type AnalysisResponse, type ComponentAnalysis } from "../api";
import { Badge, Button, Card, ErrorState, Loading } from "../components/ui";

export default function Architecture() {
  const { projectId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<ComponentAnalysis | null>(null);
  const [showAiOnly, setShowAiOnly] = useState(false);

  // Poll the run list while the latest run is still "running".
  const { data: latestRun } = useQuery({
    queryKey: ["analysis-runs", projectId],
    queryFn: () => api.listAnalysisRuns(projectId),
    retry: false,
    refetchInterval: (query) =>
      query.state.data?.[0]?.status === "running" ? 3000 : false,
  });

  // Poll the run detail while it is still "running" (result is null until done).
  const { data: result } = useQuery({
    queryKey: ["analysis-run", projectId, latestRun?.[0]?.id],
    queryFn: () => api.getAnalysisRun(projectId, latestRun![0].id),
    enabled: !!latestRun && latestRun.length > 0,
    retry: false,
    refetchInterval: (query) =>
      query.state.data?.run?.status === "running" ? 3000 : false,
  });

  const runAnalysis = useMutation({
    mutationFn: () => api.runAnalysis(projectId),
    onSuccess: () => {
      // The run is now "running"; invalidate so polling picks it up.
      queryClient.invalidateQueries({ queryKey: ["analysis-runs", projectId] });
    },
  });

  const isAnalyzing = latestRun?.[0]?.status === "running";
  const analysis: AnalysisResponse | null = result?.result ?? null;
  const components = analysis?.components ?? [];

  // Build graph nodes/edges from components.
  const visible = showAiOnly
    ? components.filter((c) => c.ai_required)
    : components;

  const nodes: Node[] = visible.map((c, i) => ({
    id: c.component_id,
    position: { x: (i % 3) * 260, y: Math.floor(i / 3) * 160 },
    data: { label: c.name },
    style: {
      backgroundColor: c.ai_required ? "#eef2ff" : "#ffffff",
      border: c.ai_required ? "1px solid #4f46e5" : "1px solid #e5e7eb",
    },
  }));
  const edges: Edge[] = [];

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Architecture</h1>
          <p className="mt-1 text-sm text-muted">
            Interactive component graph. Click a component to see its model
            recommendations.
          </p>
        </div>
        <Button
          onClick={() => runAnalysis.mutate()}
          disabled={runAnalysis.isPending || isAnalyzing}
        >
          {runAnalysis.isPending || isAnalyzing ? "Analyzing…" : "Run analysis"}
        </Button>
      </header>

      {runAnalysis.isError && (
        <div className="mb-4">
          <ErrorState message={(runAnalysis.error as Error).message} />
        </div>
      )}

      {isAnalyzing && (
        <div className="mb-4">
          <Loading label="Analyzing… this can take a few minutes." />
        </div>
      )}

      {result?.run?.status === "failed" && (
        <div className="mb-4">
          <ErrorState
            message={
              result.run.error ||
              "Analysis failed. Please try again."
            }
          />
        </div>
      )}

      {analysis ? (
        <>
          <div className="mb-4 flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={showAiOnly}
                onChange={(e) => setShowAiOnly(e.target.checked)}
              />
              Show AI components only
            </label>
            <Button
              variant="secondary"
              onClick={() => navigate(`/projects/${projectId}/models`)}
            >
              Compare models
            </Button>
          </div>

          <Card className="h-[420px] p-0">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodeClick={(_evt, node) => {
                const c = components.find((x) => x.component_id === node.id);
                if (c) setSelected(c);
              }}
              fitView
            >
              <Background />
            </ReactFlow>
          </Card>

          {/* Accessible alternative: component list */}
          <Card className="mt-6">
            <h2 className="mb-3 text-sm font-semibold text-ink">
              Components (list)
            </h2>
            <ul className="space-y-2">
              {components.map((c) => (
                <li key={c.component_id}>
                  <button
                    onClick={() => setSelected(c)}
                    className="w-full rounded-md border border-border bg-surface p-3 text-left text-sm hover:bg-canvas"
                  >
                    <span className="font-medium text-ink">{c.name}</span>
                    {c.ai_required && (
                      <span className="ml-2">
                        <Badge tone="info">AI</Badge>
                      </span>
                    )}
                    <span className="ml-2 text-xs text-muted">
                      {c.recommended_approach}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>

          {selected && (
            <Card className="mt-6">
              <h2 className="mb-2 text-base font-semibold text-ink">
                {selected.name}
              </h2>
              <p className="text-sm text-muted">{selected.purpose}</p>
              <div className="mt-4 space-y-3 text-sm">
                <p>
                  <span className="font-medium">Approach:</span>{" "}
                  {selected.recommended_approach}
                </p>
                <p>
                  <span className="font-medium">Rationale:</span>{" "}
                  {selected.decision_rationale}
                </p>
                {selected.model_recommendations.length > 0 && (
                  <div>
                    <h3 className="mb-2 font-semibold">
                      Model recommendations
                    </h3>
                    <ol className="space-y-2">
                      {selected.model_recommendations.map((m) => (
                        <li
                          key={m.rank}
                          className="rounded-md border border-border p-3"
                        >
                          <div className="flex items-center gap-2">
                            <Badge tone="info">#{m.rank}</Badge>
                            <span className="font-medium">{m.model_name}</span>
                            {m.verified ? (
                              <Badge tone="success">verified</Badge>
                            ) : (
                              <Badge tone="warning">unverified</Badge>
                            )}
                          </div>
                          <p className="mt-1 text-muted">{m.rationale}</p>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            </Card>
          )}
        </>
      ) : (
        <EmptyAnalysis onRun={() => runAnalysis.mutate()} />
      )}
    </div>
  );
}

function EmptyAnalysis({ onRun }: { onRun: () => void }) {
  return (
    <Card>
      <p className="text-sm text-muted">
        No analysis yet. Run analysis to decompose the application into
        components and generate model recommendations.
      </p>
      <div className="mt-4">
        <Button onClick={onRun}>Run analysis</Button>
      </div>
    </Card>
  );
}
