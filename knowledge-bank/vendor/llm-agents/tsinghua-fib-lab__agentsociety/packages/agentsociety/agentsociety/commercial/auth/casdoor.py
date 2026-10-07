"""
Casdoor Authentication Provider

Provides a unified interface for Casdoor authentication in the commercial version.
"""

from typing import Dict, Any
from .api.auth import Casdoor, CasdoorConfig, auth_bearer_token
from .api.login import router as login_router

def get_casdoor_auth(config: Dict[str, Any]):
    """Get Casdoor authentication configuration"""
    casdoor_config = config.get('casdoor', {})
    if not casdoor_config.get('enabled', False):
        return None
    
    return {
        'casdoor': Casdoor(CasdoorConfig.model_validate(casdoor_config)),
        'auth_function': auth_bearer_token,
        'router': login_router
    } 