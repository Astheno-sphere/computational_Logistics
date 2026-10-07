import traceback

from loguru import logger
from errors import MoveNotFoundExeption
from models import Person, PersonId, PersonMove
from gama_models import \
    DailyCronRequest, GamaPersonData, MessageResponse, \
    MessageType, ObservationUpdateRequest, \
    PeopleNextMoveRequest, WorldInitRequest, WorldInitResponse
from api.application import app

""" World
"""
@app.post("/init")
async def init(_: WorldInitRequest) -> MessageResponse[WorldInitResponse]:
    return MessageResponse(
        message_type=MessageType.AG_WORLD_INIT,
        data=WorldInitResponse(
            people=[],
            num_people=len([]),
            # TODO: remove this
            timestamp=0,
        )
    )


# """ Move
# """
# @app.post("/move/next")
# async def move_next(request: PeopleNextMoveRequest) -> MessageResponse[PersonMove]:
#     logger.debug(f"Next move request: {request}")
#     try:
#         move = await simulation.next_move(
#             person_id=request.person_id,
#             timestamp=request.timestamp,
#             from_purpose=request.from_purpose,
#             from_location=request.from_location,
#         )
#     except Exception as e:
#         traceback.print_exc()
#         return MessageResponse(
#             success=False,
#             message_type=MessageType.AG_PEOPLE_NEXT_MOVE,
#             error=f"Error in next move: {str(e)}",
#         )
    
#     return MessageResponse(
#         message_type=MessageType.AG_PEOPLE_NEXT_MOVE,
#         data=move,
#     )


# """ Observation
# """
# @app.post("/ob/add")
# async def ob_update(request: ObservationUpdateRequest) -> MessageResponse[PersonMove]:
#     try:
#         person = simulation.population.get_person(request.person_id)
#         if not person:
#             return MessageResponse(
#                 success=False,
#                 message_type=MessageType.AG_ACK,
#                 error=f"Person with ID {request.person_id} not found.",
#             )
#         await simulation.llm_agent.short_term_memory.add_observation(
#             person=person,
#             ob_type=EventType(request.type),
#             observation_data=request.data,
#         )
#     except MoveNotFoundExeption as e:
#         traceback.print_exc()
#         return MessageResponse(
#             success=False,
#             message_type=MessageType.AG_ACK,
#             error=f"Error in finish move: {str(e)}",
#         )
    
#     return MessageResponse(
#         message_type=MessageType.AG_ACK,
#     )

# """ Cron
# """
# @app.post("/cron/daily")
# async def daily_cron(request: DailyCronRequest) -> MessageResponse[None]:
#     try:
#         # await simulation.cron_daily(timestamp=request.timestamp)
#         pass
#     except Exception as e:
#         traceback.print_exc()
#         return MessageResponse(
#             success=False,
#             message_type=MessageType.AG_ACK,
#             error=f"Error in daily cron: {str(e)}",
#         )
    
#     return MessageResponse(
#         message_type=MessageType.AG_ACK,
#     )

# """ DEBUG routes
# """
# @app.get("/debug/person")
# async def debug_people(person_id: PersonId) -> MessageResponse[Person]:
#     person = simulation.population.get_person(person_id)
#     if not person:
#         return MessageResponse(
#             success=False,
#             error=f"Person with ID {person_id} not found.",
#         )
    
#     return MessageResponse(
#         data=person,
#     )
