import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { Badge, Card, Loading } from "../components/ui";

export default function Settings() {
  const { data: health, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    retry: false,
  });

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-ink">Project settings</h1>
        <p className="mt-1 text-sm text-muted">
          Configuration status. Credentials are never displayed.
        </p>
      </header>

      {isLoading ? (
        <Loading label="Checking configuration…" />
      ) : health ? (
        <Card>
          <ul className="space-y-3 text-sm">
            <li className="flex items-center justify-between">
              <span className="text-ink">AI endpoint</span>
              <Badge tone={health.ai_configured ? "success" : "danger"}>
                {health.ai_configured ? "configured" : "not configured"}
              </Badge>
            </li>
            <li className="flex items-center justify-between">
              <span className="text-ink">Database</span>
              <Badge tone={health.db_configured ? "success" : "danger"}>
                {health.db_configured ? "configured" : "not configured"}
              </Badge>
            </li>
            <li className="flex items-center justify-between">
              <span className="text-ink">Classification threshold</span>
              <span className="text-ink">
                {health.classification_threshold_billions}B
              </span>
            </li>
          </ul>
          <p className="mt-4 text-xs text-muted">
            Secrets are stored in a local .env file and are never exposed in the
            UI, logs, or API responses.
          </p>
        </Card>
      ) : (
        <Card>
          <p className="text-sm text-muted">Unable to load configuration.</p>
        </Card>
      )}
    </div>
  );
}
