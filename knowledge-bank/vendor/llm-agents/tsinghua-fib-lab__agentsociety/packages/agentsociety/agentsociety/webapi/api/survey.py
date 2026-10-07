import uuid
from typing import Any, Dict, List, cast

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .const import DEMO_USER_ID
from ..models import ApiResponseWrapper
from ..models.survey import ApiSurvey, Survey
from .timezone import ensure_timezone_aware

__all__ = ["router"]

router = APIRouter(tags=["surveys"])


@router.get("/surveys")
async def list_survey(request: Request) -> ApiResponseWrapper[List[ApiSurvey]]:
    """List all surveys"""

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        tenant_id = await request.app.state.get_tenant_id(request)
        stmt = select(Survey).where(Survey.tenant_id.in_([tenant_id, "", "default"]))
        results = await db.execute(stmt)
        db_surveys = [row[0] for row in results.all() if len(row) > 0]
        db_surveys = cast(List[ApiSurvey], db_surveys)
        
        # 处理时区
        for survey in db_surveys:
            survey.created_at = ensure_timezone_aware(survey.created_at)
            survey.updated_at = ensure_timezone_aware(survey.updated_at)
        
        return ApiResponseWrapper(data=db_surveys)


@router.get("/surveys/{id}")
async def get_survey(request: Request, id: uuid.UUID) -> ApiResponseWrapper[ApiSurvey]:
    """Get survey by ID"""

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        tenant_id = await request.app.state.get_tenant_id(request)
        stmt = select(Survey).where(
            Survey.tenant_id.in_([tenant_id, "", "default"]), Survey.id == id
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row or len(row) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Survey not found"
            )
        survey = row[0]
        
        # 处理时区
        survey.created_at = ensure_timezone_aware(survey.created_at)
        survey.updated_at = ensure_timezone_aware(survey.updated_at)
        
        return ApiResponseWrapper(data=ApiSurvey.model_validate(survey))


class ApiSurveyCreate(BaseModel):
    name: str
    """Survey name"""
    data: Dict[str, Any]
    """Survey data (any JSON object)"""


@router.post(
    "/surveys",
)
async def create_survey(
    request: Request,
    survey: ApiSurveyCreate,
):
    """Create a new survey"""

    if request.app.state.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Server is in read-only mode"
        )
    tenant_id = await request.app.state.get_tenant_id(request)
    if tenant_id == DEMO_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo user is not allowed to create surveys",
        )

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = insert(Survey).values(
            tenant_id=tenant_id, name=survey.name, data=survey.data
        )
        await db.execute(stmt)
        await db.commit()


class ApiSurveyUpdate(BaseModel):
    name: str
    """Survey name"""
    data: Dict[str, Any]
    """Survey data (any JSON object)"""


@router.put("/surveys/{id}")
async def update_survey(
    request: Request,
    id: uuid.UUID,
    survey: ApiSurveyUpdate,
):
    """Update survey by ID"""

    if request.app.state.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Server is in read-only mode"
        )
    tenant_id = await request.app.state.get_tenant_id(request)
    if tenant_id == DEMO_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo user is not allowed to update surveys",
        )

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = (
            update(Survey)
            .where(Survey.tenant_id == tenant_id, Survey.id == id)
            .values(name=survey.name, data=survey.data)
        )
        await db.execute(stmt)
        await db.commit()


@router.delete("/surveys/{id}", status_code=status.HTTP_200_OK)
async def delete_survey(request: Request, id: uuid.UUID):
    """Delete survey by ID"""
    if request.app.state.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Server is in read-only mode"
        )
    tenant_id = await request.app.state.get_tenant_id(request)
    if tenant_id == DEMO_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo user is not allowed to delete surveys",
        )

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = delete(Survey).where(Survey.tenant_id == tenant_id, Survey.id == id)
        await db.execute(stmt)
        await db.commit()
