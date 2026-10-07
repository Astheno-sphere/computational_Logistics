from fastapi import FastAPI
from loguru import logger
import orjson
from helper import create_json_logger
import time

create_json_logger()

def orjson_serializer(obj):
    return orjson.dumps(obj, option=orjson.OPT_SERIALIZE_NUMPY).decode()

app = FastAPI()
app.router.json_dumps = orjson_serializer

_t = time.time()
logger.debug(f"Simulation loaded in {time.time() - _t:.2f} seconds")

