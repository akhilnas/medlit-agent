import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.clinical_query import (
    ClinicalQueryCreate,
    ClinicalQueryListResponse,
    ClinicalQueryResponse,
    ClinicalQueryUpdate,
    Pagination,
)
from src.core.database import get_db
from src.models.clinical_query import ClinicalQuery

router = APIRouter(prefix="/queries", tags=["clinical-queries"])


@router.get("", response_model=ClinicalQueryListResponse)
async def list_queries(
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ClinicalQueryListResponse:
    stmt = select(ClinicalQuery)
    if is_active is not None:
        stmt = stmt.where(ClinicalQuery.is_active == is_active)

    total: int = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    rows = (
        await db.execute(
            stmt.order_by(ClinicalQuery.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).scalars().all()

    return ClinicalQueryListResponse(
        data=[ClinicalQueryResponse.model_validate(q) for q in rows],
        pagination=Pagination(page=page, per_page=per_page, total=total),
    )


@router.post("", response_model=ClinicalQueryResponse, status_code=201)
async def create_query(
    body: ClinicalQueryCreate,
    db: AsyncSession = Depends(get_db),
) -> ClinicalQueryResponse:
    query = ClinicalQuery(
        id=uuid.uuid4(),
        **body.model_dump(),
    )
    db.add(query)
    await db.commit()
    await db.refresh(query)
    return ClinicalQueryResponse.model_validate(query)


@router.get("/{query_id}", response_model=ClinicalQueryResponse)
async def get_query(
    query_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ClinicalQueryResponse:
    query = await db.get(ClinicalQuery, query_id)
    if query is None:
        raise HTTPException(status_code=404, detail="Clinical query not found")
    return ClinicalQueryResponse.model_validate(query)


@router.patch("/{query_id}", response_model=ClinicalQueryResponse)
async def update_query(
    query_id: uuid.UUID,
    body: ClinicalQueryUpdate,
    db: AsyncSession = Depends(get_db),
) -> ClinicalQueryResponse:
    query = await db.get(ClinicalQuery, query_id)
    if query is None:
        raise HTTPException(status_code=404, detail="Clinical query not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(query, field, value)

    await db.commit()
    await db.refresh(query)
    return ClinicalQueryResponse.model_validate(query)


@router.delete("/{query_id}", status_code=204)
async def delete_query(
    query_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    query = await db.get(ClinicalQuery, query_id)
    if query is None:
        raise HTTPException(status_code=404, detail="Clinical query not found")
    await db.delete(query)
    await db.commit()
