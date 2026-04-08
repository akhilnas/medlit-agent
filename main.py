from contextlib import asynccontextmanager

import prometheus_client
from fastapi import Depends, FastAPI
from fastapi.responses import PlainTextResponse

from src.api.dependencies import require_api_key
from src.api.middleware import CorrelationIdMiddleware, PrometheusMiddleware, SecurityHeadersMiddleware
from src.api.routes import router
from src.core.config import settings
from src.core.logging import configure_logging

# Configure structured logging before anything else creates a logger
configure_logging()

# Disable interactive docs in production; keep available in debug/dev
_docs_url = "/docs" if settings.debug else None
_redoc_url = "/redoc" if settings.debug else None
_openapi_url = "/openapi.json" if settings.debug else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.core.database import get_db
    from src.services.scheduler import PipelineScheduler

    scheduler = PipelineScheduler(
        db_factory=get_db,
        enabled=settings.scheduler_enabled,
    )
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    scheduler.shutdown()


app = FastAPI(
    title="MedLit Agent",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(PrometheusMiddleware)

app.include_router(router)


@app.get("/metrics", include_in_schema=False, dependencies=[Depends(require_api_key)])
async def metrics() -> PlainTextResponse:
    """Prometheus scrape endpoint — protected by API key."""
    data = prometheus_client.generate_latest()
    return PlainTextResponse(
        data.decode("utf-8"),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
