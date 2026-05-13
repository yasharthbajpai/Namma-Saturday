# Perfect Saturday Planner

An AI agent that builds a personalised Saturday plan. Takes your city, budget, time,
mood, interests, and constraints, then runs them through a 5-tool pipeline:

1. **`parse_preferences`** — turns free text into structured preferences and asks
   clarifying questions when input is vague.
2. **`get_options`** — pulls candidate places from the Google Places API (with a
   curated fallback if the API is unavailable).
3. **`filter_options`** — scores and filters candidates against budget and
   constraints, flagging borderline items with trade-off notes.
4. **`build_itinerary`** — Claude (via AWS Bedrock) arranges the survivors into a
   time-logical plan, explains the reasoning, and generates a "minimal chill day"
   fallback when nothing matches.
5. **`cost_check`** — validates the plan against budget and trims if needed.

Every step is captured in a trace shown in the UI.

---

## Project Layout

```
backend/    FastAPI app — 5-tool pipeline, Bedrock + Google Places integrations
frontend/   React + Vite — input form, plan timeline, agent trace
```

---

## Run Locally

### Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in AWS + Google Places credentials in .env
uvicorn main:app --reload --port 8000
```

The agent still works **without** any credentials — Tool 2 falls back to a
curated list and Tool 4 falls back to a deterministic Python itinerary. With
credentials you get live Places data and Claude-generated reasoning.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
# Optionally point VITE_API_URL at your deployed backend
npm run dev
```

Open <http://localhost:5173>.

---

## Required Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Notes |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | — | IAM user/role with `bedrock:InvokeModel` permission |
| `AWS_SECRET_ACCESS_KEY` | — | |
| `AWS_REGION` | `us-east-1` | Region where Bedrock model is enabled |
| `BEDROCK_MODEL_ID` | `anthropic.claude-3-sonnet-20240229-v1:0` | Any Claude model on Bedrock |
| `GOOGLE_PLACES_API_KEY` | — | Places API (New) enabled in Google Cloud |

### Frontend (`frontend/.env`)

| Variable | Default | Notes |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | URL of the deployed backend |

---

## Features Mapped to the Assignment

| Requirement | Implementation |
|---|---|
| Hosted UI on a public URL | Vercel (frontend) + Railway (backend) |
| Understands preferences | Tool 1 `parse_preferences.py` |
| At least 3 tools/functions | 5 tools — parse, get_options, filter, build_itinerary, cost_check |
| Realistic, specific plan | Tool 4 grounds Claude on real Places data + scores |
| Explains why each part fits | `reasoning` field per itinerary item |
| Handles a failure case | Google Places failure → curated fallback. Bedrock failure → deterministic itinerary. Both logged in the trace. |
| Agent trace | Returned in `PlanResponse.trace`, rendered by `AgentTrace.tsx` |
| Clarifying questions when vague | Tool 1 detects missing/vague input, short-circuits, returns up to 2 questions |
| Trade-off explanations | Tool 3 flags borderline items, Tool 4 surfaces them in `reasoning` + `trade_offs` |
| Real data | Google Places API (Text Search New) |
| Fallback when no options match | Tool 4 generates a "minimal chill day" plan |

---

## Notes

- The agent NEVER crashes. Every failure path either uses a fallback or returns
  a graceful error structure with the trace populated, so the UI always has
  something to show.
- Tools 1, 3, 5 are pure Python — fast, deterministic, easy to test. Only
  Tools 2 and 4 hit external services.
- Budget math and constraint filtering are deterministic code, not LLM —
  Claude only owns narrative and time-logical ordering.
