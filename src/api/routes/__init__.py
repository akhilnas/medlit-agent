from fastapi import APIRouter, Depends

from src.api.dependencies import require_api_key
from src.api.routes.articles import router as articles_router
from src.api.routes.health import router as health_router
from src.api.routes.pipeline import router as pipeline_router
from src.api.routes.queries import router as queries_router
from src.api.routes.syntheses import router as syntheses_router

_protected = [Depends(require_api_key)]

router = APIRouter(prefix="/v1")
router.include_router(health_router, tags=["health"])  # open — used by ALB health checks
router.include_router(queries_router, dependencies=_protected)
router.include_router(pipeline_router, dependencies=_protected)
router.include_router(articles_router, dependencies=_protected)
router.include_router(syntheses_router, dependencies=_protected)
