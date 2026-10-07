from datetime import datetime, timezone
import json
import uuid
from typing import List, Optional, cast

from fastapi import APIRouter, Body, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ApiResponseWrapper
from ..models.agent import (
    AgentDialogType,
    ApiAgentDialog,
    ApiAgentProfile,
    ApiAgentStatus,
    ApiAgentSurvey,
    ApiGlobalPrompt,
    agent_dialog,
    agent_profile,
    agent_status,
    agent_survey,
    global_prompt,
    pending_dialog,
    pending_survey,
)
from ..models.experiment import Experiment, ExperimentStatus
from ..models.survey import Survey
from .experiment import _find_started_experiment_by_id
from .timezone import ensure_timezone_aware

__all__ = ["router"]

router = APIRouter(tags=["agent"])


@router.get("/experiments/{exp_id}/agents/{agent_id}/dialog")
async def get_agent_dialog_by_exp_id_and_agent_id(
    request: Request,
    exp_id: uuid.UUID,
    agent_id: int,
) -> ApiResponseWrapper[List[ApiAgentDialog]]:
    """Get dialog by experiment ID and agent ID"""

    # Check whether the experiment is started
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        experiment = await _find_started_experiment_by_id(request, db, exp_id)

        # Generate table name dynamically
        table_name = experiment.agent_dialog_tablename
        table, columns = agent_dialog(table_name)
        stmt = (
            select(table).where(table.c.id == agent_id).order_by(table.c.day, table.c.t)
        )
        rows = (await db.execute(stmt)).all()
        dialogs: List[ApiAgentDialog] = []
        for row in rows:
            dialog = {columns[i]: row[i] for i in range(len(columns))}
            if "created_at" in dialog:
                dialog["created_at"] = ensure_timezone_aware(dialog["created_at"])
            dialogs.append(ApiAgentDialog(**dialog))

        # Get pending dialogs
        table_name = experiment.pending_dialog_tablename
        pending_table, pending_columns = pending_dialog(table_name)
        pending_stmt = (
            select(pending_table)
            .where(pending_table.c.agent_id == agent_id)
            .where(pending_table.c.processed == False)
            .order_by(pending_table.c.created_at)
        )
        pending_rows = (await db.execute(pending_stmt)).all()
        for row in pending_rows:
            dialog = {pending_columns[i]: row[i] for i in range(len(pending_columns))}

            dialogs.append(ApiAgentDialog(
                id=agent_id,
                day=dialog["day"],
                t=dialog["t"],
                type=AgentDialogType.User,
                speaker="user",
                content=dialog["content"],
                created_at=ensure_timezone_aware(dialog["created_at"]),
            ))
        dialogs.sort(key=lambda x: (x.day, x.t))

        return ApiResponseWrapper(data=dialogs)


@router.get(
    "/experiments/{exp_id}/agents/-/profile",
)
async def list_agent_profile_by_exp_id(
    request: Request,
    exp_id: uuid.UUID,
) -> ApiResponseWrapper[List[ApiAgentProfile]]:
    """List agent profile by experiment ID"""

    async with request.app.state.get_db() as db:
        experiment = await _find_started_experiment_by_id(request, db, exp_id)

        table_name = experiment.agent_profile_tablename
        table, columns = agent_profile(table_name)
        stmt = select(table)
        rows = (await db.execute(stmt)).all()
        profiles: List[ApiAgentProfile] = []
        for row in rows:
            profile = {columns[i]: row[i] for i in range(len(columns))}
            if "profile" in profile and isinstance(profile["profile"], str):
                profile["profile"] = json.loads(profile["profile"])
            profiles.append(ApiAgentProfile(**profile))

        return ApiResponseWrapper(data=profiles)


@router.get(
    "/experiments/{exp_id}/agents/{agent_id}/profile",
)
async def get_agent_profile_by_exp_id_and_agent_id(
    request: Request,
    exp_id: uuid.UUID,
    agent_id: int,
) -> ApiResponseWrapper[ApiAgentProfile]:
    """Get agent profile by experiment ID and agent ID"""

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        experiment = await _find_started_experiment_by_id(request, db, exp_id)

        table_name = experiment.agent_profile_tablename
        table, columns = agent_profile(table_name)
        stmt = select(table).where(table.c.id == agent_id).limit(1)
        row = (await db.execute(stmt)).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agent profile not found"
            )
        profile = {columns[i]: row[i] for i in range(len(columns))}
        if "profile" in profile and isinstance(profile["profile"], str):
            profile["profile"] = json.loads(profile["profile"])
        profile = ApiAgentProfile(**profile)

        return ApiResponseWrapper(data=profile)


@router.get("/experiments/{exp_id}/agents/-/status")
async def list_agent_status_by_day_and_t(
    request: Request,
    exp_id: uuid.UUID,
    day: Optional[int] = Query(None, description="the day for getting agent status"),
    t: Optional[float] = Query(None, description="the time for getting agent status"),
) -> ApiResponseWrapper[List[ApiAgentStatus]]:
    """List agent status by experiment ID, day and time"""

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        experiment = await _find_started_experiment_by_id(request, db, exp_id)

        if day is None:
            day = experiment.cur_day
        if t is None:
            t = experiment.cur_t

        table_name = experiment.agent_status_tablename
        table, columns = agent_status(table_name)
        stmt = select(table).where(table.c.day == day).where(table.c.t == t)
        rows = (await db.execute(stmt)).all()
        statuses: List[ApiAgentStatus] = []
        for row in rows:
            s = {columns[i]: row[i] for i in range(len(columns))}
            if "status" in s and isinstance(s["status"], str):
                try:
                    s["status"] = json.loads(s["status"])
                except Exception:
                    pass
            if "created_at" in s:
                s["created_at"] = ensure_timezone_aware(s["created_at"])
            statuses.append(ApiAgentStatus(**s))

        return ApiResponseWrapper(data=statuses)


@router.get("/experiments/{exp_id}/agents/{agent_id}/status")
async def get_agent_status_by_exp_id_and_agent_id(
    request: Request,
    exp_id: uuid.UUID,
    agent_id: int,
) -> ApiResponseWrapper[List[ApiAgentStatus]]:
    """Get agent status by experiment ID and agent ID"""

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        experiment = await _find_started_experiment_by_id(request, db, exp_id)

        table_name = experiment.agent_status_tablename
        table, columns = agent_status(table_name)
        stmt = (
            select(table).where(table.c.id == agent_id).order_by(table.c.day, table.c.t)
        )
        rows = (await db.execute(stmt)).all()
        statuses: List[ApiAgentStatus] = []
        for row in rows:
            s = {columns[i]: row[i] for i in range(len(columns))}
            if "status" in s and isinstance(s["status"], str):
                try:
                    s["status"] = json.loads(s["status"])
                except Exception:
                    pass
            if "created_at" in s:
                s["created_at"] = ensure_timezone_aware(s["created_at"])
            statuses.append(ApiAgentStatus(**s))

        return ApiResponseWrapper(data=statuses)


@router.get("/experiments/{exp_id}/agents/{agent_id}/survey")
async def get_agent_survey_by_exp_id_and_agent_id(
    request: Request,
    exp_id: uuid.UUID,
    agent_id: int,
) -> ApiResponseWrapper[List[ApiAgentSurvey]]:
    """Get survey by experiment ID and agent ID"""

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        experiment = await _find_started_experiment_by_id(request, db, exp_id)

        table_name = experiment.agent_survey_tablename
        table, columns = agent_survey(table_name)
        stmt = (
            select(table).where(table.c.id == agent_id).order_by(table.c.day, table.c.t)
        )
        rows = (await db.execute(stmt)).all()
        surveys: List[ApiAgentSurvey] = []
        for row in rows:
            survey = {columns[i]: row[i] for i in range(len(columns))}
            if "data" in survey and isinstance(survey["data"], str):
                survey["data"] = json.loads(survey["data"])
            if "created_at" in survey:
                survey["created_at"] = ensure_timezone_aware(survey["created_at"])
            surveys.append(ApiAgentSurvey(**survey))

        # Get pending surveys

        table_name = experiment.pending_survey_tablename
        pending_table, pending_columns = pending_survey(table_name)
        pending_stmt = (
            select(pending_table)
            .where(pending_table.c.agent_id == agent_id)
            .where(pending_table.c.processed == False)
            .order_by(pending_table.c.created_at)
        )
        pending_rows = (await db.execute(pending_stmt)).all()
        for row in pending_rows:
            survey = {pending_columns[i]: row[i] for i in range(len(pending_columns))}
            surveys.append(ApiAgentSurvey(
                id=agent_id,
                day=survey["day"],
                t=survey["t"],
                survey_id=survey["survey_id"],
                result=None,
                created_at=ensure_timezone_aware(survey["created_at"]),
            ))
        surveys.sort(key=lambda x: (x.day, x.t))

        return ApiResponseWrapper(data=surveys)


@router.get("/experiments/{exp_id}/prompt")
async def get_global_prompt_by_day_t(
    request: Request,
    exp_id: uuid.UUID,
    day: Optional[int] = Query(None, description="the day for getting agent status"),
    t: Optional[float] = Query(None, description="the time for getting agent status"),
) -> ApiResponseWrapper[Optional[ApiGlobalPrompt]]:
    """Get global prompt by experiment ID, day and time"""

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        experiment = await _find_started_experiment_by_id(request, db, exp_id)

        if day is None:
            day = experiment.cur_day
        if t is None:
            t = experiment.cur_t

        table_name = experiment.global_prompt_tablename
        table, columns = global_prompt(table_name)
        stmt = select(table).where(table.c.day == day).where(table.c.t == t)
        row = (await db.execute(stmt)).first()
        if row is None:
            return ApiResponseWrapper(data=None)
        prompt_data = {columns[i]: row[i] for i in range(len(columns))}
        if "created_at" in prompt_data:
            prompt_data["created_at"] = ensure_timezone_aware(prompt_data["created_at"])
        prompt = ApiGlobalPrompt(**prompt_data)

        return ApiResponseWrapper(data=prompt)


class AgentChatMessage(BaseModel):
    content: str
    day: int
    t: float


@router.post("/experiments/{exp_id}/agents/{agent_id}/dialog")
async def post_agent_dialog(
    request: Request,
    exp_id: uuid.UUID,
    agent_id: int,
    message: AgentChatMessage = Body(...),
) -> ApiResponseWrapper[None]:
    """Send dialog to agent by experiment ID and agent ID"""

    # Get tenant_id from request
    tenant_id = await request.app.state.get_tenant_id(request)

    # Check whether the experiment is started and belongs to the tenant
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = select(Experiment).where(
            Experiment.tenant_id == tenant_id, Experiment.id == exp_id
        )
        result = await db.execute(stmt)
        experiment = result.scalar_one_or_none()
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found or you don't have permission to access it",
            )

        if ExperimentStatus(experiment.status) != ExperimentStatus.RUNNING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Experiment not running"
            )

        # Store the dialog request in pending_dialog table
        table_name = experiment.pending_dialog_tablename
        table, _ = pending_dialog(table_name)
        stmt = table.insert().values(
            agent_id=agent_id,
            day=message.day,
            t=message.t,
            content=message.content,
            created_at=datetime.now(timezone.utc),
            processed=False,
        )
        await db.execute(stmt)
        await db.commit()

        return ApiResponseWrapper(data=None)


class AgentSurveyMessage(BaseModel):
    survey_id: uuid.UUID
    day: int
    t: float


@router.post("/experiments/{exp_id}/agents/{agent_id}/survey")
async def post_agent_survey(
    request: Request,
    exp_id: uuid.UUID,
    agent_id: int,
    message: AgentSurveyMessage = Body(...),
) -> ApiResponseWrapper[None]:
    """Send survey to agent by experiment ID and agent ID"""

    # Get tenant_id from request
    tenant_id = await request.app.state.get_tenant_id(request)

    # Check whether the experiment is started and belongs to the tenant
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = select(Experiment).where(
            Experiment.tenant_id == tenant_id, Experiment.id == exp_id
        )
        result = await db.execute(stmt)
        experiment = result.scalar_one_or_none()
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found or you don't have permission to access it",
            )

        if ExperimentStatus(experiment.status) != ExperimentStatus.RUNNING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Experiment not running"
            )

        # Check whether the survey exists
        stmt = select(Survey).where(
            Survey.tenant_id.in_([tenant_id, "", "default"]), Survey.id == message.survey_id
        )
        result = await db.execute(stmt)
        survey = result.scalar_one_or_none()
        if not survey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Survey not found"
            )

        # Store the survey request in pending_survey table
        table_name = experiment.pending_survey_tablename
        table, _ = pending_survey(table_name)
        stmt = table.insert().values(
            agent_id=agent_id,
            day=message.day,
            t=message.t,
            survey_id=message.survey_id,
            data=survey.data,
            created_at=datetime.now(timezone.utc),
            processed=False,
        )
        await db.execute(stmt)
        await db.commit()

        return ApiResponseWrapper(data=None)
