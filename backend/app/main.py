import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Load .env from repo root (one level up from backend/) and backend/ itself.
_repo_root = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=_repo_root / ".env", override=False)
load_dotenv(dotenv_path=_repo_root / "backend" / ".env", override=False)

# Force UTF-8 on stdout/stderr so Turkish characters in Jira summaries
# (Düzenleme, İçerik etc.) don't break the Windows cp1252 default console.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
    stream=sys.stdout,
    force=True,
)
log = logging.getLogger("sprintpilot")

from .routers import (  # noqa: E402  (env must load before routers init clients)
    auto_sprint,
    backlog,
    create_sprint,
    decompose,
    manager_dashboard,
    notifications,
    planning,
    review,
    sequence,
    simulate,
    sprints,
    status,
    tasks,
    team,
    team_performance,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("SprintPilot backend starting up")
    yield
    log.info("SprintPilot backend shutting down")


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

# CORS — allow any localhost/127.0.0.1 port. Browsers send Origin without trailing
# slash, so an exact-string list is fragile. Regex covers vite (5173), vite preview
# (4173), or any other dev port the team uses.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every HTTP request with method/path/origin/duration/status for debugging."""
    start = time.time()
    origin = request.headers.get("origin", "-")
    try:
        response = await call_next(request)
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        log.exception(
            "%s %s origin=%s -> EXCEPTION after %.0fms: %s",
            request.method, request.url.path, origin, elapsed, exc,
        )
        raise
    elapsed = (time.time() - start) * 1000
    if response.status_code >= 400:
        log.warning(
            "%s %s origin=%s -> %d in %.0fms",
            request.method, request.url.path, origin, response.status_code, elapsed,
        )
    else:
        log.info(
            "%s %s origin=%s -> %d in %.0fms",
            request.method, request.url.path, origin, response.status_code, elapsed,
        )
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


for router in (
    backlog.router,
    team.router,
    team_performance.router,
    sprints.router,
    planning.router,
    decompose.router,
    sequence.router,
    tasks.router,
    notifications.router,
    review.router,
    simulate.router,
    status.router,
    auto_sprint.router,
    manager_dashboard.router,
    create_sprint.router,
):
    app.include_router(router)
