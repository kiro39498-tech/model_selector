import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api, type AnalysisResponse, type ModelRecommendation } from "../api";
import { Badge, Card, Loading } from "../components/ui";

export default function ModelComparison() {
  const { projectId = "" } = useParams();

  const { data: latestRun } = useQuery({
    queryKey: ["analysis-runs", projectId],
    queryFn: () => api.listAnalysisRuns(projectId),
    retry: false,
  });

  const { data: result } = useQuery({
    queryKey: ["analysis-run", projectId, latestRun?.[0]?.id],
    queryFn: () => api.getAnalysisRun(projectId, latestRun![0].id),
    enabled: !!latestRun && latestRun.length > 0,
    retry: false,
  });

  const analysis: AnalysisResponse | null = result?.result ?? null;

  // Collect AI components that have recommendations.
  const aiComponents = (analysis?.components ?? []).filter(
    (c) => c.ai_required && c.model_recommendations.length > 0
  );

  if (!analysis) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-10">
        <h1 className="mb-4 text-xl font-semibold text-ink">Model comparison</h1>
        <Loading label="Loading analysis…" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-ink">Model comparison</h1>
        <p className="mt-1 text-sm text-muted">
          Ranked candidates per task. Cost is shown separately and is not the
          ranking criterion.
        </p>
      </header>

      <div className="space-y-8">
        {aiComponents.map((c) => (
          <Card key={c.component_id}>
            <h2 className="mb-1 text-base font-semibold text-ink">{c.name}</h2>
            <p className="mb-4 text-sm text-muted">{c.purpose}</p>
            <div className="grid gap-4 md:grid-cols-3">
              {c.model_recommendations.map((m) => (
                <CandidateCard key={m.rank} rec={m} />
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function CandidateCard({ rec }: { rec: ModelRecommendation }) {
  return (
    <div className="rounded-md border border-border p-4">
      <div className="mb-2 flex items-center gap-2">
        <Badge tone="info">#{rec.rank}</Badge>
        <span className="font-medium text-ink">{rec.model_name}</span>
        {rec.verified ? (
          <Badge tone="success">verified</Badge>
        ) : (
          <Badge tone="warning">unverified</Badge>
        )}
      </div>
      <dl className="space-y-1 text-sm">
        <div>
          <dt className="text-muted">Provider</dt>
          <dd className="text-ink">{rec.provider}</dd>
        </div>
        {rec.classification && (
          <div>
            <dt className="text-muted">Classification</dt>
            <dd className="text-ink">{rec.classification}</dd>
          </div>
        )}
        <div>
          <dt className="text-muted">Why</dt>
          <dd className="text-ink">{rec.rationale}</dd>
        </div>
        {rec.cost && (
          <div>
            <dt className="text-muted">Cost (reported separately)</dt>
            <dd className="text-ink">
              {JSON.stringify(rec.cost)}
            </dd>
          </div>
        )}
        {rec.unverified.length > 0 && (
          <div>
            <dt className="text-muted">Unverified</dt>
            <dd className="text-amber-700">{rec.unverified.join(", ")}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}
