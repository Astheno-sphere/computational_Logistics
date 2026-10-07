from datetime import datetime
from typing import Any
from decimal import Decimal
from sqlalchemy import Text, TIMESTAMP, DECIMAL, JSON
from sqlalchemy.ext.declarative import declarative_base

__all__ = ["Base", "TABLE_PREFIX", "MoneyDecimal"]


# Define decimal types for type annotations
class MoneyDecimal(Decimal):
    pass  # 6 decimal places for bills


# The base class of sqlalchemy models
Base = declarative_base(
    type_annotation_map={
        Any: JSON,
        str: Text,
        datetime: TIMESTAMP(timezone=True),
        Decimal: DECIMAL,
        MoneyDecimal: DECIMAL(precision=18, scale=6),
    }
)
"""
If the table needs to be initialized, use this base class.
"""

TABLE_PREFIX = "as_"
