import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ..configs import EnvConfig
from .api import api_router
from .models._base import Base

__all__ = ["create_app", "empty_get_tenant_id"]

_script_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_script_dir)

logger = logging.getLogger(__name__)


async def empty_get_tenant_id(_: Request) -> str:
    return "default"


def _try_load_commercial_features(
    app: FastAPI, commercial: Dict[str, Any],
) -> None:
    """try to load commercial features"""
    try:
        from ..commercial import is_available
        if not is_available():
            logger.debug("Commercial features not available, using open source version")
            return

        logger.info("Loading commercial features...")
        # Authentication
        auth_config = commercial.get("auth", {})
        if auth_config.get("enabled", False):
            from ..commercial import get_auth_provider

            auth_provider = get_auth_provider(auth_config)
            if auth_provider:
                app.state.casdoor = auth_provider["casdoor"]
                app.state.get_tenant_id = auth_provider["auth_function"]
                app.include_router(auth_provider["router"], prefix="/api")
                logger.info("Commercial authentication enabled")

        # Executor
        executor_config = commercial.get("executor", {})
        k8s_config = executor_config.get("kubernetes", {})
        if k8s_config.get("enabled", False):
            from ..commercial import get_kubernetes_executor

            k8s_executor = get_kubernetes_executor(k8s_config)
            if k8s_executor:
                app.state.executor = k8s_executor
                logger.info("Commercial Kubernetes executor enabled")

        # Billing
        billing_config = commercial.get("billing", {})
        if billing_config.get("enabled", False):
            from ..commercial import get_billing_system

            billing_system = get_billing_system(billing_config)
            if billing_system:
                app.state.billing_system = billing_system
                app.include_router(billing_system["router"], prefix="/api")
                logger.info("Commercial billing system enabled")

    except ImportError as e:
        logger.info(f"Commercial features not available: {e}")
    except Exception as e:
        logger.warning(f"Failed to load commercial features: {e}")


def create_app(
    db_dsn: str,
    read_only: bool,
    env: EnvConfig,
    more_state: Dict[str, Any] = {},
    commercial: Dict[str, Any] = {},
):

    # https://fastapi.tiangolo.com/advanced/events/#use-case
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Init database when app starts
        engine = create_async_engine(db_dsn)
        session_factory = async_sessionmaker(engine)
        # test the postgres connection
        try:
            async with engine.connect() as conn:
                pass
        except Exception as e:
            raise Exception(
                f"Failed to connect to database: {e}. Please check the connection string: {db_dsn}"
            )
        # save session_factory to app state
        app.state.get_db = session_factory

        # save read_only to app state
        app.state.read_only = read_only
        # save env to app state
        app.state.env = env

        # Hook to get tenant_id
        if not hasattr(app.state, "get_tenant_id"):
            app.state.get_tenant_id = empty_get_tenant_id

        # save more_state to app state
        for k, v in more_state.items():
            if not hasattr(app.state, k):
                setattr(app.state, k, v)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield

    # create FastAPI app
    app = FastAPI(
        title="AgentSociety WebUI API",
        lifespan=lifespan,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # try to load commercial features
    _try_load_commercial_features(app, commercial)

    # add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://moss.fiblab.net"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # https://stackoverflow.com/questions/75958222/can-i-return-400-error-instead-of-422-error
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(ValidationError)
    async def validation_pydantic_exception_handler(
        request: Request, exc: ValidationError
    ):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": jsonable_encoder(exc.errors())},
        )

    app.include_router(api_router)

    # serve frontend files
    frontend_path = Path(_parent_dir) / "_dist"
    app.mount("/", StaticFiles(directory=frontend_path, html=True))

    # 404 handler, redirect all 404 to index.html except /api
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException):
        if not request.url.path.startswith("/api"):
            return FileResponse(frontend_path / "index.html")
        # change the exception to JSONResponse
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": jsonable_encoder(exc.detail)},
        )

    return app
