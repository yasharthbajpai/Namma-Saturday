# Namma Saturday

> AI-powered Saturday day planner for Bangalore — give it your budget, mood, and interests, get a full itinerary with reasoning, trade-offs, and a live agent trace.

---

## Live Demo

| | |
|---|---|
| **Live URL** | [https://namma-saturday.vercel.app](https://namma-saturday.vercel.app) |
| **Backend API** | [https://namma-saturday-production.up.railway.app/health](https://namma-saturday-production.up.railway.app/health) |
| **GitHub Repo** | [https://github.com/yasharthbajpai/Namma-Saturday](https://github.com/yasharthbajpai/Namma-Saturday) |
| **Loom Demo** | _Coming soon_ |

---

## How I Used AI Tools During the Build

- **Claude (via AWS Bedrock)** is the core LLM in the pipeline — it receives scored, filtered places and generates the final itinerary with per-stop reasoning, trade-offs, and time-logical ordering.
- **Cursor** (AI coding assistant) was used throughout development to scaffold the FastAPI pipeline, write the scoring logic in `filter_options.py`, debug SSE streaming, and iterate on the React trace UI — significantly speeding up the build.
- The tool pipeline is designed so that AI only owns the narrative layer (Tool 4); all budget math, constraint filtering, and scoring are deterministic Python — making the agent reliable, testable, and predictable even when the LLM is slow or unavailable.

---

## What It Does

Takes your city, budget, available time, mood, interests, and constraints, then runs them through a 4-tool pipeline:

1. **`parse_preferences`** — structures free-text input; asks clarifying questions when input is vague.
2. **`get_options`** — queries Google Places API for candidate venues; falls back to a curated Bangalore list if the API is unavailable.
3. **`filter_options`** — scores and filters candidates against budget and constraints; flags borderline items with trade-off notes.
4. **`build_itinerary`** — Claude (via AWS Bedrock) arranges the survivors into a time-logical plan with reasoning per stop; falls back to a deterministic Python itinerary if Bedrock is unavailable.

Every step is captured in a live trace shown in the UI as the plan streams in.

---

## Project Layout

```
backend/    FastAPI app — 4-tool agent pipeline, AWS Bedrock + Google Places integrations
frontend/   React + Vite + Tailwind — input form, streaming plan timeline, agent trace
```

---

## Run Locally

### Prerequisites

- Python 3.12+
- Node.js 18+
- AWS credentials with `bedrock:InvokeModel` permission (optional — fallback works without it)
- Google Places API key (optional — curated fallback works without it)

### Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your credentials in .env (see table below)
uvicorn main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`.

> The agent works **without any credentials** — Tool 2 falls back to a curated list and Tool 4 falls back to a deterministic Python itinerary. With credentials you get live Places data and Claude-generated reasoning.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
# Set VITE_API_URL=http://localhost:8000 (already the default)
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Notes |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | — | IAM user/role with `bedrock:InvokeModel` permission |
| `AWS_SECRET_ACCESS_KEY` | — | |
| `AWS_REGION` | `us-east-1` | Region where the Bedrock model is enabled |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-6` | Any Claude model enabled on Bedrock |
| `GOOGLE_PLACES_API_KEY` | — | Places API (New) enabled in Google Cloud Console |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins; set to your Vercel URL in production |

### Frontend (`frontend/.env`)

| Variable | Default | Notes |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | URL of the backend (local or deployed) |

---

## Features

| Requirement | Implementation |
|---|---|
| Hosted UI on a public URL | [namma-saturday.vercel.app](https://namma-saturday.vercel.app) (Vercel) + Railway backend |
| Understands preferences | `parse_preferences.py` — structured parsing with clarification flow |
| At least 3 tools/functions | 4 tools — `parse_preferences`, `get_options`, `filter_options`, `build_itinerary` |
| Realistic, specific plan | Tool 4 grounds Claude on real Places data with scores and ratings |
| Explains why each part fits | `reasoning` field on every itinerary item |
| Handles failure cases | Google Places failure → curated fallback; Bedrock failure → deterministic itinerary; both logged in trace |
| Agent trace | Returned in `PlanResponse.trace`, rendered live by `AgentTrace.tsx` via SSE |
| Clarifying questions when vague | Tool 1 detects missing/vague input, short-circuits pipeline, returns up to 2 questions |
| Trade-off explanations | Tool 3 flags borderline items; Tool 4 surfaces them in `trade_offs` array |
| Real data | Google Places API (Text Search New) |
| Streaming UX | `/api/plan/stream` emits SSE `thinking` + `trace` + `result` events |

---

## Notes

- The agent **never crashes**. Every failure path either uses a fallback or returns a graceful error structure with the trace populated — the UI always has something to show.
- Tools 1, 3 are pure Python — fast, deterministic, easy to test. Only Tools 2 and 4 hit external services.
- Budget math and constraint filtering are deterministic code, not LLM — Claude only owns narrative and time-logical ordering.
