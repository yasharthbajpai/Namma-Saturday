import { useState } from "react";
import { InputForm } from "./components/InputForm";
import { PlanDisplay } from "./components/PlanDisplay";
import { AgentTrace } from "./components/AgentTrace";
import {
  planSaturdayStream,
  type PlanResponse,
  type ToolTrace,
  type UserInput,
  type StreamEvent,
} from "./api";

type LiveStep =
  | { kind: "thinking"; step: number; message: string }
  | { kind: "done"; step: number; tool_name: string; output: string; duration_ms: number; used_fallback: boolean };

export default function App() {
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveSteps, setLiveSteps] = useState<LiveStep[]>([]);
  const [trace, setTrace] = useState<ToolTrace[]>([]);

  const handleSubmit = async (input: UserInput) => {
    setLoading(true);
    setError(null);
    setPlan(null);
    setLiveSteps([]);
    setTrace([]);

    try {
      await planSaturdayStream(input, (event: StreamEvent) => {
        if (event.type === "thinking") {
          setLiveSteps((prev) => [
            ...prev.filter((s) => s.step !== event.step),
            { kind: "thinking", step: event.step, message: event.message },
          ]);
        } else if (event.type === "trace") {
          setLiveSteps((prev) =>
            prev.map((s) =>
              s.step === event.step
                ? { kind: "done", step: event.step, tool_name: event.tool_name, output: event.output, duration_ms: event.duration_ms, used_fallback: event.used_fallback }
                : s
            )
          );
          setTrace((prev) => [
            ...prev,
            {
              tool_name: event.tool_name,
              input_summary: "",
              output_summary: event.output,
              duration_ms: event.duration_ms,
              used_fallback: event.used_fallback,
              error: event.error,
            },
          ]);
        } else if (event.type === "result") {
          setPlan(event.plan);
        } else if (event.type === "error") {
          setError(event.message);
        }
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="header">
        <h1>Perfect Saturday Planner</h1>
        <p>Tell me your vibe and I'll build you a Saturday plan.</p>
      </header>

      <div className="grid">
        <InputForm loading={loading} onSubmit={handleSubmit} />
        <div>
          {/* Live trace while loading */}
          {loading && liveSteps.length > 0 && (
            <div className="panel" style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, color: "var(--text-dim)", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                Agent is thinking
              </div>
              {liveSteps.map((s) => (
                <div key={s.step} className="live-step">
                  {s.kind === "thinking" ? (
                    <>
                      <span className="spinner" />
                      <span>{s.message}</span>
                    </>
                  ) : (
                    <>
                      <span className="step-done">✓</span>
                      <span style={{ color: "var(--text)" }}>{s.tool_name}</span>
                      <span style={{ color: "var(--text-dim)", marginLeft: 8 }}>{s.output}</span>
                      <span className="step-ms">{s.duration_ms}ms</span>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Final plan */}
          {!loading && (
            <div className="panel">
              <PlanDisplay plan={plan} error={error} />
            </div>
          )}

          {/* Full trace (collapsed, shown after plan loads) */}
          {!loading && trace.length > 0 && <AgentTrace trace={trace} />}
        </div>
      </div>
    </div>
  );
}
