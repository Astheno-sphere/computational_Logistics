import base64
import importlib.metadata
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import click
import yaml
from pydantic import BaseModel, Field

from ..cityagent import SocietyAgent

version_string_of_agentsociety = importlib.metadata.version("agentsociety")

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
PARAM_DECLS_VERSION = ("-V", "--version")


def load_config(
    config_path: Optional[str] = None, config_base64: Optional[str] = None
) -> Dict[Any, Any]:
    """Load configuration file, supports JSON and YAML formats, as well as base64 encoded config"""
    if config_base64:
        # Decode base64 config
        config_str = base64.b64decode(config_base64).decode("utf-8")
        # For base64 encoded config, try both JSON and YAML parsing
        try:
            # Try to parse as JSON
            return json.loads(config_str)
        except json.JSONDecodeError:
            try:
                # Try to parse as YAML
                return yaml.safe_load(config_str)
            except yaml.YAMLError as e:
                raise click.BadParameter(f"Failed to parse base64 config: {e}")
    elif config_path:
        # Determine format based on file extension
        path = Path(config_path)
        if not path.exists():
            raise click.BadParameter(f"Config file {config_path} does not exist")
        file_ext = path.suffix.lower()
        if file_ext in [".json"]:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                raise click.BadParameter(f"Failed to parse JSON config file: {e}")
        elif file_ext in [".yaml", ".yml"]:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise click.BadParameter(f"Failed to parse YAML config file: {e}")
        else:
            raise click.BadParameter(f"Unsupported config file format: {file_ext}")
    else:
        raise click.BadParameter("No config file or base64 encoded config provided")


def common_options(f):
    """Common configuration options decorator"""
    f = click.option("--config", "-c", help="Path to config file (.json, .yml, .yaml)")(
        f
    )
    f = click.option(
        "--config-base64", help="Base64 encoded config with JSON or YAML format"
    )(f)
    return f


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=version_string_of_agentsociety, prog_name="AgentSociety")
def cli():
    """AgentSociety CLI tool"""
    pass


@cli.command()
@common_options
def ui(config: Optional[str], config_base64: Optional[str]):
    """Launch AgentSociety GUI"""
    if config is None and config_base64 is None:
        config_data = {}
    else:
        config_data = load_config(config, config_base64)

    import uvicorn

    from ..configs import EnvConfig
    from ..logger import get_logger, set_logger_level
    from ..webapi.app import create_app
    from ..executor import ProcessExecutor

    class WebUIConfig(BaseModel):
        addr: str = Field(default="127.0.0.1:8080")
        callback_url: str = ""
        env: EnvConfig = Field(default_factory=lambda: EnvConfig.model_validate({
            "db": {
                "enabled": True,
            }
        }))
        read_only: bool = Field(default=False)
        debug: bool = Field(default=False)
        logging_level: str = Field(default="INFO")
        commercial: Dict[str, Any] = {}

    async def _main():
        c = WebUIConfig.model_validate(config_data)
        set_logger_level(c.logging_level.upper())
        get_logger().info("Launching AgentSociety WebUI")
        get_logger().debug(f"WebUI config: {c}")

        db_dsn = c.env.db.get_dsn(Path(c.env.home_dir) / "sqlite.db")

        # default executor
        executor = ProcessExecutor(c.env.home_dir)

        more_state: Dict[str, Any] = {
            "callback_url": c.callback_url,
            "executor": executor,
        }

        app = create_app(
            db_dsn=db_dsn,
            read_only=c.read_only,
            env=c.env,
            more_state=more_state,
            commercial=c.commercial,
        )

        # Start server
        url = urlsplit("//" + c.addr)
        host, port = url.hostname, url.port
        if host is None or host == "" or host == "localhost":
            host = "127.0.0.1"
        if port is None:
            port = 8080
        log_level = "debug" if c.debug else "info"
        get_logger().info("Starting server at %s:%s", host, port)
        config = uvicorn.Config(app, host=host, port=port, log_level=log_level)
        server = uvicorn.Server(config)
        await server.serve()

    import asyncio

    asyncio.run(_main())


@cli.command()
@common_options
@click.option("--type", default="simulation", help="Specify the type of the simulation", type=click.Choice(["simulation", "individual"]))
def check(config: str, config_base64: str, type: str):
    """Pre-check the config"""
    from pathlib import Path

    config_dict = load_config(config, config_base64)

    if type == "simulation":
        from ..configs import Config

        c = Config.model_validate(config_dict)
    elif type == "individual":
        from ..configs import IndividualConfig

        c = IndividualConfig.model_validate(config_dict)
    else:
        raise ValueError(f"Invalid type: {type}")

    click.echo(f"Config format check. {click.style('Passed.', fg='green')}")

    # =================
    # check the connection to the database server using SQLAlchemy
    # =================
    if c.env.db.enabled:
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import OperationalError

        try:
            # Get the DSN for the database
            sqlite_path = Path(c.env.home_dir) / "sqlite.db"
            dsn = c.env.db.get_dsn(sqlite_path)

            # Convert async DSN to sync DSN for testing
            if dsn.startswith("postgresql+asyncpg://"):
                sync_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
            elif dsn.startswith("sqlite+aiosqlite://"):
                sync_dsn = dsn.replace("sqlite+aiosqlite://", "sqlite://", 1)
            else:
                sync_dsn = dsn

            # Create sync engine for testing
            engine = create_engine(sync_dsn)

            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            click.echo(f"Database connection check. {click.style('Passed.', fg='green')}")

        except OperationalError as e:
            click.echo(f"Database connection check. {click.style('Failed:', fg='red')} {e}")
            if c.env.db.db_type == "postgresql":
                click.echo(
                    f"Explanation: Please check the `pg_dsn` (value={c.env.db.pg_dsn}) of the PostgreSQL server. The format of `pg_dsn` is `postgresql://<username>:<password>@<host>:<port>/<database_name>`. The item wrapped in `<>` should be replaced with the actual values."
                )
                error_msg = str(e)
                if "password authentication failed" in error_msg:
                    click.echo(
                        "Explanation: The username or password of the PostgreSQL server is incorrect."
                    )
                elif "Temporary failure in name resolution" in error_msg:
                    click.echo(
                        "Explanation: The host of the PostgreSQL server is invalid. Maybe you should use `localhost` or `127.0.0.1` instead if you are running the simulation on a single machine (used to run docker compose)."
                    )
                elif "Connection refused" in error_msg:
                    click.echo(
                        "Explanation: The host or port of the PostgreSQL server is incorrect."
                    )
            elif c.env.db.db_type == "sqlite":
                click.echo(
                    "Explanation: SQLite database connection failed. Please check the file path and permissions."
                )
        except Exception as e:
            click.echo(f"Database connection check. {click.style('Failed:', fg='red')} {e}")
    else:
        click.echo(f"Database is disabled. {click.style('Skipped.', fg='yellow')}")

    # =================
    # check whether the map file exists
    # =================
    if type == "simulation":
        if not os.path.exists(c.map.file_path): # type: ignore
            click.echo(
                f"Map file {c.map.file_path} does not exist. {click.style('Failed.', fg='red')}" # type: ignore
            )
            return
        click.echo(f"Map file. {click.style('Passed.', fg='green')}")


@cli.command()
@common_options
@click.option("--tenant-id", default="default", help="Specify tenant ID")
@click.option("--callback-url", default="", help="Specify callback URL (POST)")
@click.option("--type", default="simulation", help="Specify the type of the simulation", type=click.Choice(["simulation", "individual"]))
def run(
    config: str,
    config_base64: str,
    tenant_id: str,
    callback_url: str,
    type: str,
):
    """Run the simulation"""
    config_dict = load_config(config, config_base64)

    import requests
    from ..configs import Config, IndividualConfig
    from ..simulation import AgentSociety
    from ..cityagent import default
    from ..configs.exp import AgentFilterConfig

    if type == "simulation":
        c = Config.model_validate(config_dict)
        # Check if we need to import community modules
        need_community = False
        if c.agents.citizens:
            for citizen in c.agents.citizens:
                if isinstance(citizen.agent_class, str):
                    need_community = True
                    break
                # go to check blocks
                if citizen.blocks is not None:
                    for block in citizen.blocks.keys():
                        if isinstance(block, str):
                            need_community = True
                            break

        if c.agents.supervisor is not None and isinstance(
            c.agents.supervisor.agent_class, str
        ):
            need_community = True

        if c.exp.workflow:
            for step in c.exp.workflow:
                if step.func is not None and isinstance(step.func, str):
                    need_community = True
                    break
                # Check if target_agent is AgentFilterConfig with agent_class
                if (step.target_agent is not None and 
                    isinstance(step.target_agent, AgentFilterConfig) and 
                    step.target_agent.agent_class is not None):
                    need_community = True
                    break

        if need_community:
            try:
                from agentsociety_community.agents import citizens, supervisors
                from agentsociety_community.blocks import citizens as citizen_blocks
                from agentsociety_community.workflows import functions as workflow_functions

                # get the mapping of the agent class
                workflow_function_map = workflow_functions.get_type_to_cls_dict()
                citizens_class_map = citizens.get_type_to_cls_dict()
                citizen_blocks_class_map = citizen_blocks.get_type_to_cls_dict()
                supervisors_class_map = supervisors.get_type_to_cls_dict()

                # process the agent_class in citizens
                for citizen in c.agents.citizens:
                    if isinstance(citizen.agent_class, str):
                        if citizen.agent_class == "SocietyAgent" or citizen.agent_class == "citizen":
                            citizen.agent_class = 'citizen'
                        else:
                            citizen.agent_class = citizens_class_map[citizen.agent_class]()
                    if citizen.blocks is not None:
                        new_blocks = {}
                        for block_name, block_params in citizen.blocks.items():
                            if isinstance(block_name, str):
                                block_class = citizen_blocks_class_map[block_name]()
                                new_blocks[block_class] = block_params
                            else:
                                new_blocks[block_name] = block_params
                        citizen.blocks = new_blocks

                # process the agent_class in supervisor
                if c.agents.supervisor is not None and isinstance(
                    c.agents.supervisor.agent_class, str
                ):
                    c.agents.supervisor.agent_class = supervisors_class_map[
                        c.agents.supervisor.agent_class
                    ]()

                # process the func in workflow
                for step in c.exp.workflow:
                    if step.func is not None and isinstance(step.func, str):
                        # if func is a string, try to get the corresponding function from function_map
                        imported_func = workflow_function_map[step.func]()
                        step.func = imported_func
                    
                    # process the agent_class in target_agent if it's an AgentFilterConfig
                    if step.target_agent is not None and isinstance(step.target_agent, AgentFilterConfig):
                        agent_filter = step.target_agent
                        if agent_filter.agent_class is not None:
                            if isinstance(agent_filter.agent_class, list):
                                # Convert string list to class list
                                converted_classes = []
                                for agent_class_str in agent_filter.agent_class:
                                    if isinstance(agent_class_str, str):
                                        if agent_class_str == "citizen":
                                            converted_classes.append(SocietyAgent)
                                        elif agent_class_str == "SocietyAgent":
                                            converted_classes.append(SocietyAgent)
                                        elif agent_class_str in citizens_class_map:
                                            converted_classes.append(citizens_class_map[agent_class_str]())
                                        elif agent_class_str in supervisors_class_map:
                                            converted_classes.append(supervisors_class_map[agent_class_str]())
                                        else:
                                            # Keep as string if not found in maps
                                            converted_classes.append(agent_class_str)
                                    else:
                                        # Already a class, keep as is
                                        converted_classes.append(agent_class_str)
                                agent_filter.agent_class = tuple(converted_classes)  # type: ignore
                            elif isinstance(agent_filter.agent_class, str):
                                # Convert single string to class
                                if agent_filter.agent_class == "citizen":
                                    agent_filter.agent_class = tuple(SocietyAgent,) # type: ignore
                                elif agent_filter.agent_class == "SocietyAgent":
                                    # For default config compatible
                                    agent_filter.agent_class = tuple(SocietyAgent,) # type: ignore
                                if agent_filter.agent_class in citizens_class_map:
                                    agent_filter.agent_class = tuple(citizens_class_map[agent_filter.agent_class](),)  # type: ignore
                                elif agent_filter.agent_class in supervisors_class_map:
                                    agent_filter.agent_class = tuple(supervisors_class_map[agent_filter.agent_class](),)  # type: ignore
                                # If not found in maps, keep as string
            except ImportError as e:
                import traceback
                print(traceback.format_exc())
                print(
                    "agentsociety_community is not installed. Please install it with `pip install agentsociety-community`"
                )
                raise e
            
        c = default(c)
    elif type == "individual":
        c = IndividualConfig.model_validate(config_dict)
        # Check if we need to import community modules
        need_community = False
        if c.individual.agent_class is not None:
            if isinstance(c.individual.agent_class, str):
                need_community = True
            # go to check blocks
            if c.individual.blocks is not None:
                for block in c.individual.blocks.keys():
                    if isinstance(block, str):
                        need_community = True
                        break
        if need_community:
            try:
                from agentsociety_community.agents import citizens, supervisors
                from agentsociety_community.blocks import citizens as citizen_blocks
                from agentsociety_community.workflows import functions as workflow_functions

                # get the mapping of the agent class
                workflow_function_map = workflow_functions.get_type_to_cls_dict()
                citizens_class_map = citizens.get_type_to_cls_dict()
                citizen_blocks_class_map = citizen_blocks.get_type_to_cls_dict()
                supervisors_class_map = supervisors.get_type_to_cls_dict()

                # process the agent_class in solver
                if c.individual.agent_class is not None and isinstance(c.individual.agent_class, str):
                    c.individual.agent_class = citizens_class_map[c.individual.agent_class]()

                # process the blocks in solver
                if c.individual.blocks is not None:
                    new_blocks = {}
                    for block_name, block_params in c.individual.blocks.items():
                        if isinstance(block_name, str):
                            block_class = citizen_blocks_class_map[block_name]()
                            new_blocks[block_class] = block_params
                        else:
                            new_blocks[block_name] = block_params
                    c.individual.blocks = new_blocks
            except ImportError as e:
                import traceback

                print(traceback.format_exc())
                print(
                    "agentsociety_community is not installed. Please install it with `pip install agentsociety-community`"
                )
                raise e
    else:
        raise ValueError(f"Invalid type: {type}")

    society = AgentSociety.create(c, tenant_id)

    async def _run():
        try:
            await society.init()
            await society.run()
        finally:
            await society.close()
            if callback_url:
                requests.post(callback_url)

    import asyncio

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
