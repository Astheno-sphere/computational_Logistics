"""
Commercial Billing System

Provides unified billing functionality for the commercial version.
"""

from typing import Dict, Any

def get_billing_system(config: Dict[str, Any]):
    """Get billing system configuration"""
    if not config.get("enabled", False):
        return None
    
    from .api import router as billing_router
    from .calculator import compute_bill, check_balance, record_experiment_bill
    
    return {
        "router": billing_router,
        "compute_bill": compute_bill,
        "check_balance": check_balance,
        "record_experiment_bill": record_experiment_bill,
        "currency": config.get("currency", "CNY"),
        "rates": config.get("rates", {})
    } 