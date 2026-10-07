import csv
import io
import json
import uuid
import os
from typing import Any, Dict, List, Optional, cast

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...configs import EnvConfig
from ..models import ApiResponseWrapper
from ..models.agent_profiles import AgentProfile, ApiAgentProfile
from .const import DEMO_USER_ID
from .timezone import ensure_timezone_aware

__all__ = ["router"]

router = APIRouter(tags=["agent_profiles"])


class SaveProfileRequest(BaseModel):
    """Request model for saving agent profiles"""

    name: str = Field(..., description="Name for the saved profile")
    description: Optional[str] = Field(
        None, description="Description for the saved profile"
    )
    agent_type: str = Field(..., description="Type of agent (citizen, firm, etc.)")
    file_path: str = Field(..., description="Path to the temporary profile file in S3")


@router.get("/agent-profiles")
async def list_agent_profiles(
    request: Request,
) -> ApiResponseWrapper[List[ApiAgentProfile]]:
    """List all agent profiles for the current tenant"""

    tenant_id = await request.app.state.get_tenant_id(request)

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)

        # Query profiles from database
        stmt = (
            select(AgentProfile)
            .where(AgentProfile.tenant_id.in_([tenant_id, "", "default"]))
            .order_by(AgentProfile.created_at.desc())
        )

        result = await db.execute(stmt)
        profiles = result.scalars().all()
        for profile in profiles:
            profile.created_at = ensure_timezone_aware(profile.created_at)
            profile.updated_at = ensure_timezone_aware(profile.updated_at)

        # Convert to ApiAgentProfile list
        profile_list = [ApiAgentProfile.model_validate(profile) for profile in profiles]
        return ApiResponseWrapper(data=profile_list)


@router.get("/agent-profiles/{profile_id}")
async def get_agent_profile(
    request: Request,
    profile_id: uuid.UUID,
) -> ApiResponseWrapper[List[Dict[str, Any]]]:
    """Get agent profile data by profile ID"""

    tenant_id = await request.app.state.get_tenant_id(request)

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)

        # Find the profile
        stmt = select(AgentProfile).where(
            AgentProfile.tenant_id.in_([tenant_id, "", "default"]), AgentProfile.id == profile_id
        )
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found"
            )

        profile.created_at = ensure_timezone_aware(profile.created_at)
        profile.updated_at = ensure_timezone_aware(profile.updated_at)

        # Get the file from S3
        env: EnvConfig = request.app.state.env
        fs_client = env.fs_client
        try:
            content = fs_client.download(profile.file_path)
            data = json.loads(content)
            return ApiResponseWrapper(data=data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving profile data: {str(e)}",
            )


@router.delete("/agent-profiles/{profile_id}")
async def delete_agent_profile(
    request: Request,
    profile_id: uuid.UUID,
) -> ApiResponseWrapper[Dict[str, str]]:
    """Delete a saved agent profile"""
    if request.app.state.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Server is in read-only mode"
        )

    tenant_id = await request.app.state.get_tenant_id(request)

    if tenant_id == DEMO_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo user is not allowed to delete profiles",
        )

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)

        # Find the profile
        stmt = select(AgentProfile).where(
            AgentProfile.tenant_id == tenant_id, AgentProfile.id == profile_id
        )
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found"
            )

        # Delete the file from webui storage
        env: EnvConfig = request.app.state.env
        fs_client = env.fs_client
        try:
            fs_client.delete(profile.file_path)
        except Exception as e:
            # Log error but continue with database deletion
            print(f"Error deleting file from S3: {str(e)}")

        # Delete from database
        stmt = delete(AgentProfile).where(
            AgentProfile.tenant_id == tenant_id, AgentProfile.id == profile_id
        )
        await db.execute(stmt)
        await db.commit()

        return ApiResponseWrapper(data={"message": "Profile deleted successfully"})


def validate_and_process_ids(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and process ID fields in the data.
    Handles three cases:
    1. All records have IDs
    2. No records have IDs
    3. Some records have IDs while others don't

    Args:
        data: List of dictionaries containing agent profile data

    Returns:
        List of dictionaries with validated and processed IDs

    Raises:
        HTTPException: If invalid or duplicate IDs are found
    """
    # Collect existing IDs
    existing_ids = set()
    max_id = 0

    # First pass: validate existing IDs
    for record in data:
        if "id" in record:
            id_value = record["id"]
            # Check if ID is an integer
            if not isinstance(id_value, (int, str)) or (
                isinstance(id_value, str) and not id_value.isdigit()
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ID must be an integer",
                )

            id_value = int(id_value)
            if id_value in existing_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate ID found: {id_value}",
                )
            existing_ids.add(id_value)
            max_id = max(max_id, id_value)

    # Second pass: assign new IDs to records without IDs
    next_id = max_id + 1
    for record in data:
        if "id" not in record:
            # Find next available ID
            while next_id in existing_ids:
                next_id += 1
            record["id"] = next_id
            existing_ids.add(next_id)
            next_id += 1

    return data


@router.post("/agent-profiles/upload")
async def upload_agent_profile(
    request: Request,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
) -> ApiResponseWrapper[ApiAgentProfile]:
    """Upload an agent profile file and save it to the database."""
    if request.app.state.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Server is in read-only mode"
        )

    tenant_id = await request.app.state.get_tenant_id(request)

    if tenant_id == DEMO_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo user is not allowed to upload profiles",
        )

    env: EnvConfig = request.app.state.env
    fs_client = env.fs_client

    # Read file content
    content = await file.read()

    # Parse file based on extension
    filename = file.filename
    if filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required"
        )
    file_ext = filename.split(".")[-1].lower()

    # Validate and parse the file
    if file_ext == "json":
        data = json.loads(content)
        if not isinstance(data, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="JSON data must be a list of objects",
            )
        data = validate_and_process_ids(data)
        record_count = len(data)
    elif file_ext == "csv":
        # Parse CSV
        csv_content = content.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        data = list(csv_reader)
        data = validate_and_process_ids(data)
        record_count = len(data)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a CSV or JSON file.",
        )

    # Generate a unique ID for the file
    file_id = str(uuid.uuid4())
    s3_path = (
        f"agent_profiles/{tenant_id}/{file_id}.json"
        if tenant_id
        else f"agent_profiles/{file_id}.json"
    )

    # Convert to JSON and upload to S3
    data_json = json.dumps(data)
    fs_client.upload(data_json.encode("utf-8"), s3_path)

    # Use provided name or filename
    profile_name = name if name else os.path.splitext(filename)[0]
    profile_description = description if description else None

    # Save metadata to database
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        # Create new profile data entry
        profile_id = uuid.uuid4()
        new_profile = AgentProfile(
            tenant_id=tenant_id,
            id=profile_id,
            name=profile_name,
            description=profile_description,
            agent_type="",  # Default value
            file_path=s3_path,
            record_count=record_count,
        )

        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)  # Refresh to get database-generated values

        # Convert to ApiAgentProfile
        new_profile.created_at = ensure_timezone_aware(new_profile.created_at)
        new_profile.updated_at = ensure_timezone_aware(new_profile.updated_at)
        api_profile = ApiAgentProfile.model_validate(new_profile)
        return ApiResponseWrapper(data=api_profile)
