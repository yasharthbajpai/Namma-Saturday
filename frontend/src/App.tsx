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
    <div className="max-w-[1080px] mx-auto px-6 min-[900px]:px-10 pt-12 pb-28">

      {/* ── Masthead ── */}
      <header className="mb-10">
        <p className="font-mono text-[10px] tracking-[0.35em] text-muted uppercase mb-4">
          Bangalore · AI day planner
        </p>
        <h1 className="font-display text-[54px] min-[900px]:text-[68px] leading-[1] font-semibold tracking-[-1.5px] text-cream mb-6">
          Namma<br />Saturday
        </h1>
        <div className="h-px bg-line-2" />
        <p className="text-muted text-sm mt-3">
          Tell me your vibe. I'll plan the rest.
        </p>
      </header>

      {/* ── Two-column layout ── */}
      <div className="grid grid-cols-1 gap-10 min-[900px]:grid-cols-[360px_1fr]">

        <InputForm loading={loading} onSubmit={handleSubmit} />

        <div className="min-w-0">

          {/* Live thinking trace */}
          {loading && liveSteps.length > 0 && (
            <div className="anim-fade-in mb-8">
              <p className="font-mono text-[10px] tracking-[0.3em] text-muted uppercase mb-4">
                Building your day
              </p>
              <div className="space-y-0">
                {liveSteps.map((s) => (
                  <div
                    key={s.step}
                    className="flex items-start gap-3 py-2.5 border-b border-line last:border-b-0"
                  >
                    {s.kind === "thinking" ? (
                      <>
                        <span
                          className="mt-[3px] w-1.5 h-1.5 rounded-full bg-accent shrink-0"
                          style={{ animation: "flicker 1.2s ease-in-out infinite" }}
                        />
                        <span className="text-[13px] text-muted">{s.message}</span>
                      </>
                    ) : (
                      <>
                        <span className="mt-[3px] w-1.5 h-1.5 rounded-full bg-good shrink-0" />
                        <span className="text-[13px] text-cream">{s.tool_name}</span>
                        <span className="text-[13px] text-muted ml-1 truncate">{s.output}</span>
                        <span className="ml-auto font-mono text-[11px] text-faint shrink-0">{s.duration_ms}ms</span>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Final plan */}
          {!loading && <PlanDisplay plan={plan} error={error} />}

          {/* Agent trace */}
          {!loading && trace.length > 0 && <AgentTrace trace={trace} />}
        </div>

      </div>
    </div>
  );
}
