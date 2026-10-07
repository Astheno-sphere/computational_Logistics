import asyncio
import json
import os
import orjson
import uvicorn
from loguru import logger
from helper import create_json_logger
from gama_models import GamaPersonData, MessageResponse, MessageType, WorldInitResponse, WorldSyncRequest
from scenarios.base import BaseScenario, Observation
from handle.websocket import WebSocketClient
from settings import settings
import traceback
from fastapi import FastAPI

workdir = os.environ.get("APP_WORKDIR", "")
if workdir:
    settings.update_workdir(workdir)

create_json_logger()

# import scenario
import scenarios.scenario_v1.factory

app = FastAPI()

def orjson_serializer(obj):
    return orjson.dumps(obj, option=orjson.OPT_SERIALIZE_NUMPY).decode()
app.router.json_dumps = orjson_serializer

print(settings.app.history_file_v2)

class LoopContainer:
    action_topic = "action/data"
    observation_topic = "observation/data"

    def __init__(self):
        self.client = None
        self.scenario = None
        self.websocket_client = WebSocketClient(settings.server.gama_ws_url)
        self.websocket_client.on_message = self.handle_message

    def set_scenario(self, scenario: BaseScenario):
        self.scenario = scenario

    async def greeting(self):
        """Send a greeting message to the WebSocket server"""
        await self.websocket_client.connect()

        greeting_message = {
            "topic": self.action_topic,
            "payload": {
                "type": "greeting",
                "message": "Hello from FastAPI + WebSocket client!"
            }
        }
        success = await self.websocket_client.send_json(greeting_message)
        if not success:
            logger.error("Failed to send greeting message")

    async def publish_loop(self):    
        while True:
            try:
                # Check if scenario has messages to publish
                if self.scenario and await self.scenario.has_messages():
                    messages = await self.scenario.pop_all_messages()
                    len_messages = len(messages)
                    while messages:
                        message = messages[0]
                        payload = message.model_dump()
                        success = await self.websocket_client.send_json({
                            "topic": self.action_topic,
                            "payload": payload,
                        })
                        if not success:
                            logger.error(f"Failed to send message: {payload}")
                            await asyncio.sleep(1)  # Wait before retrying
                            continue
                        messages.pop(0)  # Remove the message from the list after sending

                    logger.info(f"Websocket loop Sent {len_messages} messages to {self.action_topic}")
            except Exception as e:
                logger.error(f"WebSocket publish loop error: {e}")
                await asyncio.sleep(self.reconnect_interval)

            await asyncio.sleep(1)  # Adjust sleep time as needed

    async def handle_message(self, text: str):
        """Handle received Websocket message"""
        try:
            logger.debug(f"Received: {self.observation_topic} -> {text}")
            await self.process_observation(self.observation_topic, text)

        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error handling message: {e}")

    async def process_observation(self, topic: str, payload: str):
        """Process observation data"""
        try:
            data = json.loads(payload)
            assert data["topic"] == self.observation_topic, "Invalid topic in observation data"
            observation = Observation(**data["payload"])
            await self.scenario.handle_observation(observation)
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error processing observation: {e}")

# Global loop container
loop_container = LoopContainer()
scenario = scenarios.scenario_v1.factory.bootstrap()
loop_container.set_scenario(scenario)

@app.on_event("startup")
async def startup_event():
    # Tạo background task cho WebSocket loop
    await loop_container.greeting()
    asyncio.create_task(loop_container.websocket_client.run_with_reconnect())
    asyncio.create_task(loop_container.publish_loop())

@app.on_event("shutdown")
async def shutdown_event():
    await loop_container.websocket_client.stop()

@app.get("/")
async def root():
    return {"status": "FastAPI + Websocket running"}

@app.post("/init")
async def init():
    logger.info("Publishing world data")

    people = scenario.population.get_people_list()

    person_response = [
        GamaPersonData(
            **person.model_dump(),
            location=scenario.population.get_person_home_location(person.person_id),
            name=person.identity.name,
        ) 
        for person in people
    ]
    return MessageResponse(
        message_type=MessageType.AG_WORLD_INIT,
        data=WorldInitResponse(
            people=person_response,
            num_people=len(people),
            # TODO: remove this
            timestamp=0,
        )
    )

@app.post("/reflect")
async def reflect(request: WorldSyncRequest):
    logger.info(f"Reflecting world at timestamp: {request.timestamp}")

    if loop_container.scenario:
        await loop_container.scenario.reflect_all(request.timestamp)
        return MessageResponse(
            data="reflected",
            success=True,
        )
    else:
        return MessageResponse(
            success=False,
            error="Scenario not set"
        )

@app.post("/sync")
async def sync(request: WorldSyncRequest):
    logger.info(f"Synchronizing world at timestamp: {request.timestamp}")

    if loop_container.scenario:
        await loop_container.scenario.sync(request.timestamp, idle_people=request.idle_people)
        return MessageResponse(
            data="synchronized",
            success=True,
        )
    else:
        return MessageResponse(
            success=False,
            error="Scenario not set"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
