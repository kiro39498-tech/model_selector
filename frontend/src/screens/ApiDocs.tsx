import { Card } from "../components/ui";

// A human-readable API reference page (Swagger-style) for the orchestrator
// service. The interactive OpenAPI/Swagger UI is also available at /docs
// (FastAPI's auto-generated UI); this page gives a concise, copy-paste
// friendly overview for developers integrating the service.

interface Endpoint {
  method: string;
  path: string;
  summary: string;
  body?: string;
  response: string;
}

const ENDPOINTS: Endpoint[] = [
  {
    method: "POST",
    path: "/api/v1/orchestrator/decide",
    summary:
      "Start an AI decision (async). Returns 202 immediately with a run id; poll GET /api/v1/orchestrator/decide/{run_id} for the result. The result is either a decision or a clarification question.",
    body: `{ "prompt": "Classify this email as spam or not", "conversation": [], "constraints": ["low latency"] }`,
    response: '{ "id": "run-uuid", "status": "running", "correlation_id": "..." }',
  },
  {
    method: "GET",
    path: "/api/v1/orchestrator/decide/{run_id}",
    summary:
      "Poll a decision run for its result. The response is either a decision (SLM/LLM) or a clarification question.",
    response:
      '{ "run": { "status": "completed" }, "response": { "status": "decision", "decision": { "recommendation": "LLM", ... } } }',
  },
  {
    method: "GET",
    path: "/api/v1/orchestrator/decide",
    summary: "List recent decision runs (most recent first).",
    response: '[ { "id": "run-uuid", "status": "completed", ... } ]',
  },
];

const REQUEST_FIELDS = [
  { name: "prompt", type: "string", required: true, desc: "The task or query to classify." },
  { name: "conversation", type: "OrchestratorMessage[]", required: false, desc: "Prior turns (role + content). The client maintains the conversation and sends it back each turn." },
  { name: "constraints", type: "string[]", required: false, desc: "e.g. \"low latency\", \"high accuracy\", \"on-prem\"." },
];

const RESPONSE_FIELDS = [
  { name: "status", type: '"decision" | "clarify"', desc: "Whether the orchestrator decided or needs more detail." },
  { name: "decision", type: "OrchestratorDecision | null", desc: "Present when status is \"decision\"." },
  { name: "question", type: "ClarificationQuestion | null", desc: "Present when status is \"clarify\" (a follow-up question)." },
];

const FACTORS = [
  { name: "Task specificity", desc: "Specific, narrow, well-defined tasks favour an SLM." },
  { name: "Open-endedness", desc: "Open-ended or complex tasks favour an LLM." },
  { name: "Reasoning depth", desc: "Long, multi-clause prompts favour an LLM." },
  { name: "Domain", desc: "Knowledge-heavy domains (legal/medical/financial) favour an LLM." },
  { name: "Constraints", desc: "Latency/cost/on-prem favour an SLM; quality favours an LLM." },
  { name: "Ambiguity", desc: "If the task is unclear, the orchestrator asks a follow-up question instead of guessing." },
];

export default function ApiDocs() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-ink">Orchestrator API</h1>
        <p className="mt-2 text-muted">
          Decide whether a task should use a Small Language Model (SLM) or a
          Large Language Model (LLM). The interactive Swagger UI is available at{" "}
          <a href="/docs" className="text-accent hover:underline">
            /docs
          </a>
          .
        </p>
      </header>

      <Card className="mb-6">
        <h2 className="mb-3 text-sm font-semibold text-ink">Endpoints</h2>
        <div className="space-y-4">
          {ENDPOINTS.map((e) => (
            <div key={e.path} className="rounded-md border border-border p-4">
              <div className="flex items-center gap-2">
                <span className="rounded bg-accent-soft px-2 py-0.5 text-xs font-semibold text-accent">
                  {e.method}
                </span>
                <code className="text-sm text-ink">{e.path}</code>
              </div>
              <p className="mt-2 text-xs text-muted">{e.summary}</p>
              {e.body && (
                <pre className="mt-2 overflow-x-auto rounded bg-canvas p-2 text-xs">
                  {e.body}
                </pre>
              )}
              <pre className="mt-2 overflow-x-auto rounded bg-canvas p-2 text-xs">
                {e.response}
              </pre>
            </div>
          ))}
        </div>
      </Card>

      <Card className="mb-6">
        <h2 className="mb-3 text-sm font-semibold text-ink">Request fields</h2>
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="text-muted">
              <th className="py-1">Field</th>
              <th className="py-1">Type</th>
              <th className="py-1">Required</th>
              <th className="py-1">Description</th>
            </tr>
          </thead>
          <tbody>
            {REQUEST_FIELDS.map((f) => (
              <tr key={f.name} className="border-t border-border">
                <td className="py-1 font-mono text-ink">{f.name}</td>
                <td className="py-1 font-mono text-muted">{f.type}</td>
                <td className="py-1">{f.required ? "yes" : "no"}</td>
                <td className="py-1 text-muted">{f.desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-semibold text-ink">
          Factors the orchestrator weighs
        </h2>
        <ul className="space-y-2">
          {FACTORS.map((f) => (
            <li key={f.name} className="text-xs text-muted">
              <span className="font-medium text-ink">{f.name}</span> — {f.desc}
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-muted">
          Classification convention: a model with fewer than 150B parameters is
          an SLM; 150B or more is an LLM.
        </p>
      </Card>
    </div>
  );
}
