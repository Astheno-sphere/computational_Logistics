from llm.llm_model import ModelConfig
from llama_index.core import Settings
from settings import settings
from inputs.gtfs.reader import GTFSData
from world import *
from trip_helper.cached_triphelper import CachedTripHelper
from trip_helper.otp import OTPTripHelper
from inputs.population import SyntheticPopulationLoader, PersonCloseToTheStopFilter
from trip_helper import SolariTripHelper
from scenarios.scenario_v1.loop import ScenarioV1
from scenarios.base import BaseScenario
from scenarios.llm_config import create_llm_config_from_settings
from scenarios.scenario_v1.agent import LLMAgent
from loguru import logger


def bootstrap() -> BaseScenario:
    gtfs_data = GTFSData.DEFAULT()

    min_lon, min_lat, max_lon, max_lat = gtfs_data.get_bounding_box()
    buffer = 0.05  # degrees ~ 5km
    world_bbox = BBox(
        min_lon=min_lon - buffer,
        min_lat=min_lat - buffer,
        max_lon=max_lon + buffer,
        max_lat=max_lat + buffer,
    )

    world_grid = WorldGrid(world_bbox)
    time_grid = TimeGrid()

    population = WorldPopulation(
        SyntheticPopulationLoader(
            filters=[
                PersonCloseToTheStopFilter(
                    max_distance=500,  # 500 meters
                    stop_locations=gtfs_data.all_stop_locations()
                )
            ]
        )
    ).init(world_bbox=world_bbox)

    # Set all people start from home
    for person in population.get_people_list():
        home_location = PersonScheduler(person).get_home_location()
        person.state.last_location = home_location

    world_model = WorldModel(
        world_grid=world_grid,
        time_grid=time_grid,
        gtfs_data=gtfs_data,
        bbox=world_bbox,
        population=population,
    )

    # model_config = ModelConfig.create_openai_config(
    #     llm_model="gpt-3.5-turbo",
    #     embedding_model="text-embedding-3-small",
    # )
    model_config = create_llm_config_from_settings()
    Settings.llm = model_config.create_llm(use_async=True)
    Settings.embed_model = model_config.create_embedding()

    trip_helper = None
    if settings.gtfs.mode == "OTP":
        logger.info("Using OTP trip helper")
        trip_helper = OTPTripHelper(
            endpoint=settings.gtfs.otp_endpoint,
            gtfs_data=gtfs_data
        )
    else:
        logger.info("Using Solari trip helper")
        trip_helper = CachedTripHelper(
            world_model=world_model,
            trip_helper=SolariTripHelper(
                endpoint=settings.gtfs.solari_endpoint,
                gtfs_data=gtfs_data,
            ),
        )

    loop = ScenarioV1(
        world_model=world_model,
        trip_helper=trip_helper,
        agent=LLMAgent(llm=Settings.llm),
    )

    return loop
