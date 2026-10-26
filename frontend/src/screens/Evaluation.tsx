import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { Badge, Card, EmptyState, Loading } from "../components/ui";

const STATUS_TONE: Record<string, "neutral" | "success" | "warning" | "danger" | "info"> = {
  planned: "neutral",
  running: "info",
  completed: "success",
  failed: "danger",
  unavailable: "warning",
};

export default function Evaluation() {
  const { projectId = "" } = useParams();

  const { data: runs, isLoading } = useQuery({
    queryKey: ["evaluations", projectId],
    queryFn: () => api.listEvaluations(projectId),
    retry: false,
  });

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-ink">Evaluation plan & results</h1>
        <p className="mt-1 text-sm text-muted">
          Planned tests are shown separately from executed results. Metrics are
          shown only when data exists. Live evaluation requires explicit
          approval.
        </p>
      </header>

      {isLoading ? (
        <Loading label="Loading evaluations…" />
      ) : runs && runs.length > 0 ? (
        <div className="space-y-4">
          {runs.map((r) => (
            <Card key={r.id}>
              <div className="flex items-center gap-2">
                <Badge tone={STATUS_TONE[r.status] ?? "neutral"}>{r.status}</Badge>
                {r.approved && <Badge tone="info">approved</Badge>}
                {r.executed && <Badge tone="success">executed</Badge>}
              </div>
              {r.dataset_version && (
                <p className="mt-2 text-sm text-muted">
                  Dataset: {r.dataset_version}
                </p>
              )}
              {r.executed && Object.keys(r.metrics).length > 0 && (
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
                  {Object.entries(r.metrics).map(([k, v]) => (
                    <div key={k} className="rounded border border-border p-2">
                      <div className="text-muted">{k}</div>
                      <div className="font-medium text-ink">
                        {v === null ? "—" : String(v)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {!r.executed && (
                <p className="mt-2 text-sm text-muted">
                  Not executed. Results are not shown until the evaluation runs.
                </p>
              )}
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No evaluations planned"
          hint="Plan an evaluation to compare approved model endpoints using representative inputs."
        />
      )}
    </div>
  );
}
