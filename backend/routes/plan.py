from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from models.request import UserInput
from models.response import PlanResponse
from core.agent import run_agent
from core.pipeline import run_agent_stream

router = APIRouter(prefix="/api", tags=["plan"])


@router.post("/plan", response_model=PlanResponse)
async def create_plan(user_input: UserInput) -> PlanResponse:
    try:
        return await run_agent(user_input)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent failure: {exc}")


@router.post("/plan/stream")
async def create_plan_stream(user_input: UserInput) -> StreamingResponse:
    return StreamingResponse(
        run_agent_stream(user_input),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disables nginx buffering on Railway/Render
        },
    )
