export type UserInput = {
  city: string;
  budget: number;
  available_time: string;
  mood: string;
  interests: string[];
  constraints: string[];
};

export type ItineraryItem = {
  time_slot: string;
  place_name: string;
  activity: string;
  duration_minutes: number;
  estimated_cost: number;
  reasoning: string;
};

export type ToolTrace = {
  tool_name: string;
  input_summary: string;
  output_summary: string;
  duration_ms: number;
  used_fallback: boolean;
  error: string;
};

export type PlanResponse = {
  status: "ok" | "needs_clarification" | "fallback";
  itinerary: ItineraryItem[];
  total_cost: number;
  summary: string;
  trade_offs: string[];
  fallback_used: boolean;
  clarification_questions: string[];
  trace: ToolTrace[];
};

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function planSaturday(input: UserInput): Promise<PlanResponse> {
  const resp = await fetch(`${API_URL}/api/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API ${resp.status}: ${text}`);
  }
  return resp.json();
}
