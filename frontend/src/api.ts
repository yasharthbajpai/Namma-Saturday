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

// SSE event shapes emitted by /api/plan/stream
export type StreamEvent =
  | { type: "thinking"; step: number; message: string }
  | { type: "trace"; step: number; tool_name: string; output: string; duration_ms: number; used_fallback: boolean; error: string }
  | { type: "result"; plan: PlanResponse }
  | { type: "error"; message: string };

export async function planSaturdayStream(
  input: UserInput,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const resp = await fetch(`${API_URL}/api/plan/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!resp.ok || !resp.body) {
    const text = await resp.text();
    throw new Error(`API ${resp.status}: ${text}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const event: StreamEvent = JSON.parse(line.slice(6));
          onEvent(event);
        } catch {
          // ignore malformed lines
        }
      }
    }
  }
}
