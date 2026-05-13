import type { ToolTrace } from "../api";

type Props = { trace: ToolTrace[] };

export function AgentTrace({ trace }: Props) {
  if (!trace.length) return null;

  return (
    <details className="mt-10 border-t border-line pt-6 anim-fade-in">
      <summary className="font-mono text-[10px] tracking-[0.3em] text-faint uppercase cursor-pointer hover:text-muted transition-colors list-none flex items-center gap-2">
        <span className="inline-block w-2 h-px bg-faint" />
        Agent trace — {trace.length} steps
      </summary>

      <div className="mt-5 space-y-2">
        {trace.map((t, i) => (
          <div
            key={i}
            className={`bg-card px-4 py-3 font-mono text-[12px] leading-relaxed ${
              t.error
                ? "[border-left:2px_solid_#c96060]"
                : t.used_fallback
                ? "[border-left:2px_solid_#d4914e]"
                : ""
            }`}
          >
            <div className="flex items-baseline justify-between mb-1.5">
              <span className="text-accent-bright">
                <span className="text-faint mr-1">{String(i + 1).padStart(2, "0")}.</span>
                {t.tool_name}
              </span>
              <span className="text-faint text-[11px]">{t.duration_ms}ms</span>
            </div>

            {t.output_summary && (
              <div className="text-[11px] text-muted">
                <span className="text-faint mr-1">out</span>
                {t.output_summary}
              </div>
            )}

            {t.used_fallback && (
              <div className="text-warn text-[11px] mt-1">fallback used</div>
            )}
            {t.error && (
              <div className="text-bad text-[11px] mt-1">error: {t.error}</div>
            )}
          </div>
        ))}
      </div>
    </details>
  );
}
