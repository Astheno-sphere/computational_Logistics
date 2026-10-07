import uvicorn
import argparse
import os
import shutil
from backup_helper import backup_file_if_exists
from loguru import logger
from helper import setup_logging
from settings import settings

args = argparse.ArgumentParser()

args.add_argument("--config", type=str, default="", help="Path to the configuration file")

if __name__ == "__main__":
    args = args.parse_args()
    if args.config:
        os.environ["APP_CONFIG_PATH"] = args.config
        settings = settings.force_reload()
        workdir = settings.workdir
        if not workdir.exists():
            logger.warning(f"Work directory {workdir} does not exist. Creating it.")
            workdir.mkdir(parents=True, exist_ok=True)

    # Backup important files
    backup_file_if_exists(settings.app.history_file_v2)

    # Copy the configuration file to the work directory
    if args.config and os.path.exists(args.config):
        shutil.copy(args.config, settings.workdir / "config.yaml")

    # Set up logging
    setup_logging(settings)

    logger.info(f"---- Starting server ... ----")

    uvicorn.run(
        "handle:app", 
        host=settings.server.http_host, 
        port=settings.server.http_port, 
        http="h11", 
        reload=False,
        reload_delay=0.25,
        timeout_keep_alive=5,
    )
