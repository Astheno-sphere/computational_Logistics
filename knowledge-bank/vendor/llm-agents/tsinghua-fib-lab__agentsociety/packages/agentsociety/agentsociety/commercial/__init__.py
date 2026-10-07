"""
AgentSociety Commercial Features

This package contains commercial-only features including:
- Casdoor authentication
- Kubernetes executor
- Billing system
- Payment integration

When this package is removed or not available, the system will
automatically fall back to open-source alternatives.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

def is_available() -> bool:
    """Check if commercial features are available"""
    try:
        # Try to import a core commercial module to verify availability
        from . import auth
        _ = auth
        return True
    except ImportError:
        return False

def get_auth_provider(config: Dict[str, Any]):
    """Get commercial authentication provider"""
    if not is_available():
        return None
    
    try:
        from .auth.casdoor import get_casdoor_auth
        return get_casdoor_auth(config)
    except ImportError as e:
        logger.warning(f"Failed to load commercial auth provider: {e}")
        return None

def get_kubernetes_executor(config: Dict[str, Any]):
    """Get commercial Kubernetes executor"""
    if not is_available():
        return None
    
    try:
        from .executor import get_kubernetes_executor
        return get_kubernetes_executor(config)
    except ImportError as e:
        logger.warning(f"Failed to load commercial Kubernetes executor: {e}")
        return None

def get_billing_system(config: Dict[str, Any]):
    """Get commercial billing system"""
    if not is_available():
        return None
    
    try:
        from .billing.system import get_billing_system
        return get_billing_system(config)
    except ImportError as e:
        logger.warning(f"Failed to load commercial billing system: {e}")
        return None 