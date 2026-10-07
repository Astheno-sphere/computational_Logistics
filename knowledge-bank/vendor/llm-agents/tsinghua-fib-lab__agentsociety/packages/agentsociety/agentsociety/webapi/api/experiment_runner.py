import asyncio
import base64
import json
import logging
import uuid
from typing import Optional, cast

from fastapi import APIRouter, Body, HTTPException, Query, Request, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...configs import (
    Config,
    EnvConfig,
    MapConfig as SimMapConfig,
    AgentsConfig as SimAgentsConfig,
)
from ...filesystem import FileSystemClient
from ...executor import ProcessExecutor
from ..models import ApiResponseWrapper
from ..models.config import AgentConfig, LLMConfig, MapConfig, WorkflowConfig
from ..models.experiment import Experiment, ExperimentStatus, RunningExperiment
from .const import DEMO_USER_ID
from .config import _convert_survey_id_to_survey_data

__all__ = ["router"]

router = APIRouter(tags=["experiment_runner"])
logger = logging.getLogger(__name__)


class ConfigPrimaryKey(BaseModel):
    """Config primary key model"""

    tenant_id: str
    id: str


class ExperimentRequest(BaseModel):
    """Experiment request model"""

    llm: ConfigPrimaryKey
    agents: ConfigPrimaryKey
    map: ConfigPrimaryKey
    workflow: ConfigPrimaryKey
    exp_name: str


class ExperimentResponse(BaseModel):
    """Experiment response model"""

    id: str


@router.post("/run-experiments")
async def run_experiment(
    request: Request, config: ExperimentRequest = Body(...)
) -> ApiResponseWrapper[ExperimentResponse]:
    """Start a new experiment"""
    if request.app.state.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Server is in read-only mode",
        )
    tenant_id = await request.app.state.get_tenant_id(request)
    if tenant_id == DEMO_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo user is not allowed to run experiments",
        )
    # if the tenant_id in config is not "" or tenant_id, 403
    if config.llm.tenant_id not in [tenant_id, ""]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    if config.agents.tenant_id not in [tenant_id, ""]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    if config.map.tenant_id not in [tenant_id, ""]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    if config.workflow.tenant_id not in [tenant_id, ""]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    webui_fs_client = request.app.state.env.fs_client
    # get config from db
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)

        # 使用商业化余额检查（如果可用）
        if not await _check_commercial_balance(request.app.state, tenant_id, db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="余额不足 / Insufficient balance",
            )

        # ===== LLM config =====
        stmt = select(LLMConfig.config).where(
            LLMConfig.tenant_id == config.llm.tenant_id,
            LLMConfig.id == uuid.UUID(config.llm.id),
        )
        llm_config = (await db.execute(stmt)).scalar_one_or_none()
        if llm_config is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="LLM config not found"
            )
        # ===== Agent config =====
        stmt = select(AgentConfig.config).where(
            AgentConfig.tenant_id == config.agents.tenant_id,
            AgentConfig.id == uuid.UUID(config.agents.id),
        )
        agent_config = (await db.execute(stmt)).scalar_one_or_none()
        if agent_config is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Agent config not found"
            )
        sim_agent_config = SimAgentsConfig.model_validate(agent_config)
        if isinstance(webui_fs_client, FileSystemClient):
            for agent_list in [
                sim_agent_config.citizens,
                sim_agent_config.firms,
                sim_agent_config.banks,
                sim_agent_config.nbs,
                sim_agent_config.governments,
            ]:
                for one in agent_list:
                    if one.memory_from_file is not None:
                        one.memory_from_file = webui_fs_client.get_absolute_path(
                            one.memory_from_file
                        )
        agent_config = sim_agent_config.model_dump()
        # ===== Map config =====
        stmt = select(MapConfig.config).where(
            MapConfig.tenant_id == config.map.tenant_id,
            MapConfig.id == uuid.UUID(config.map.id),
        )
        map_config = (await db.execute(stmt)).scalar_one_or_none()
        if map_config is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Map config not found"
            )
        # change map_config to pydantic model
        sim_map_config = SimMapConfig.model_validate(map_config)
        if isinstance(webui_fs_client, FileSystemClient):
            sim_map_config.file_path = webui_fs_client.get_absolute_path(
                sim_map_config.file_path
            )
        map_config = sim_map_config.model_dump()
        # ===== Workflow config =====
        stmt = select(WorkflowConfig.config).where(
            WorkflowConfig.tenant_id == config.workflow.tenant_id,
            WorkflowConfig.id == uuid.UUID(config.workflow.id),
        )
        workflow_config = (await db.execute(stmt)).scalar_one_or_none()
        if workflow_config is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow config not found",
            )
        
        # 转换survey ID为survey data
        workflow_config = await _convert_survey_id_to_survey_data(db, tenant_id, workflow_config)
    # Generate unique experiment ID
    experiment_id = str(uuid.uuid4())
    c = {
        "llm": llm_config,
        "env": cast(EnvConfig, request.app.state.env).model_dump(),
        "map": map_config,
        "agents": agent_config,
        "exp": {
            "id": experiment_id,
            "name": config.exp_name,
            "workflow": workflow_config,
            "environment": {
                "start_tick": 28800,
            },
        },
    }
    logger.debug(f"Received experiment config: {json.dumps(c, indent=2)}")

    # Config model validate
    try:
        Config.model_validate(c)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

    # Convert config to base64
    config_base64 = base64.b64encode(json.dumps(c).encode()).decode()

    # Start experiment container
    # Create an async task and get its result
    auth_token = uuid.uuid4().hex

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = insert(RunningExperiment).values(
            tenant_id=tenant_id,
            id=uuid.UUID(experiment_id),
            callback_auth_token=auth_token,
        )
        await db.execute(stmt)
        await db.commit()

        await _record_experiment_bill(
            request.app.state,
            db,
            tenant_id,
            uuid.UUID(experiment_id),
            uuid.UUID(config.llm.id) if config.llm.tenant_id == "" else None,
        )

    executor = cast(ProcessExecutor, request.app.state.executor)
    task = asyncio.create_task(
        executor.create(
            config_base64=config_base64,
            tenant_id=tenant_id,
            callback_url=request.app.state.callback_url,
            callback_auth_token=auth_token,
        )
    )

    # Set up a callback function to handle task completion
    def container_started(future):
        try:
            container_id = future.result()
            logger.info(f"Container started with ID: {container_id}")
        except Exception as e:
            logger.error(f"Error starting container: {e}")

    # Add callback
    task.add_done_callback(container_started)

    logger.info("Successfully created experiment container task")

    return ApiResponseWrapper(
        data=ExperimentResponse(id=experiment_id),
    )


@router.delete("/run-experiments/{exp_id}")
async def delete_experiment(
    request: Request,
    exp_id: str,
):
    """Delete an experiment pod"""
    if request.app.state.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Server is in read-only mode",
        )
    tenant_id = await request.app.state.get_tenant_id(request)
    if tenant_id == DEMO_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo user is not allowed to delete experiments",
        )
    executor = cast(ProcessExecutor, request.app.state.executor)
    await executor.delete(tenant_id, exp_id)

    # convert exp_id into uuid
    exp_id = uuid.UUID(exp_id)

    # update experiment status to STOPPED
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = (
            update(Experiment)
            .where(Experiment.tenant_id == tenant_id, Experiment.id == exp_id)
            .values(status=ExperimentStatus.STOPPED, error="Experiment stopped by user")
        )
        await db.execute(stmt)
        await db.commit()

        stmt = select(Experiment).where(
            Experiment.tenant_id == tenant_id, Experiment.id == exp_id
        )
        experiment = (await db.execute(stmt)).scalar_one_or_none()
        await _compute_commercial_bill(request.app.state, db, experiment)

        # delete the running experiment
        stmt = delete(RunningExperiment).where(
            RunningExperiment.id == exp_id,
        )
        await db.execute(stmt)
        await db.commit()


@router.get("/run-experiments/{exp_id}/log")
async def get_experiment_logs(
    request: Request,
    exp_id: str,
) -> str:
    """Get experiment pod logs"""
    tenant_id = await request.app.state.get_tenant_id(request)
    if tenant_id == DEMO_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo user is not allowed to view experiment logs",
        )
    executor = cast(ProcessExecutor, request.app.state.executor)
    logs = await executor.get_logs(tenant_id, exp_id)
    return logs


@router.get("/run-experiments/{exp_id}/status")
async def get_experiment_status(
    request: Request,
    exp_id: str,
) -> ApiResponseWrapper[str]:
    """Get experiment pod status"""
    tenant_id = await request.app.state.get_tenant_id(request)
    if tenant_id == DEMO_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo user is not allowed to view experiment status",
        )
    executor = cast(ProcessExecutor, request.app.state.executor)
    pod_status = await executor.get_status(tenant_id, exp_id)
    return ApiResponseWrapper(
        data=pod_status,
    )


@router.post("/run-experiments/{exp_id}/finish")
async def finish_experiment(
    request: Request,
    exp_id: str,
    callback_auth_token: str = Query(...),
):
    """Finish an experiment"""
    if request.app.state.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Server is in read-only mode",
        )
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        # 1. check the callback_auth_token is valid
        stmt = select(RunningExperiment).where(
            RunningExperiment.id == exp_id,
            RunningExperiment.callback_auth_token == callback_auth_token,
        )
        running_experiment = (await db.execute(stmt)).scalar_one_or_none()
        if running_experiment is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Running experiment not found",
            )
        # 2. check the experiment is FINISHED or STOPPED
        tenant_id = running_experiment.tenant_id
        stmt = select(Experiment).where(
            Experiment.tenant_id == tenant_id,
            Experiment.id == exp_id,
            Experiment.status.in_(
                [ExperimentStatus.FINISHED, ExperimentStatus.STOPPED]
            ),
        )
        experiment = (await db.execute(stmt)).scalar_one_or_none()
        if experiment is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment is not finished or stopped",
            )
        # 3. compute the bill
        await _compute_commercial_bill(request.app.state, db, experiment)
        # 4. delete the running experiment
        stmt = delete(RunningExperiment).where(
            RunningExperiment.id == exp_id,
        )
        await db.execute(stmt)
        await db.commit()


async def _compute_commercial_bill(app_state, db: AsyncSession, experiment: Experiment):
    """compute commercial bill"""
    try:
        billing_system = getattr(app_state, "billing_system", None)
        if billing_system and "compute_bill" in billing_system:
            rates = billing_system.get("rates", {})
            await billing_system["compute_bill"](db, experiment, rates)
            return
    except Exception as e:
        logger.warning(f"Failed to compute commercial bill: {e}")

    # 如果商业化功能不可用，跳过计费
    logger.info("No commercial billing system available, skipping billing")


async def _check_commercial_balance(app_state, tenant_id: str, db: AsyncSession):
    """check commercial balance"""
    try:
        billing_system = getattr(app_state, "billing_system", None)
        if billing_system and "check_balance" in billing_system:
            return await billing_system["check_balance"](tenant_id, db)
    except Exception as e:
        logger.warning(f"Failed to check commercial balance: {e}")
    return True  # 如果没有商业化功能，默认允许


async def _record_experiment_bill(
    app_state,
    db: AsyncSession,
    tenant_id: str,
    exp_id: uuid.UUID,
    llm_config_id: Optional[uuid.UUID] = None,
):
    """record experiment bill"""
    try:
        billing_system = getattr(app_state, "billing_system", None)
        if billing_system and "record_experiment_bill" in billing_system:
            await billing_system["record_experiment_bill"](
                db, tenant_id, exp_id, llm_config_id
            )
    except Exception as e:
        logger.warning(f"Failed to record experiment bill: {e}")
