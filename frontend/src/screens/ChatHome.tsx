import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  api,
  type ClarificationQuestion,
  type OrchestratorDecision,
  type OrchestratorMessage,
  type OrchestratorResult,
} from "../api";
import { Button, Card, ErrorState, Loading } from "../components/ui";
import { DecisionDiagram } from "../components/DecisionDiagram";

// A Gemini/ChatGPT-style home page: the user types a task/query and the
// orchestrator (AI-driven) decides whether it should use an SLM or an LLM.
// If the task is ambiguous, the orchestrator asks a follow-up question before
// deciding. The client maintains the conversation and sends it back each turn.

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  decision?: OrchestratorDecision;
  question?: ClarificationQuestion;
}

export default function ChatHome() {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversation, setConversation] = useState<OrchestratorMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState("");

  // Keep a ref of the conversation so the async send() reads the latest value
  // (avoiding a stale closure across the async AI call + polling).
  const conversationRef = useRef<OrchestratorMessage[]>([]);
  useEffect(() => {
    conversationRef.current = conversation;
  }, [conversation]);

  const canSubmit = prompt.trim().length > 0 && !isThinking;

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || isThinking) return;
    const priorConversation = conversationRef.current;
    setMessages((m) => [...m, { role: "user", text: trimmed }]);
    setPrompt("");
    setIsThinking(true);
    setError("");
    try {
      const run = await api.decide({ prompt: trimmed, conversation: priorConversation });
      const result = await pollDecision(run.id);
      if (result.run.status === "failed") {
        throw new Error(result.run.error || "The orchestrator failed to respond.");
      }
      const response = result.response;
      if (!response) throw new Error("No response from the orchestrator.");
      if (response.status === "clarify" && response.question) {
        const q = response.question;
        setMessages((m) => [
          ...m,
          { role: "assistant", text: q.question, question: q },
        ]);
        setConversation((c) => [
          ...c,
          { role: "user", content: trimmed },
          { role: "assistant", content: q.question },
        ]);
      } else if (response.status === "decision" && response.decision) {
        const d = response.decision;
        setMessages((m) => [
          ...m,
          { role: "assistant", text: summarize(d), decision: d },
        ]);
        setConversation((c) => [...c, { role: "user", content: trimmed }]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setIsThinking(false);
    }
  }

  function reset() {
    setMessages([]);
    setConversation([]);
    setPrompt("");
    setError("");
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <header className="mb-8 text-center">
        <h1 className="text-2xl font-semibold text-ink">AI Application Architect</h1>
        <p className="mt-2 text-muted">
          Ask what a task needs — an SLM or an LLM. The orchestrator reasons
          about your query and tells you which model class fits, and why. If
          it needs more detail, it will ask.
        </p>
      </header>

      {/* Chat transcript */}
      {messages.length > 0 && (
        <div className="mb-6 space-y-4">
          {messages.map((m, i) => (
            <div
              key={i}
              className={
                m.role === "user"
                  ? "ml-auto max-w-[85%] rounded-lg bg-accent px-4 py-2 text-sm text-white"
                  : "mr-auto max-w-[95%]"
              }
            >
              {m.role === "user" ? (
                <p>{m.text}</p>
              ) : (
                <Card className="p-4">
                  <p className="text-sm text-ink">{m.text}</p>
                  {m.question && (
                    <div className="mt-3">
                      {m.question.why && (
                        <p className="mb-2 text-xs text-muted">{m.question.why}</p>
                      )}
                      {m.question.options.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {m.question.options.map((opt) => (
                            <button
                              key={opt}
                              onClick={() => setPrompt(opt)}
                              className="rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted hover:bg-canvas"
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {m.decision && (
                    <div className="mt-3">
                      <DecisionDiagram decision={m.decision} prompt={m.text} />
                    </div>
                  )}
                </Card>
              )}
            </div>
          ))}
          {isThinking && (
            <div className="mr-auto max-w-[95%]">
              <Card className="p-4">
                <Loading label="The orchestrator is thinking…" />
              </Card>
            </div>
          )}
        </div>
      )}

      {/* Prompt input */}
      <Card>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          className="w-full resize-none rounded-md border border-border bg-surface px-3 py-2 text-sm"
          placeholder="e.g. Classify support tickets by intent, or: Write a detailed strategy for market entry…"
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && canSubmit) {
              send(prompt);
            }
          }}
        />
        {error && (
          <div className="mt-3">
            <ErrorState message={error} />
          </div>
        )}
        <div className="mt-4 flex items-center gap-3">
          <Button
            type="button"
            onClick={() => send(prompt)}
            disabled={!canSubmit}
          >
            {isThinking ? "Thinking…" : "Send"}
          </Button>
          {messages.length > 0 && (
            <Button
              type="button"
              variant="ghost"
              onClick={reset}
              disabled={isThinking}
            >
              New conversation
            </Button>
          )}
          <span className="text-xs text-muted">
            Press Ctrl/Cmd + Enter to send.
          </span>
        </div>
      </Card>

      {/* Quick examples */}
      {messages.length === 0 && (
        <div className="mt-6 flex flex-wrap gap-2">
          {[
            "Classify this email as spam or not",
            "Summarize this support ticket into 3 bullets",
            "Write a detailed essay on the causes of World War II",
            "Analyze the legal implications of this contract",
          ].map((ex) => (
            <button
              key={ex}
              onClick={() => setPrompt(ex)}
              className="rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted hover:bg-canvas"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      {/* Secondary actions */}
      <div className="mt-10 flex items-center justify-center gap-4 text-sm">
        <button
          onClick={() => navigate("/new-project")}
          className="text-accent hover:underline"
        >
          Design a full application →
        </button>
        <span className="text-muted">·</span>
        <a href="/docs" className="text-accent hover:underline">
          API reference
        </a>
      </div>
    </div>
  );
}

// Poll a decision run until it completes or fails.
async function pollDecision(runId: string): Promise<OrchestratorResult> {
  for (let i = 0; i < 60; i++) {
    const result = await api.getDecisionRun(runId);
    if (result.run.status === "completed" || result.run.status === "failed") {
      return result;
    }
    await new Promise((r) => setTimeout(r, 5000));
  }
  throw new Error("Timed out waiting for the orchestrator.");
}

function summarize(d: OrchestratorDecision): string {
  if (d.recommendation === "unknown") {
    return "I'm not certain which model class fits — the task is ambiguous. Here's what I weighed:";
  }
  return `I'd use a ${d.recommendation} for this (${Math.round(
    d.confidence * 100
  )}% confidence). ${d.rationale}`;
}
