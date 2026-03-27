"""Admin Panel — FastAPI + Jinja2 web dashboard for Income Platform."""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware

from app.config import settings

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(title="Income Platform Admin", docs_url=None, redoc_url=None)
app.add_middleware(GZipMiddleware)
import os as _os
_cors_origins = [o.strip() for o in _os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8200",
).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="app/templates")

# ── Import and mount routes ──
from app.routes import dashboard, services, scheduler, portfolio, alerts, proposals, analysts, newsletters, settings, proxy, api_portfolio, api_dashboard  # noqa: E402

app.include_router(dashboard.router)
app.include_router(services.router)
app.include_router(scheduler.router)
app.include_router(portfolio.router)
app.include_router(alerts.router)
app.include_router(proposals.router)
app.include_router(analysts.router)
app.include_router(newsletters.router)
app.include_router(settings.router)
app.include_router(api_portfolio.router)   # JSON API — before proxy to avoid catch-all
app.include_router(api_dashboard.router)   # Dashboard aggregate endpoint
app.include_router(proxy.router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "admin-panel"}
