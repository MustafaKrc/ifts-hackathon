from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env from repo root (one level up from backend/) and backend/ itself.
_repo_root = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=_repo_root / ".env", override=False)
load_dotenv(dotenv_path=_repo_root / "backend" / ".env", override=False)

from .routers import (  # noqa: E402  (env must load before routers init clients)
    backlog,
    decompose,
    notifications,
    planning,
    review,
    sequence,
    simulate,
    status,
    tasks,
    team,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="SprintPilot AI",
    description=(
        "AI Agile Control Tower + Sprint Decision Simulator. "
        "Reads Jira (read-only), produces predictive sizing, decomposition, "
        "dependency-aware sequencing, sprint health and what-if scenarios."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


for router in (
    backlog.router,
    team.router,
    planning.router,
    decompose.router,
    sequence.router,
    tasks.router,
    notifications.router,
    review.router,
    simulate.router,
    status.router,
):
    app.include_router(router)
