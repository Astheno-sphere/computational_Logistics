from fastapi import APIRouter

from .experiment import router as experiment_router
from .agent import router as agent_dialog_router
from .survey import router as survey_router
from .experiment_runner import router as experiment_runner_router
from .config import router as config_router
from .agent_profiles import router as agent_profiles_router
from .agent_template import router as agent_template_router

__all__ = ["api_router"]

# Main API router
api_router = APIRouter(prefix="/api")

# Include sub-routers
api_router.include_router(experiment_router)
api_router.include_router(agent_dialog_router)
api_router.include_router(survey_router)
api_router.include_router(experiment_runner_router)
api_router.include_router(config_router)
api_router.include_router(agent_profiles_router)
api_router.include_router(agent_template_router)