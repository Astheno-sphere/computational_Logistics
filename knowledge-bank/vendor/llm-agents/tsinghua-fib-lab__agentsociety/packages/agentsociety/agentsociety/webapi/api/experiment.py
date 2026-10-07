from collections import defaultdict
import csv
import io
import json
import logging
import uuid
import zipfile
from typing import List, cast, Dict, Tuple

import yaml
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import ApiResponseWrapper
from ..models.agent import (
    agent_dialog,
    agent_profile,
    agent_status,
    agent_survey,
    global_prompt,
)
from ..models.experiment import ApiExperiment, ApiTime, Experiment, ExperimentStatus
from ..models.metric import ApiMetric, metric
from .const import DEMO_USER_ID
from .timezone import ensure_timezone_aware

__all__ = ["router"]

router = APIRouter(tags=["experiments"])


async def _find_started_experiment_by_id(
    request: Request, db: AsyncSession, exp_id: uuid.UUID
) -> Experiment:
    """Find an experiment by ID and check if it has started"""
    tenant_id = await request.app.state.get_tenant_id(request)
    stmt = select(Experiment).where(
        Experiment.tenant_id.in_([tenant_id, "", "default"]), Experiment.id == exp_id
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found"
        )
    exp: Experiment = row[0]
    if ExperimentStatus(exp.status) == ExperimentStatus.NOT_STARTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Experiment not running"
        )
    return exp


@router.get("/experiments")
async def list_experiments(
    request: Request,
) -> ApiResponseWrapper[List[ApiExperiment]]:
    """List all experiments"""
    tenant_id = await request.app.state.get_tenant_id(request)
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = (
            select(Experiment)
            .where(Experiment.tenant_id.in_([tenant_id, "", "default"]))
            .order_by(Experiment.created_at.desc())
        )
        results = await db.execute(stmt)
        db_experiments = [row[0] for row in results.all() if len(row) > 0]

        # 处理时区
        for experiment in db_experiments:
            experiment.created_at = ensure_timezone_aware(experiment.created_at)
            experiment.updated_at = ensure_timezone_aware(experiment.updated_at)

        experiments = cast(List[ApiExperiment], db_experiments)
        return ApiResponseWrapper(data=experiments)


@router.get("/experiments/{exp_id}")
async def get_experiment_by_id(
    request: Request,
    exp_id: uuid.UUID,
) -> ApiResponseWrapper[ApiExperiment]:
    """Get experiment by ID"""

    tenant_id = await request.app.state.get_tenant_id(request)
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = select(Experiment).where(
            Experiment.tenant_id.in_([tenant_id, "", "default"]), Experiment.id == exp_id
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row or len(row) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found"
            )
        exp = row[0]
        # 处理时区
        exp.created_at = ensure_timezone_aware(exp.created_at)
        exp.updated_at = ensure_timezone_aware(exp.updated_at)
        return ApiResponseWrapper(data=exp)


@router.get("/experiments/{exp_id}/timeline")
async def get_experiment_status_timeline_by_id(
    request: Request,
    exp_id: uuid.UUID,
) -> ApiResponseWrapper[List[ApiTime]]:
    """Get experiment status timeline by ID"""

    tenant_id = await request.app.state.get_tenant_id(request)
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = select(Experiment).where(
            Experiment.tenant_id.in_([tenant_id, "", "default"]), Experiment.id == exp_id
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row or len(row) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found"
            )
        experiment: Experiment = row[0]
        # Check if the experiment has started
        if ExperimentStatus(experiment.status) == ExperimentStatus.NOT_STARTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment has not started yet",
            )

        # Get timeline from agent status table
        table_name = experiment.agent_status_tablename

        # the table_name is safe to use in the query
        # it is generated from the experiment id
        query = text(
            f"""
            SELECT day, t 
            FROM {table_name} 
            GROUP BY day, t 
            ORDER BY day, t
        """
        )

        results = (await db.execute(query)).all()
        timeline = [ApiTime(day=int(row[0]), t=float(row[1])) for row in results]

        return ApiResponseWrapper(data=timeline)


@router.delete("/experiments/{exp_id}", status_code=status.HTTP_200_OK)
async def delete_experiment_by_id(
    request: Request,
    exp_id: uuid.UUID,
):
    """Delete experiment by ID"""

    if request.app.state.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Server is in read-only mode"
        )
    tenant_id = await request.app.state.get_tenant_id(request)
    if tenant_id == DEMO_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo user is not allowed to delete experiments",
        )

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        try:
            # Start transaction
            async with db.begin():
                stmt = select(Experiment).where(
                    Experiment.tenant_id == tenant_id, Experiment.id == exp_id
                )
                result = await db.execute(stmt)
                row = result.first()
                if not row or len(row) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Experiment not found",
                    )
                experiment: Experiment = row[0]

                # Get all table names that need to be deleted
                table_names = [
                    experiment.agent_profile_tablename,
                    experiment.agent_status_tablename,
                    experiment.agent_dialog_tablename,
                    experiment.agent_survey_tablename,
                    experiment.global_prompt_tablename,
                    experiment.pending_dialog_tablename,
                    experiment.pending_survey_tablename,
                    experiment.metric_tablename,
                ]

                # Delete related tables
                for table_name in table_names:
                    try:
                        query = text(f"DROP TABLE IF EXISTS {table_name}")
                        await db.execute(query)
                    except Exception as e:
                        logging.error(f"Error dropping table {table_name}: {str(e)}")
                        # Continue execution without interruption

                # Delete experiment record
                await db.delete(experiment)

            # Transaction will be committed automatically

            return ApiResponseWrapper(
                data={"message": "Experiment deleted successfully"}
            )

        except Exception as e:
            logging.error(f"Error deleting experiment: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete experiment: {str(e)}",
            )


async def get_experiment_metrics_by_id(
    request: Request,
    db: AsyncSession,
    exp_id: uuid.UUID,
) -> Tuple[bool, Dict[str, List[ApiMetric]]]:
    """Get metrics for an experiment by ID

    Args:
        request: FastAPI request
        db: Database session
        exp_id: Experiment ID

    Returns:
        Tuple containing:
        - bool: Whether metrics were found
        - Dict[str, List[ApiMetric]]: Metrics data aggregated by key
    """

    experiment = await _find_started_experiment_by_id(request, db, exp_id)

    # Get metrics from the metric table
    table_name = experiment.metric_tablename
    
    # Execute query to get metrics data
    query = text(
        f"""
        SELECT key, value, step
        FROM {table_name}
        ORDER BY step
        """
    )
    results = await db.execute(query)
    rows = results.all()

    if not rows:
        return False, {}

    # Aggregate metrics by key
    metrics_by_key: Dict[str, List[ApiMetric]] = defaultdict(list)
    for row in rows:
        api_metric = ApiMetric(
            key=row[0],
            value=float(row[1]),
            step=int(row[2]),
        )
        metrics_by_key[row[0]].append(api_metric)

    return True, metrics_by_key


def serialize_metrics(
    metrics_by_key: Dict[str, List[ApiMetric]],
) -> Dict[str, List[dict]]:
    """Serialize metrics data for JSON output

    Args:
        metrics_by_key: Metrics data aggregated by key

    Returns:
        Dict with serialized metrics data
    """
    return {
        key: [metric.model_dump() for metric in metrics]
        for key, metrics in metrics_by_key.items()
    }


@router.get("/experiments/{exp_id}/metrics")
async def get_experiment_metrics(
    request: Request,
    exp_id: uuid.UUID,
) -> ApiResponseWrapper[Dict[str, List[ApiMetric]]]:
    """Get all metrics for an experiment, aggregated by metric key"""

    tenant_id = await request.app.state.get_tenant_id(request)
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)

        # First verify the experiment exists
        stmt = select(Experiment).where(
            Experiment.tenant_id == tenant_id, Experiment.id == exp_id
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found"
            )

        _, metrics_by_key = await get_experiment_metrics_by_id(request, db, exp_id)
        return ApiResponseWrapper(data=metrics_by_key)


@router.post("/experiments/{exp_id}/export")
async def export_experiment_data(
    request: Request,
    exp_id: uuid.UUID,
) -> StreamingResponse:
    """Export experiment data as a zip file containing YAML and CSV files"""

    tenant_id = await request.app.state.get_tenant_id(request)
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)

        # Get experiment info
        stmt = select(Experiment).where(
            Experiment.tenant_id == tenant_id, Experiment.id == exp_id
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found"
            )
        experiment: Experiment = row

        # Create in-memory zip file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Export experiment info as YAML
            exp_dict = experiment.to_dict()
            yaml_content = yaml.dump(exp_dict, allow_unicode=True)
            zip_file.writestr("experiment.yaml", yaml_content)

            # Export metrics data as JSON
            found, metrics_by_key = await get_experiment_metrics_by_id(request, db, exp_id)
            if found:
                serialized_metrics = serialize_metrics(metrics_by_key)
                metrics_json = json.dumps(serialized_metrics, indent=2)
                zip_file.writestr("metrics.json", metrics_json)

            # Export artifacts data
            fs_client = request.app.state.env.fs_client
            artifacts_path = f"exps/{tenant_id}/{exp_id}/artifacts.json"
            artifacts_data = fs_client.download(artifacts_path)
            if artifacts_data:
                zip_file.writestr("artifacts.json", artifacts_data)

            # get all tables
            tables = {
                "agent_profile": agent_profile(experiment.agent_profile_tablename),
                "agent_status": agent_status(experiment.agent_status_tablename),
                "agent_survey": agent_survey(experiment.agent_survey_tablename),
                "agent_dialog": agent_dialog(experiment.agent_dialog_tablename),
                "global_prompt": global_prompt(experiment.global_prompt_tablename),
                "metric": metric(experiment.metric_tablename),
            }

            for table_name, (db_table, columns) in tables.items():
                query = select(db_table)
                results = await db.execute(query)
                rows = results.all()

                if rows:
                    # create csv file
                    output = io.StringIO()
                    writer = csv.writer(output)
                    # write header
                    writer.writerow([col for col in columns])
                    # write data
                    writer.writerows(rows)

                    zip_file.writestr(f"{table_name}.csv", output.getvalue())
                    output.close()

        # prepare response
        zip_buffer.seek(0)
        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=experiment_{exp_id}_export.zip"
            },
        )


@router.post("/experiments/{exp_id}/artifacts")
async def export_experiment_artifacts(
    request: Request,
    exp_id: uuid.UUID,
) -> StreamingResponse:
    """Export experiment artifacts as a JSON file"""

    tenant_id = await request.app.state.get_tenant_id(request)
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)

        # Get experiment info
        stmt = select(Experiment).where(
            Experiment.tenant_id == tenant_id, Experiment.id == exp_id
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found"
            )

        # Get artifacts from S3
        fs_client = request.app.state.env.fs_client
        artifacts_path = f"exps/{tenant_id}/{exp_id}/artifacts.json"
        artifacts_data = fs_client.download(artifacts_path)

        if not artifacts_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Artifacts not found"
            )

        return StreamingResponse(
            iter([artifacts_data]),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=experiment_{exp_id}_artifacts.json"
            },
        )
