import { useNavigate } from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api, type Requirement } from "../api";
import { Badge, Button, Card, ErrorState, Loading } from "../components/ui";

const CATEGORIES = [
  "business",
  "functional",
  "data",
  "non_functional",
  "ai",
  "operational",
];

export default function RequirementsReview() {
  const { projectId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: requirements, isLoading } = useQuery({
    queryKey: ["requirements", projectId],
    queryFn: () => api.listRequirements(projectId),
    retry: false,
  });

  const { data: completeness } = useQuery({
    queryKey: ["completeness", projectId],
    queryFn: () => api.completeness(projectId),
    retry: false,
  });

  // Confirm/reject a single requirement. This is what lets a user resolve a
  // high-criticality requirement so the approval gate can open.
  const updateStatus = useMutation({
    mutationFn: (args: { code: string; status: string }) =>
      api.updateRequirement(projectId, args.code, args.status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["requirements", projectId] });
      queryClient.invalidateQueries({ queryKey: ["completeness", projectId] });
    },
  });

  const approve = useMutation({
    mutationFn: () => api.approve(projectId),
    onSuccess: () => navigate(`/projects/${projectId}/architecture`),
  });

  if (isLoading) return <Loading label="Loading requirements…" />;

  const grouped = CATEGORIES.map((cat) => ({
    cat,
    items: (requirements ?? []).filter((r) => r.category === cat),
  }));

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-ink">Review requirements</h1>
        <p className="mt-1 text-sm text-muted">
          Review, edit, and approve requirements before final analysis. Final
          analysis is blocked until critical requirements are resolved.
        </p>
      </header>

      {completeness && completeness.critical_unresolved.length > 0 && (
        <div className="mb-6">
          <ErrorState
            message={`Cannot approve: critical requirements unresolved — ${completeness.critical_unresolved.join(", ")}. Confirm each one below (or reject it) to clear the gate.`}
          />
        </div>
      )}

      <div className="space-y-6">
        {grouped.map(
          ({ cat, items }) =>
            items.length > 0 && (
              <Card key={cat}>
                <h2 className="mb-3 text-sm font-semibold capitalize text-ink">
                  {cat}
                </h2>
                <ul className="space-y-3">
                  {items.map((r: Requirement) => (
                    <li key={r.id} className="border-b border-border pb-3">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-ink">{r.code}</span>
                        <Badge tone={r.source === "user" ? "info" : "warning"}>
                          {r.source}
                        </Badge>
                        {r.criticality === "high" && (
                          <Badge tone="danger">critical</Badge>
                        )}
                        <Badge
                          tone={
                            r.status === "confirmed" ? "success" : "neutral"
                          }
                        >
                          {r.status}
                        </Badge>
                      </div>
                      <p className="mt-1 text-sm text-ink">{r.description}</p>
                      {r.status !== "confirmed" && (
                        <div className="mt-2 flex items-center gap-2">
                          <Button
                            variant="secondary"
                            onClick={() =>
                              updateStatus.mutate({
                                code: r.code,
                                status: "confirmed",
                              })
                            }
                            disabled={updateStatus.isPending}
                          >
                            Confirm
                          </Button>
                          <Button
                            variant="secondary"
                            onClick={() =>
                              updateStatus.mutate({
                                code: r.code,
                                status: "rejected",
                              })
                            }
                            disabled={updateStatus.isPending}
                          >
                            Reject
                          </Button>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </Card>
            )
        )}
      </div>

      <div className="mt-8 flex items-center gap-3">
        <Button
          onClick={() => approve.mutate()}
          disabled={!completeness?.ready_for_approval || approve.isPending}
        >
          {approve.isPending ? "Approving…" : "Approve & analyze"}
        </Button>
        {approve.isError && (
          <ErrorState message={(approve.error as Error).message} />
        )}
        <Button variant="secondary" onClick={() => navigate(`/projects/${projectId}/discovery`)}>
          Back to discovery
        </Button>
      </div>
    </div>
  );
}
