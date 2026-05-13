import type { ToolTrace } from "../api";

type Props = { trace: ToolTrace[] };

export function AgentTrace({ trace }: Props) {
  if (!trace.length) return null;

  return (
    <details className="trace" open>
      <summary>Agent trace ({trace.length} steps)</summary>
      {trace.map((t, i) => {
        const cls = t.error ? "error" : t.used_fallback ? "fallback" : "";
        return (
          <div key={i} className={`trace-item ${cls}`}>
            <div>
              <span className="tool">{i + 1}. {t.tool_name}</span>
              <span style={{ float: "right", color: "var(--text-dim)" }}>{t.duration_ms} ms</span>
            </div>
            <div>
              <span className="label">in:</span> {t.input_summary}
            </div>
            <div>
              <span className="label">out:</span> {t.output_summary}
            </div>
            {t.used_fallback && (
              <div style={{ color: "var(--warn)" }}>fallback used</div>
            )}
            {t.error && <div style={{ color: "var(--bad)" }}>error: {t.error}</div>}
          </div>
        );
      })}
    </details>
  );
}
