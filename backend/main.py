from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.plan import router as plan_router
from core.logging_config import setup_logging
from core.config import settings

setup_logging()

app = FastAPI(
    title="Perfect Saturday Planner",
    description="AI agent that builds a personalised Saturday plan",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plan_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
