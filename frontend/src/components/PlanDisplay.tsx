import type { PlanResponse } from "../api";

type Props = { plan: PlanResponse | null; error: string | null };

export function PlanDisplay({ plan, error }: Props) {
  if (error) {
    return (
      <div className="border-l-2 border-bad pl-4 py-1 anim-fade-in">
        <p className="font-mono text-[10px] tracking-[0.2em] text-bad uppercase mb-1">Error</p>
        <p className="text-[14px] text-muted">{error}</p>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="py-16 text-center">
        <p className="font-display text-[15px] italic text-faint leading-relaxed">
          Fill in your preferences<br />and hit <span className="text-muted not-italic font-mono text-[12px] tracking-widest uppercase">Plan my Saturday</span>
        </p>
      </div>
    );
  }

  if (plan.status === "needs_clarification") {
    return (
      <div className="anim-fade-in">
        <div className="border-l-2 border-accent pl-4 py-1 mb-6">
          <p className="font-mono text-[10px] tracking-[0.2em] text-accent uppercase mb-1">
            Need more details
          </p>
          <p className="text-[14px] text-muted">
            Before I can plan your day, help me with a couple of things:
          </p>
        </div>
        <div className="space-y-3">
          {plan.clarification_questions.map((q, i) => (
            <div key={i} className="flex gap-3">
              <span className="font-mono text-[11px] text-faint mt-[3px] shrink-0">{String(i + 1).padStart(2, "0")}</span>
              <p className="text-[14px] text-cream leading-relaxed">{q}</p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="anim-fade-in">

      {plan.fallback_used && (
        <div className="border-l-2 border-warn pl-4 py-1 mb-8">
          <p className="font-mono text-[10px] tracking-[0.2em] text-warn uppercase mb-1">Heads up</p>
          <p className="text-[13px] text-muted">
            Used a fallback for part of this plan — see the trace below.
          </p>
        </div>
      )}

      {plan.summary && (
        <p className="font-display text-[17px] italic leading-[1.65] text-muted mb-8 border-b border-line pb-8">
          {plan.summary}
        </p>
      )}

      {/* Timeline */}
      <div>
        {plan.itinerary.map((stop, i) => (
          <div
            key={i}
            className="anim-fade-up border-b border-line py-6 last:border-b-0"
            style={{ animationDelay: `${i * 80}ms` }}
          >
            <div className="flex items-baseline gap-3 mb-2">
              <span className="font-mono text-[11px] tracking-[0.15em] text-accent uppercase shrink-0">
                {stop.time_slot}
              </span>
              <div className="flex-1 h-px bg-line" />
            </div>

            <h3 className="font-display text-[24px] leading-tight font-semibold text-cream mb-1">
              {stop.place_name}
            </h3>

            <p className="text-[14px] text-muted leading-relaxed mb-2">
              {stop.activity}
            </p>

            {stop.reasoning && (
              <p className="font-display text-[13px] italic text-faint mb-3">
                "{stop.reasoning}"
              </p>
            )}

            <div className="flex items-center gap-4 font-mono text-[11px] text-faint">
              <span>{stop.duration_minutes} min</span>
              <span>·</span>
              <span>₹{Math.round(stop.estimated_cost)}</span>
              {stop.maps_url && (
                <>
                  <span>·</span>
                  <a
                    href={stop.maps_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent hover:underline"
                  >
                    Open in Maps ↗
                  </a>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Total cost */}
      <div
        className="anim-fade-up flex items-baseline justify-between pt-6 border-t border-line-2 mt-2"
        style={{ animationDelay: `${plan.itinerary.length * 80}ms` }}
      >
        <span className="font-mono text-[10px] tracking-[0.25em] text-faint uppercase">
          Estimated total
        </span>
        <span className="font-display text-[22px] text-cream">
          ₹{Math.round(plan.total_cost)}
        </span>
      </div>

      {/* Trade-offs */}
      {plan.trade_offs.length > 0 && (
        <div
          className="anim-fade-up mt-8"
          style={{ animationDelay: `${(plan.itinerary.length + 1) * 80}ms` }}
        >
          <p className="font-mono text-[10px] tracking-[0.25em] text-faint uppercase mb-4">
            Trade-offs
          </p>
          <ul className="space-y-2">
            {plan.trade_offs.map((t, i) => (
              <li key={i} className="flex gap-3 text-[13px] text-muted leading-relaxed">
                <span className="text-faint font-mono shrink-0 mt-[2px]">–</span>
                {t}
              </li>
            ))}
          </ul>
        </div>
      )}

    </div>
  );
}
