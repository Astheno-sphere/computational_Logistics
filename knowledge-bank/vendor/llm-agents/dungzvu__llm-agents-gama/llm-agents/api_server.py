import uvicorn
import argparse
import os
from loguru import logger

args = argparse.ArgumentParser()
args.add_argument("--workdir", type=str, default=".", help="Working directory")

if __name__ == "__main__":
    args = args.parse_args()
    if args.workdir:
        os.makedirs(args.workdir, exist_ok=True)
        os.environ["APP_WORKDIR"] = args.workdir
        logger.info(f"Updated working directory to {args.workdir}")
    uvicorn.run("api:app", host="localhost", port=8002, reload=True)
