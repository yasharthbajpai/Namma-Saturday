from fastapi import APIRouter, HTTPException
from models.request import UserInput
from models.response import PlanResponse
from core.agent import run_agent

router = APIRouter(prefix="/api", tags=["plan"])


@router.post("/plan", response_model=PlanResponse)
async def create_plan(user_input: UserInput) -> PlanResponse:
    try:
        return await run_agent(user_input)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent failure: {exc}")
