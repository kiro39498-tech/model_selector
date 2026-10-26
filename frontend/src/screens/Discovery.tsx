import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
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

export default function Discovery() {
  const { projectId = "" } = useParams();
  const navigate = useNavigate();
  const [message, setMessage] = useState("");
  const [questions, setQuestions] = useState<string[]>([]);
  const [ambiguities, setAmbiguities] = useState<string[]>([]);

  const { data: requirements } = useQuery({
    queryKey: ["requirements", projectId],
    queryFn: () => api.listRequirements(projectId),
    retry: false,
  });

  const { data: completeness } = useQuery({
    queryKey: ["completeness", projectId],
    queryFn: () => api.completeness(projectId),
    retry: false,
  });

  const discovery = useMutation({
    mutationFn: () => api.discovery(projectId, message.trim()),
    onSuccess: (res) => {
      setQuestions(res.questions);
      setAmbiguities(res.ambiguities);
      setMessage("");
    },
  });

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-ink">Requirements discovery</h1>
        <p className="mt-1 text-sm text-muted">
          Tell us about your application. We will ask only the questions that
          matter and extract requirements as we go.
        </p>
      </header>

      <div className="grid gap-6 md:grid-cols-3">
        <div className="md:col-span-2">
          <Card>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
              placeholder="Describe a feature, a user journey, a data source, or a constraint…"
            />
            <div className="mt-3 flex items-center gap-3">
              <Button
                onClick={() => discovery.mutate()}
                disabled={!message.trim() || discovery.isPending}
              >
                {discovery.isPending ? "Thinking…" : "Send"}
              </Button>
              {discovery.isError && (
                <ErrorState message={(discovery.error as Error).message} />
              )}
            </div>

            {questions.length > 0 && (
              <div className="mt-5">
                <h3 className="mb-2 text-sm font-semibold text-ink">
                  Follow-up questions
                </h3>
                <ul className="space-y-1 text-sm text-ink">
                  {questions.map((q, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-accent">•</span>
                      {q}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {ambiguities.length > 0 && (
              <div className="mt-4">
                <h3 className="mb-2 text-sm font-semibold text-ink">
                  Ambiguities detected
                </h3>
                <ul className="space-y-1 text-sm text-amber-700">
                  {ambiguities.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">
              Discovery progress
            </h3>
            {completeness ? (
              <ul className="space-y-2 text-sm">
                {CATEGORIES.map((cat) => (
                  <li key={cat} className="flex items-center justify-between">
                    <span className="capitalize text-ink">{cat}</span>
                    <Badge tone={completeness.by_category[cat] >= 0.5 ? "success" : "neutral"}>
                      {Math.round((completeness.by_category[cat] ?? 0) * 100)}%
                    </Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <Loading label="Assessing…" />
            )}
            {completeness && (
              <div className="mt-4">
                <Button
                  variant="secondary"
                  onClick={() => navigate(`/projects/${projectId}/requirements`)}
                >
                  Review requirements
                </Button>
              </div>
            )}
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">
              Requirements captured
            </h3>
            {requirements && requirements.length > 0 ? (
              <ul className="space-y-2 text-sm">
                {requirements.map((r: Requirement) => (
                  <li key={r.id} className="border-b border-border pb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-ink">{r.code}</span>
                      <Badge tone={r.source === "user" ? "info" : "warning"}>
                        {r.source}
                      </Badge>
                    </div>
                    <p className="mt-1 text-muted">{r.description}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">No requirements captured yet.</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
