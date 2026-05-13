import { useState } from "react";
import { InputForm } from "./components/InputForm";
import { PlanDisplay } from "./components/PlanDisplay";
import { AgentTrace } from "./components/AgentTrace";
import { planSaturday, type PlanResponse, type UserInput } from "./api";

export default function App() {
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (input: UserInput) => {
    setLoading(true);
    setError(null);
    setPlan(null);
    try {
      const result = await planSaturday(input);
      setPlan(result);
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
          <div className="panel">
            <PlanDisplay plan={plan} error={error} />
          </div>
          {plan && <AgentTrace trace={plan.trace} />}
        </div>
      </div>
    </div>
  );
}
