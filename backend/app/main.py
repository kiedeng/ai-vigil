from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import (
    alert_channels,
    analytics,
    auth,
    checks,
    dashboard,
    evaluator_prompts,
    golden,
    model_rules,
    new_api,
    runs,
    samples,
    settings,
)
from .config import get_settings
from .database import SessionLocal, init_db
from .services.bootstrap import seed_defaults
from .services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()
    start_scheduler()
    yield
    stop_scheduler()


settings_obj = get_settings()
app = FastAPI(title=settings_obj.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = settings_obj.api_prefix
app.include_router(auth.router, prefix=api_prefix)
app.include_router(dashboard.router, prefix=api_prefix)
app.include_router(analytics.router, prefix=api_prefix)
app.include_router(checks.router, prefix=api_prefix)
app.include_router(runs.router, prefix=api_prefix)
app.include_router(new_api.router, prefix=api_prefix)
app.include_router(model_rules.router, prefix=api_prefix)
app.include_router(samples.router, prefix=api_prefix)
app.include_router(evaluator_prompts.router, prefix=api_prefix)
app.include_router(golden.router, prefix=api_prefix)
app.include_router(alert_channels.router, prefix=api_prefix)
app.include_router(settings.router, prefix=api_prefix)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


dist_dir = Path(settings_obj.frontend_dist_dir)
if dist_dir.exists():
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa_fallback(path: str):
    index_file = dist_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Frontend dist not found. Run npm run build in frontend/."}
