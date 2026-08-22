# How I Build With AI — Namma Saturday

**Project:** [Namma Saturday](https://github.com/yasharthbajpai/Namma-Saturday) — an AI agent that plans a personalised Saturday in Bangalore
**Live app:** https://namma-saturday.vercel.app
**Repo:** https://github.com/yasharthbajpai/Namma-Saturday
**Backend health check:** https://namma-saturday-production.up.railway.app/health

---

## What it does

Namma Saturday takes a user's city, budget, available time, mood, interests, and constraints and runs them through a 4-tool pipeline to produce a full-day itinerary — with per-stop reasoning, trade-off notes on borderline choices, and a live "agent trace" that streams to the UI as each tool completes.

**Stack:** FastAPI (Python) backend, React + Vite + Tailwind frontend, Claude via AWS Bedrock as the reasoning layer, Google Places API for venue data.

## AI tools and where they sit

| Tool | Role |
|---|---|
| **Cursor** | Coding agent used throughout development — scaffolded the FastAPI pipeline, wrote the scoring logic in `filter_options.py`, debugged SSE streaming, iterated on the React trace UI |
| **Claude (via AWS Bedrock)** | Ships *inside* the product, not just during dev — it's Tool 4 in the pipeline, turning scored/filtered places into a time-ordered itinerary with reasoning |

---

## 1. Planning: deciding what the LLM should and shouldn't own

The clearest planning decision in this project is architectural: the LLM is boxed into exactly one stage.

- Tools 1–3 (`parse_preferences`, `get_options`, `filter_options`) are pure, deterministic Python — no model calls, fully testable.
- Only Tool 4 (`build_itinerary`) calls Claude, and only for narrative ordering and per-stop reasoning — not for budget math or constraint filtering.

This wasn't the original plan. The first version handed Claude the entire pipeline — parsing preferences, filtering venues by budget, *and* building the itinerary. 

The breaking point came when Claude decided a ₹500 budget meant "skip breakfast entirely and go straight to a ₹400 lunch." The math was wrong, the time gaps were nonsensical, and debugging via prompt tweaks felt like whack-a-mole.

**Prompt that failed:**
```
Given these preferences: budget ₹500, interests: cafes, parks, bookstores
Build a full-day itinerary in Bangalore with travel times between stops.
```

**What came back:** 3 places, total spend ₹720, "walking time: 15 mins" between stops 8km apart.

That's when I moved budget math, constraint filtering, and API calls into deterministic Python. Now Claude only sees pre-scored, pre-filtered options and writes narrative reasoning — much harder to hallucinate when the input is already valid.

## 2. Designing with AI

**Backend scaffold.** First prompt to Cursor:
```
Set up a FastAPI app with:
- routes/plan.py for the /plan endpoint
- core/agent.py as the orchestrator
- core/tools.py with parse_preferences, get_options, filter_options, build_itinerary
- Each tool returns structured output for the next stage
```

Cursor scaffolded the structure perfectly but made every tool async, which added zero value since Tools 1-3 are pure Python (no I/O). I stripped `async`/`await` from everything except Tool 4 (the Bedrock call) and the SSE endpoint itself. The first version also had tools taking raw dicts instead of Pydantic models — I added schemas for every tool boundary so type errors surface at dev time, not in production.

**Scoring logic (`filter_options.py`).** 

**Prompt:**
```
Write a scoring function that ranks Google Places results by:
- Hard constraint: price level must fit budget (eliminates options)
- Soft weights: rating (40%), distance from city center (30%), popularity (20%), opens-now (10%)
Return top 15 scored places
```

**Cursor's first pass:**
```python
def score_place(place):
    score = place['rating'] * 0.4 + (1 / place['distance']) * 0.3 + ...
    return score
```

Problem: it crashed on missing `distance` and treated a 3.2 rating the same as 4.8 (no normalization).

**After tuning:**
```python
def score_place(place, user_location):
    # Normalize rating to 0-1 (assuming 5-star scale)
    rating_score = (place.get('rating', 0) / 5.0) * 0.4
    
    # Distance penalty (inverse, capped at 15km)
    dist = haversine(user_location, place['coords'])
    dist_score = max(0, (1 - dist / 15000)) * 0.3
    
    # Popularity (log-scaled to prevent huge chains dominating)
    pop_score = min(1.0, math.log10(place.get('user_ratings_total', 1)) / 4) * 0.2
    
    # Open now: binary boost
    open_score = 0.1 if place.get('opening_hours', {}).get('open_now') else 0
    
    return rating_score + dist_score + pop_score + open_score
```

The key fix: missing fields default gracefully instead of crashing, and log-scaling popularity prevents Starbucks from always winning.

**Streaming (`/api/plan/stream`).** The API emits `thinking`, `trace`, and `result` events over SSE so the frontend shows tools completing in real time. SSE has real footguns — buffering, dropped connections, event framing — so this is a strong place to show actual back-and-forth.

**First ask to Cursor:**
```
Add SSE streaming to /api/plan/stream so the frontend can show progress as each tool completes.
Emit 'thinking' when a tool starts, 'trace' when it finishes, 'result' for the final itinerary.
```

**What broke:** All events arrived in a single burst at the end instead of streaming in real-time.

**Diagnosis:** 
1. Added `print()` statements in the event loop — they showed up immediately in the terminal
2. But the browser DevTools Network tab showed the response hanging until everything completed
3. Checked Railway logs (where it's deployed) — saw the events being written, but the proxy was buffering

**The fix:**
```python
# Before (Cursor's version):
async def stream_plan():
    yield f"event: thinking\ndata: Starting tool 1\n\n"
    result = tool_1()
    yield f"event: trace\ndata: {result}\n\n"
```

Problem: No explicit flush, and Railway's proxy buffers responses by default.

```python
# After:
from fastapi.responses import StreamingResponse

async def stream_plan():
    async def event_generator():
        yield f"event: thinking\ndata: Starting tool 1\n\n"
        await asyncio.sleep(0)  # Force yield to runtime
        result = tool_1()
        yield f"event: trace\ndata: {json.dumps(result)}\n\n"
        await asyncio.sleep(0)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disables nginx buffering on Railway
        }
    )
```

The `X-Accel-Buffering: no` header was the breakthrough — without it, Railway's reverse proxy holds the entire response.

**Frontend trace UI (`AgentTrace.tsx`).**

Started by describing the UX:
```
Build a React component that listens to SSE from /api/plan/stream and shows:
- A vertical timeline with 4 steps (one per tool)
- Each step starts gray, turns blue with a spinner when 'thinking' event arrives
- Turns green with a checkmark when 'trace' event arrives
- Shows the trace data below each completed step
Use Tailwind + lucide-react icons
```

Cursor generated a working first pass but the SSE listener had a memory leak — it never cleaned up the EventSource on unmount.

**The bug:**
```tsx
// Cursor's version
useEffect(() => {
  const es = new EventSource('/api/plan/stream');
  es.addEventListener('trace', (e) => setTraces([...traces, JSON.parse(e.data)]));
  // Missing cleanup!
}, []);
```

Every component re-mount spawned a new EventSource but never closed the old one. After 3-4 runs, the browser had 12 open connections.

**The fix:**
```tsx
useEffect(() => {
  const es = new EventSource('/api/plan/stream');
  
  es.addEventListener('thinking', (e) => { /* ... */ });
  es.addEventListener('trace', (e) => { /* ... */ });
  
  return () => es.close();  // Cleanup on unmount
}, []);
```

Also asked Cursor to add a "copy trace as JSON" button — it nailed that on first try, used `navigator.clipboard.writeText()`.

## 3. Debugging: where it went wrong

This is the part the request cared about most, so it's worth being specific rather than general. A few prompts, in case they jog something concrete:

- A case where Cursor's first implementation looked right but broke at runtime (SSE not flushing, a CORS misconfiguration, a fallback path silently swallowing an error instead of surfacing it).
- A case where Claude's itinerary output (Tool 4) came back malformed, hallucinated a place, or ignored a constraint — and how you constrained the prompt or output schema to fix it.
- Any point where you had to override or discard what the agent suggested because it was confidently wrong, and how you caught it.

### Case 1: Claude hallucinating places that don't exist

**The bug:** Tool 4 (`build_itinerary`) was supposed to pick from the filtered venue list, but Claude kept inventing places.

**Bad output:**
```json
{
  "itinerary": [
    {"time": "10:00", "place": "Cubbon Park", "reason": "Great for morning walks"},
    {"time": "12:30", "place": "The Hidden Gem Café", "reason": "Cozy spot with local art"},
    {"time": "15:00", "place": "Bangalore Book Haven", "reason": "Indie bookstore vibe"}
  ]
}
```

Problem: "The Hidden Gem Café" and "Bangalore Book Haven" don't exist. Claude made them up because the prompt said "build an itinerary" without constraining it to the input list.

**Original prompt to Claude:**
```
Build a day itinerary in Bangalore based on these preferences:
- Budget: ₹800
- Interests: cafes, bookstores, parks
- Available time: 10am-6pm
```

**The fix — changed the prompt structure:**
```
You are Tool 4 in a pipeline. Your ONLY job is to arrange these pre-filtered places into a time-ordered itinerary.

INPUT PLACES (you must use ONLY these, no others):
{json.dumps(filtered_places)}

OUTPUT: A JSON array with fields: time, place_id, place_name, reasoning
DO NOT invent new places. DO NOT add places not in the input list.
```

Also switched the response format to require `place_id` — Claude had to reference the actual ID from the input, making hallucination harder.

---

### Case 2: CORS blocking the frontend from calling the Railway-deployed backend

**The bug:** Frontend on Vercel (`namma-saturday.vercel.app`) couldn't call the backend on Railway (`namma-saturday-production.up.railway.app`). Browser console:

```
Access to fetch at 'https://namma-saturday-production.up.railway.app/api/plan/stream' 
from origin 'https://namma-saturday.vercel.app' has been blocked by CORS policy
```

**First attempt — asked Cursor:**
```
Add CORS middleware to FastAPI so the Vercel frontend can call it
```

**What it generated:**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

This worked in local dev (`localhost:5173` → `localhost:8000`) but still failed in production. Turned out Railway was stripping the CORS headers.

**The actual fix:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://namma-saturday.vercel.app",
        "http://localhost:5173",  # Local dev
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type"],  # Required for SSE
)
```

The missing piece: `expose_headers=["Content-Type"]` for SSE responses. Without it, the browser couldn't read the `text/event-stream` content type.

One piece of the final design that *is* directly debugging-shaped: every external dependency has a deterministic fallback path, and both are logged in the trace.

- Google Places unavailable → falls back to a curated Bangalore venue list
- Bedrock/Claude unavailable → falls back to a deterministic Python itinerary builder

**Added after hitting real outages.**

**The Google Places incident:** During a demo to a friend, the `/api/plan/stream` call hung for 30 seconds, then returned:
```json
{"error": "Google Places API quota exceeded"}
```

The daily free tier is 2,500 requests. I'd been testing all day and hit the limit at the worst possible moment. No fallback = the entire pipeline died.

**The fix:**
```python
# In get_options.py (Tool 2)
try:
    places = fetch_from_google_places(query, api_key)
except (HTTPError, Timeout):
    logger.warning("Google Places unavailable, falling back to curated list")
    places = load_bangalore_venues_from_csv()  # 200 hand-picked spots
```

The curated list is a CSV with ~200 Bangalore venues (Cubbon Park, MTR, Koshy's, etc.) that I seeded manually. Not as fresh as the live API, but better than a blank screen.

**The Bedrock incident:** AWS Bedrock threw a `ThrottlingException` during a burst of 5 requests in 10 seconds (I was testing the retry logic itself, ironically).

```python
# In build_itinerary.py (Tool 4)
try:
    itinerary = call_claude_via_bedrock(prompt)
except ThrottlingException:
    logger.warning("Bedrock throttled, using deterministic fallback")
    itinerary = build_itinerary_deterministic(filtered_places)
```

The deterministic fallback just sorts places by score, bins them into time slots (10am, 12pm, 3pm, 5pm), and returns a JSON structure — no reasoning field, but functional.

Both fallbacks now log to the `trace` so users see "⚠ Using fallback: curated venue list" in the UI instead of a silent degradation.

## 4. What I'd do differently

1. **More structured output from the start.** I prompted Claude with free-form JSON and spent days fixing malformed responses. Next time: use AWS Bedrock's native JSON mode or constrain the schema upfront with a tool like Guardrails AI.

2. **Test the failure paths first.** I only added fallbacks *after* hitting quota limits in production. Should've tested "what if Google Places returns 429" on day one by mocking the failure.

3. **Move travel-time estimation out of Claude entirely.** Right now Tool 4 generates vague time windows ("10:00-11:30 at Cubbon Park"), but it doesn't account for actual travel time between stops. A deterministic function using Google Directions API would be more accurate than Claude guessing "15 min walk" between places 3km apart.

4. **Stop asking Cursor to write comments.** Half the generated comments were outdated by the next refactor. Better to invest that time in clear function names and docstrings at module boundaries only.

---

## Summary

Namma Saturday demonstrates how to build with AI by keeping the LLM contained to the parts it's actually good at — narrative reasoning and output structuring — while leaving math, filtering, and external API calls to deterministic code. The biggest lesson: constraint the model's input and output format early, test failure paths before production, and use streaming + fallbacks to make the product resilient when APIs inevitably fail.

The full codebase and deployment are linked at the top. This project took approximately 3 weeks from first commit to launch, with AI tools (Cursor for code generation, Claude via Bedrock in production) accelerating the development cycle while requiring careful prompt engineering and validation to avoid hallucinations.
