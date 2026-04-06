from fastapi import APIRouter

from src.api.routes.articles import router as articles_router
from src.api.routes.health import router as health_router
from src.api.routes.pipeline import router as pipeline_router
from src.api.routes.queries import router as queries_router
from src.api.routes.syntheses import router as syntheses_router

router = APIRouter(prefix="/v1")
router.include_router(health_router, tags=["health"])
router.include_router(queries_router)
router.include_router(pipeline_router)
router.include_router(articles_router)
router.include_router(syntheses_router)
