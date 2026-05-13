import type { PlanResponse } from "../api";

type Props = { plan: PlanResponse | null; error: string | null };

export function PlanDisplay({ plan, error }: Props) {
  if (error) {
    return <div className="banner error">{error}</div>;
  }

  if (!plan) {
    return (
      <div className="empty">
        Fill in your preferences on the left and hit <strong>Plan my Saturday</strong>.
      </div>
    );
  }

  if (plan.status === "needs_clarification") {
    return (
      <>
        <div className="banner">
          Need a couple more details before I can plan your day:
        </div>
        <div className="questions">
          {plan.clarification_questions.map((q, i) => (
            <div key={i} className="q">
              {q}
            </div>
          ))}
        </div>
      </>
    );
  }

  return (
    <>
      {plan.fallback_used && (
        <div className="banner">
          Heads up: I used a fallback for part of this plan — see the trace below for what happened.
        </div>
      )}

      {plan.summary && <div className="summary-card">{plan.summary}</div>}

      <div className="timeline">
        {plan.itinerary.map((stop, i) => (
          <div key={i} className="stop">
            <div className="time">{stop.time_slot}</div>
            <div className="name">{stop.place_name}</div>
            <p className="activity">{stop.activity}</p>
            {stop.reasoning && <div className="reasoning">{stop.reasoning}</div>}
            <div className="meta">
              <span>~{stop.duration_minutes} min</span>
              <span>~₹{Math.round(stop.estimated_cost)}</span>
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 14, color: "var(--text-dim)", fontSize: 13 }}>
        Estimated total: <strong style={{ color: "var(--text)" }}>₹{Math.round(plan.total_cost)}</strong>
      </div>

      {plan.trade_offs.length > 0 && (
        <div className="trade-offs">
          <h4>Trade-offs</h4>
          <ul>
            {plan.trade_offs.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
