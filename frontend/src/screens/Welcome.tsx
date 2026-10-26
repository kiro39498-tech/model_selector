import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type Project } from "../api";
import { Button, Card, ErrorState } from "../components/ui";

export default function Welcome() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: api.listProjects,
    retry: false,
  });

  const create = useMutation({
    mutationFn: () => api.createProject(name.trim(), description.trim()),
    onSuccess: (project: Project) => {
      navigate(`/projects/${project.id}/discovery`);
    },
    onError: (err: Error) => setError(err.message),
  });

  const canSubmit = name.trim().length > 0 && description.trim().length > 0;

  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <header className="mb-10">
        <h1 className="text-2xl font-semibold text-ink">AI Application Architect</h1>
        <p className="mt-2 text-muted">
          Describe the application you want to build. We will guide you through
          requirements discovery, decompose it into components, and recommend the
          best AI model for each task — with evidence, not guesses.
        </p>
      </header>

      <Card>
        <label className="block text-sm font-medium text-ink" htmlFor="name">
          Project name
        </label>
        <input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
          placeholder="e.g. Customer support assistant"
        />

        <label className="mt-4 block text-sm font-medium text-ink" htmlFor="desc">
          Describe your application
        </label>
        <textarea
          id="desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={6}
          className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
          placeholder="A vague description is fine. We will ask follow-up questions to understand it end to end."
        />

        {error && (
          <div className="mt-4">
            <ErrorState message={error} />
          </div>
        )}

        <div className="mt-6 flex items-center gap-3">
          <Button
            type="button"
            onClick={() => create.mutate()}
            disabled={!canSubmit || create.isPending}
          >
            {create.isPending ? "Creating…" : "Start discovery"}
          </Button>
          <span className="text-xs text-muted">
            Requirements must be approved before final analysis.
          </span>
        </div>
      </Card>

      {projects && projects.length > 0 && (
        <section className="mt-10">
          <h2 className="mb-3 text-sm font-semibold text-ink">Existing projects</h2>
          <ul className="space-y-2">
            {projects.map((p) => (
              <li key={p.id}>
                <button
                  onClick={() => navigate(`/projects/${p.id}/discovery`)}
                  className="w-full rounded-md border border-border bg-surface p-3 text-left text-sm hover:bg-canvas"
                >
                  <span className="font-medium text-ink">{p.name}</span>
                  <span className="ml-2 text-xs text-muted">{p.status}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
