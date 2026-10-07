from typing import List, Optional, cast
from fastapi import APIRouter, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...webapi.models import ApiResponseWrapper, ApiPaginatedResponseWrapper
from .models import Account, ApiAccount, Bill, ApiBill
from ...webapi.api.timezone import ensure_timezone_aware

__all__ = ["router"]

router = APIRouter(tags=["billing"])


@router.get("/account")
async def get_account(
    request: Request,
) -> ApiResponseWrapper[ApiAccount]:
    """Get account information for the current tenant. If account doesn't exist, create one."""
    tenant_id = await request.app.state.get_tenant_id(request)
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = select(Account).where(Account.tenant_id == tenant_id)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            # Create new account if not exists
            account = Account(tenant_id=tenant_id)
            db.add(account)
            await db.commit()
            await db.refresh(account)

        account.created_at = ensure_timezone_aware(account.created_at)
        account.updated_at = ensure_timezone_aware(account.updated_at)

        return ApiResponseWrapper(data=account)


@router.get("/bills")
async def list_bills(
    request: Request,
    item: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> ApiPaginatedResponseWrapper[ApiBill]:
    """List all bills for the current tenant with optional filtering"""
    tenant_id = await request.app.state.get_tenant_id(request)
    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)

        # Build base query
        base_query = select(Bill).where(Bill.tenant_id == tenant_id)
        if item:
            base_query = base_query.where(Bill.item == item)

        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        # Get paginated results
        stmt = base_query.order_by(Bill.created_at.desc())
        stmt = stmt.offset(skip).limit(limit)
        results = await db.execute(stmt)
        bills = cast(List[ApiBill], results.scalars().all())

        # 处理时区
        for bill in bills:
            bill.created_at = ensure_timezone_aware(bill.created_at)

        return ApiPaginatedResponseWrapper(total=total, data=bills)
