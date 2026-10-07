"""
Billing Calculator

Provides billing calculation logic for experiments.
"""

import uuid
from decimal import Decimal, localcontext
from typing import Dict, Optional
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Bill, Account, ItemEnum, ExperimentBillConfig


async def compute_bill(
    db: AsyncSession, experiment, rates: Optional[Dict[str, float]] = None
) -> None:
    """计算并记录账单"""

    stmt = select(ExperimentBillConfig).where(
        ExperimentBillConfig.tenant_id == experiment.tenant_id,
        ExperimentBillConfig.exp_id == experiment.id,
    )
    experiment_bill_config = (await db.execute(stmt)).scalar_one_or_none()

    free_llm = experiment_bill_config is not None and experiment_bill_config.llm_config_id is None

    if rates is None:
        rates = {
            "llm_input_token": 3.0,  # 每百万token
            "llm_output_token": 3.0,  # 每百万token
            "runtime": 0.001,  # 每秒
        }

    tenant_id = experiment.tenant_id

    total_amount = 0
    if not free_llm:
        input_tokens = experiment.input_tokens / 1_000_000
        input_token_price = rates.get("llm_input_token", 3.0)
        output_tokens = experiment.output_tokens / 1_000_000
        output_token_price = rates.get("llm_output_token", 3.0)
        llm_input_amount = int(-input_tokens * input_token_price * 1_000_000) / 1_000_000
        llm_output_amount = int(-output_tokens * output_token_price * 1_000_000) / 1_000_000
        # 记录输入token账单
        stmt = insert(Bill).values(
            tenant_id=tenant_id,
            id=uuid.uuid4(),
            related_exp_id=experiment.id,
            item=ItemEnum.LLM_INPUT_TOKEN,
            amount=llm_input_amount,
            unit_price=input_token_price,
            quantity=input_tokens,
            description="",
        )
        await db.execute(stmt)
        total_amount += llm_input_amount

        # 记录输出token账单
        stmt = insert(Bill).values(
            tenant_id=tenant_id,
            id=uuid.uuid4(),
            related_exp_id=experiment.id,
            item=ItemEnum.LLM_OUTPUT_TOKEN,
            amount=llm_output_amount,
            unit_price=output_token_price,
            quantity=output_tokens,
            description="",
        )
        await db.execute(stmt)
        total_amount += llm_output_amount

    time = experiment.updated_at - experiment.created_at
    time_seconds = time.total_seconds()
    time_second_price = rates.get("runtime", 0.001)
    runtime_amount = int(-time_seconds * time_second_price * 1_000_000) / 1_000_000

    # 记录运行时间账单
    stmt = insert(Bill).values(
        tenant_id=tenant_id,
        id=uuid.uuid4(),
        related_exp_id=experiment.id,
        item=ItemEnum.RUNTIME,
        amount=runtime_amount,
        unit_price=time_second_price,
        quantity=time_seconds,
        description="",
    )
    await db.execute(stmt)
    total_amount += runtime_amount

    stmt = select(Account).where(Account.tenant_id == tenant_id)
    account = (await db.execute(stmt)).scalar_one_or_none()

    if account is None:
        # 创建账户
        account = Account(tenant_id=tenant_id, balance=Decimal(0))
        db.add(account)
        await db.flush()

    # 更新余额
    with localcontext() as ctx:
        ctx.prec = 6
        # Update account balance
        stmt = (
            update(Account)
            .where(Account.tenant_id == tenant_id)
            .values(
                balance=Account.balance
                + Decimal(
                    total_amount,
                ),
            )
        )
    await db.execute(stmt)
    await db.commit()


async def check_balance(tenant_id: str, db: AsyncSession) -> bool:
    """检查余额是否充足"""
    stmt = select(Account).where(Account.tenant_id == tenant_id)
    account = (await db.execute(stmt)).scalar_one_or_none()

    if account is None:
        return False

    return account.balance > 0


async def record_experiment_bill(
    db: AsyncSession,
    tenant_id: str,
    exp_id: uuid.UUID,
    llm_config_id: Optional[uuid.UUID] = None,
) -> None:
    """记录实验计费"""
    stmt = insert(ExperimentBillConfig).values(
        tenant_id=tenant_id,
        exp_id=exp_id,
        llm_config_id=llm_config_id,
    )
    await db.execute(stmt)
    await db.commit()
