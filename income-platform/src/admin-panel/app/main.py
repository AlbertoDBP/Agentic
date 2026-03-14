"""Admin Panel — FastAPI + Jinja2 web dashboard for Income Platform."""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware

from app.config import settings

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(title="Income Platform Admin", docs_url=None, redoc_url=None)
app.add_middleware(GZipMiddleware)

templates = Jinja2Templates(directory="app/templates")

# ── Import and mount routes ──
from app.routes import dashboard, services, scheduler, portfolio, alerts, proposals, analysts  # noqa: E402

app.include_router(dashboard.router)
app.include_router(services.router)
app.include_router(scheduler.router)
app.include_router(portfolio.router)
app.include_router(alerts.router)
app.include_router(proposals.router)
app.include_router(analysts.router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "admin-panel"}
