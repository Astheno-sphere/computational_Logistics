import traceback
from typing import Any
import asyncio

from loguru import logger
from errors import MoveNotFoundExeption
from models import Person, PersonId, PersonMove
from gama_models import \
    DailyCronRequest, GamaPersonData, MessageResponse, \
    MessageType, ObservationBatchUpdateRequest, ObservationUpdateRequest, PeopleBatchNextMoveRequest, \
    PeopleNextMoveRequest, WorldInitRequest, WorldInitResponse
from agents.events import EventType
from api.application import app, simulation


""" Move
"""
async def query_move(person, timestamp, semaphore: asyncio.Semaphore):
    async with semaphore:
        move = await simulation.next_move(
            person_id=person.person_id,
            timestamp=timestamp,
            from_purpose=person.from_purpose,
            from_location=person.from_location,
        )
        return move
    
@app.post("/move/batch/next")
async def batch_move_next(request: PeopleBatchNextMoveRequest) -> MessageResponse[list[PersonMove]]:
    try:
        moves = []
        concurrency_limit = 8
        semaphore = asyncio.Semaphore(concurrency_limit)
        tasks = [asyncio.create_task(query_move(person, request.timestamp, semaphore)) for person in request.people]
        results = await asyncio.gather(*tasks)
        moves = [result for result in results if result is not None]
    except Exception as e:
        traceback.print_exc()
        return MessageResponse(
            success=False,
            message_type=MessageType.AG_PEOPLE_BATCH_NEXT_MOVE,
            error=f"Error in next move: {str(e)}",
        )
    
    return MessageResponse(
        message_type=MessageType.AG_PEOPLE_BATCH_NEXT_MOVE,
        data=moves,
    )


""" Observation
"""
@app.post("/ob/batch/add")
async def batch_ob_update(request: ObservationBatchUpdateRequest) -> MessageResponse[Any]:
    try:
        pass
        # for ob in request.observations:
        #     person = simulation.population.get_person(ob.person_id)
        #     if not person:
        #         return MessageResponse(
        #             success=False,
        #             message_type=MessageType.AG_ACK,
        #             error=f"Person with ID {ob.person_id} not found.",
        #         )
        #     context = simulation.default_context(timestamp=ob.timestamp)
        #     await simulation.llm_agent.add_observation(
        #         context=context,
        #         person=person,
        #         event_type=EventType(ob.type),
        #         data=ob.data,
        #     )
    except MoveNotFoundExeption as e:
        traceback.print_exc()
        return MessageResponse(
            success=False,
            message_type=MessageType.AG_ACK,
            error=f"Error in finish move: {str(e)}",
        )
    
    return MessageResponse(
        message_type=MessageType.AG_ACK,
    )
