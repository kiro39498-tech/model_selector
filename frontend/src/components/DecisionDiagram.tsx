import { clsx } from "clsx";
import type { OrchestratorDecision } from "../api";

// Animated decision diagram: shows how a task flows through the orchestrator
// (decision layer) and is routed to an SLM or an LLM, with the factors
// considered. Pure CSS/Tailwind animation — no external animation library.

function Node({
  label,
  sub,
  tone,
  active,
  className,
}: {
  label: string;
  sub?: string;
  tone: "input" | "decision" | "slm" | "llm";
  active?: boolean;
  className?: string;
}) {
  const tones: Record<string, string> = {
    input: "border-border bg-surface text-ink",
    decision: "border-accent/40 bg-accent-soft text-accent",
    slm: "border-green-300 bg-green-50 text-green-800",
    llm: "border-indigo-300 bg-indigo-50 text-indigo-800",
  };
  return (
    <div
      className={clsx(
        "flex min-w-[120px] flex-col items-center justify-center rounded-lg border px-4 py-3 text-center transition-all duration-500",
        tones[tone],
        active && "ring-2 ring-accent ring-offset-2 scale-105 shadow-md",
        className
      )}
    >
      <span className="text-sm font-semibold">{label}</span>
      {sub && <span className="mt-0.5 text-[11px] text-muted">{sub}</span>}
    </div>
  );
}

function Arrow({ active, label }: { active?: boolean; label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center px-1">
      <div
        className={clsx(
          "h-0.5 w-8 bg-accent transition-all duration-500",
          active ? "opacity-100 animate-pulse" : "opacity-30"
        )}
      />
      {label && (
        <span className="mt-1 text-[10px] text-muted">{label}</span>
      )}
    </div>
  );
}

export function DecisionDiagram({
  decision,
  prompt,
}: {
  decision: OrchestratorDecision | null;
  prompt: string;
}) {
  const rec = decision?.recommendation ?? "unknown";
  const slmActive = rec === "SLM";
  const llmActive = rec === "LLM";
  const decisionActive = decision !== null;

  return (
    <div className="rounded-lg border border-border bg-surface p-6">
      <h3 className="mb-1 text-sm font-semibold text-ink">
        How the orchestrator decides
      </h3>
      <p className="mb-6 text-xs text-muted">
        A task is evaluated against the factors below, then routed to the
        appropriate model class.
      </p>

      {/* Flow: Task -> Decision Layer -> SLM / LLM */}
      <div className="flex flex-wrap items-center justify-center gap-2">
        <Node
          tone="input"
          label="Task / Query"
          sub={prompt ? prompt.slice(0, 28) + (prompt.length > 28 ? "…" : "") : "your prompt"}
        />
        <Arrow active={decisionActive} label="evaluate" />
        <Node
          tone="decision"
          label="Decision Layer"
          sub="orchestrator"
          active={decisionActive}
        />
        <Arrow active={decisionActive} />
        <div className="flex flex-col gap-2">
          <Node tone="slm" label="SLM" sub="small model" active={slmActive} />
          <Node tone="llm" label="LLM" sub="large model" active={llmActive} />
        </div>
      </div>

      {/* Factors considered (the factors the AI actually weighed) */}
      <div className="mt-6">
        <h4 className="mb-2 text-xs font-semibold text-ink">
          Factors considered
        </h4>
        {decision && decision.factors.length > 0 ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {decision.factors.map((f, i) => (
              <div
                key={i}
                className="rounded-md border border-border bg-canvas px-3 py-2 text-xs text-muted"
              >
                {f.name}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted">
            The orchestrator weighed the task against its nature, complexity,
            and any constraints you provided.
          </p>
        )}
      </div>

      {/* Result */}
      {decision && (
        <div className="mt-6 rounded-md border border-accent/30 bg-accent-soft p-4">
          <p className="text-sm text-ink">
            <span className="font-semibold">
              {decision.recommendation === "unknown"
                ? "Uncertain"
                : `Recommend ${decision.recommendation}`}
            </span>{" "}
            · {Math.round(decision.confidence * 100)}% confidence ·{" "}
            {decision.use_case}
          </p>
          <p className="mt-1 text-xs text-muted">{decision.rationale}</p>
          {decision.factors.length > 0 && (
            <ul className="mt-3 space-y-1">
              {decision.factors.slice(0, 4).map((f, i) => (
                <li key={i} className="text-xs text-muted">
                  <span
                    className={clsx(
                      "mr-1 font-medium",
                      f.direction === "slm" && "text-green-700",
                      f.direction === "llm" && "text-indigo-700",
                      f.direction === "neutral" && "text-muted"
                    )}
                  >
                    {f.direction === "slm" ? "→ SLM" : f.direction === "llm" ? "→ LLM" : "•"}
                  </span>
                  {f.name}: {f.signal}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
