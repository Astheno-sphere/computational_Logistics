"""Simulator: Urban Simulator"""

import asyncio
import os
import tempfile
from datetime import datetime
from subprocess import Popen
from typing import Any, Literal, Optional, Tuple, Union, overload

import yaml
from pycityproto.city.map.v2 import map_pb2 as map_pb2
from pycityproto.city.person.v2 import person_pb2 as person_pb2
from pycityproto.city.person.v2 import person_service_pb2 as person_service
from pycityproto.city.trip.v2.trip_pb2 import TripMode
from pydantic import BaseModel, ConfigDict, Field
from pyproj import Proj
from shapely.geometry import Point

from ..logger import get_logger
from ..s3 import S3Client, S3Config
from .economy.econ_client import EconomyClient
from .mapdata import MapConfig, MapData
from .sim import CityClient
from .syncer import Syncer
from .utils import find_free_ports
from .utils.base64 import encode_to_base64
from .utils.const import POI_CATG_DICT
from .utils.protobuf import dict2pb
from .download_sim import download_binary

__all__ = [
    "Environment",
    "EnvironmentStarter",
    "EnvironmentConfig",
]


POI_START_ID = 7_0000_0000


class EnvironmentConfig(BaseModel):
    """Configuration for the simulation environment."""

    model_config = ConfigDict(use_enum_values=True, use_attribute_docstrings=True)

    start_tick: int = Field(default=8 * 60 * 60)
    """Starting tick of one day, in seconds"""

    metric_interval: int = Field(default=3600)
    """Interval of metrics, in ticks"""

    weather: str = Field(default="The weather is sunny")
    """Current weather condition in the environment"""

    temperature: str = Field(default="The temperature is 23C")
    """Current temperature in the environment"""

    workday: bool = Field(default=True)
    """Indicates if it's a working day"""

    other_information: str = Field(default="")
    """Additional environment information"""

    def to_prompts(self) -> dict[str, Any]:
        """Convert the environment config to prompts"""
        return {
            "weather": self.weather,
            "temperature": self.temperature,
            "workday": self.workday,
            "other_information": self.other_information,
        }


class Environment:
    """
    The environment, including map data, simulator clients, and environment variables.
    """

    def __init__(
        self,
        map_data: MapData,
        server_addr: Optional[str],
        environment_config: EnvironmentConfig,
        citizen_ids: set[int] = set(),
        firm_ids: set[int] = set(),
        bank_ids: set[int] = set(),
        nbs_ids: set[int] = set(),
        government_ids: set[int] = set(),
    ):
        """
        Initialize the Environment.

        - **Args**:
            - `map_data`: `MapData`, map data
            - `server_addr`: `str`, server address
            - `environment_config`: `EnvironmentConfig`, environment config
            - `citizen_ids`: `set[int]`, citizen ids
            - `firm_ids`: `set[int]`, firm ids
            - `bank_ids`: `set[int]`, bank ids
            - `nbs_ids`: `set[int]`, nbs ids
            - `government_ids`: `set[int]`, government ids
            - `syncer`: `ray.ObjectRef`, syncer for get_tick
        """
        self._map = map_data
        self._create_poi_id_2_aoi_id()
        self._server_addr = server_addr
        self.poi_cate = POI_CATG_DICT
        """poi categories"""

        self._projector = Proj(self._map.get_projector())
        self._environment_config = environment_config
        self._environment_prompt = environment_config.to_prompts()

        self._log_list = []
        """log list"""

        self._lock = asyncio.Lock()
        """lock for simulator"""

        self._tick = 0
        """number of simulated ticks"""

        self._aoi_message: dict[int, dict[int, list[str]]] = {}
        """aoi message"""

        self._init_citizen_ids = citizen_ids
        self._init_firm_ids = firm_ids
        self._init_bank_ids = bank_ids
        self._init_nbs_ids = nbs_ids
        self._init_government_ids = government_ids

        # type annotation
        self._server_addr = server_addr
        self._city_client: Optional[CityClient] = None
        self._economy_client: Optional[EconomyClient] = None

    def init(self) -> Any:
        assert self._server_addr is not None, "Server address not initialized"
        self._city_client = CityClient(self._server_addr)
        self._economy_client = EconomyClient(self._server_addr)
        self._economy_client.set_ids(
            citizen_ids=self._init_citizen_ids,
            firm_ids=self._init_firm_ids,
            bank_ids=self._init_bank_ids,
            nbs_ids=self._init_nbs_ids,
            government_ids=self._init_government_ids,
        )

    def close(self) -> Any:
        """Close the Environment."""
        pass

    def _create_poi_id_2_aoi_id(self):
        assert self._map is not None
        pois = self._map.get_all_pois()
        self.poi_id_2_aoi_id: dict[int, int] = {
            poi["id"]: poi["aoi_id"] for poi in pois
        }

    @property
    def map(self):
        assert self._map is not None, "Map not initialized"
        return self._map

    @property
    def city_client(self):
        assert self._city_client is not None, "Client not initialized"
        return self._city_client

    @property
    def economy_client(self):
        assert self._economy_client is not None, "Economy client not initialized"
        return self._economy_client

    @property
    def projector(self):
        return self._projector

    def get_log_list(self):
        return self._log_list

    def clear_log_list(self):
        self._log_list = []

    def get_poi_cate(self):
        return self.poi_cate

    def get_aoi_ids(self):
        aois = self._map.get_all_aois()
        return [aoi["id"] for aoi in aois]

    def register_aoi_message(
        self, agent_id: int, target_aoi: Union[int, list[int]], content: str
    ):
        """
        Register aoi message

        - **Args**:
            - `target_aoi` (`Union[int, list[int]]`): The ID of the target aoi.
            - `content` (`str`): The content of the message to send.
        """
        if isinstance(target_aoi, int):
            target_aoi = [target_aoi]
        for aoi in target_aoi:
            if aoi not in self._aoi_message:
                self._aoi_message[aoi] = {}
            if agent_id not in self._aoi_message[aoi]:
                self._aoi_message[aoi][agent_id] = []
            self._aoi_message[aoi][agent_id].append(content)

    def cancel_aoi_message(self, agent_id: int, target_aoi: Union[int, list[int]]):
        """
        Cancel aoi message
        """
        if isinstance(target_aoi, int):
            target_aoi = [target_aoi]
        for aoi in target_aoi:
            if aoi in self._aoi_message:
                if agent_id in self._aoi_message[aoi]:
                    self._aoi_message[aoi].pop(agent_id)
                if len(self._aoi_message[aoi]) == 0:
                    self._aoi_message.pop(aoi)

    @property
    def environment(self) -> dict[str, str]:
        """
        Get the current state of environment variables.
        """
        return self._environment_prompt

    def set_environment(self, environment: dict[str, str]):
        """
        Set the entire dictionary of environment variables.

        - **Args**:
            - `environment` (`Dict[str, str]`): Key-value pairs of environment variables.
        """
        self._environment_prompt = environment

    def sense(self, key: str) -> Any:
        """
        Retrieve the value of an environment variable by its key.

        - **Args**:
            - `key` (`str`): The key of the environment variable.

        - **Returns**:
            - `Any`: The value of the corresponding key, or an empty string if not found.
        """
        return self._environment_prompt.get(key, "Don't know")

    def sense_aoi(self, aoi_id: int) -> str:
        """
        Retrieve the value of an environment variable by its key.
        """
        if aoi_id in self._aoi_message:
            msg_ = ""
            aoi_messages = self._aoi_message[aoi_id]
            for _, messages in aoi_messages.items():
                for message in messages:
                    msg_ += message + "\n"
            return msg_
        else:
            return ""

    def update_environment(self, key: str, value: Any):
        """
        Update the value of a single environment variable.

        - **Args**:
            - `key` (`str`): The key of the environment variable.
            - `value` (`Any`): The new value to set.
        """
        self._environment_prompt[key] = value

    def get_environment(self) -> str:
        global_prompt = ""
        for key in self._environment_prompt:
            value = self._environment_prompt[key]
            if isinstance(value, str):
                global_prompt += f"{key}: {value}\n"
            elif isinstance(value, dict):
                for k, v in value.items():
                    global_prompt += f"{key}.{k}: {v}\n"
            elif isinstance(value, bool):
                global_prompt += f"Is it {key}: {value}\n"
            elif isinstance(value, list):
                global_prompt += f"{key} elements: {value}\n"
            else:
                global_prompt += f"{key}: {value}\n"
        return global_prompt

    def get_poi_categories(
        self,
        center: Optional[Union[tuple[float, float], Point]] = None,
        radius: Optional[float] = None,
    ) -> list[str]:
        """
        Retrieve unique categories of Points of Interest (POIs) around a central point.

        - **Args**:
            - `center` (`Optional[Union[Tuple[float, float], Point]]`): The central point as a tuple or Point object.
              Defaults to (0, 0) if not provided.
            - `radius` (`Optional[float]`): The search radius in meters. If not provided, all POIs are considered.

        - **Returns**:
            - `List[str]`: A list of unique POI category names.
        """
        categories: list[str] = []
        if center is None:
            center = (0, 0)
        assert self._map is not None
        _pois: list[Any] = self._map.query_pois(
            center=center,
            radius=radius,
            return_distance=False,
        )
        for poi in _pois:
            catg = poi["category"]
            categories.append(catg.split("|")[-1])
        return list(set(categories))

    def set_tick(self, tick: int):
        self._tick = tick

    def get_tick(self) -> int:
        return self._tick

    @overload
    def get_datetime(self) -> tuple[int, int]: ...
    @overload
    def get_datetime(self, format_time: Literal[False]) -> tuple[int, int]: ...
    @overload
    def get_datetime(
        self, format_time: Literal[True], format: str = "%H:%M:%S"
    ) -> tuple[int, str]: ...

    def get_datetime(
        self, format_time: bool = False, format: str = "%H:%M:%S"
    ) -> Union[tuple[int, int], tuple[int, str]]:
        """
        Get the current time of the simulator.

        By default, returns the number of seconds since midnight. Supports formatted output.

        - **Args**:
            - `format_time` (`bool`): Whether to return the time in a formatted string. Defaults to `False`.
            - `format` (`str`): The format string for formatting the time. Defaults to "%H:%M:%S".

        - **Returns**:
            - `Union[tuple[int, int], tuple[int, str]]`: The current simulation (day, time) either as an integer representing seconds since midnight or as a formatted string.
        """

        tick = self._tick
        day = (tick + self._environment_config.start_tick) // (24 * 60 * 60)
        time = (tick + self._environment_config.start_tick) % (24 * 60 * 60)
        if format_time:
            hours = time // 3600
            minutes = (time % 3600) // 60
            seconds = time % 60
            formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            if format != "%H:%M:%S":
                temp_time = datetime.strptime(formatted_time, "%H:%M:%S")
                formatted_time = temp_time.strftime(format)
            return (day, formatted_time)
        else:
            return (day, time)

    async def get_person(self, person_id: int) -> dict:
        """
        Retrieve information about a specific person by ID.

        - **Args**:
            - `person_id` (`int`): The ID of the person to retrieve information for.

        - **Returns**:
            - `Dict`: Information about the specified person.
        """
        person = await self.city_client.person_service.GetPerson(
            req={"person_id": person_id}
        )
        return person

    async def add_person(self, dict_person: dict) -> dict:
        """
        Add a new person to the simulation.

        - **Args**:
            - `dict_person` (`dict`): The person object to add.

        - **Returns**:
            - `Dict`: Response from adding the person.
        """
        person = dict2pb(dict_person, person_pb2.Person())
        if isinstance(person, person_pb2.Person):
            req = person_service.AddPersonRequest(person=person)
        else:
            req = person
        resp: dict = await self.city_client.person_service.AddPerson(req)
        return resp

    async def set_aoi_schedules(
        self,
        person_id: int,
        target_positions: Union[
            list[Union[int, tuple[int, int]]], Union[int, tuple[int, int]]
        ],
        departure_times: Optional[list[float]] = None,
        modes: Optional[list[TripMode]] = None,
    ):
        """
        Set schedules for a person to visit Areas of Interest (AOIs).

        - **Args**:
            - `person_id` (`int`): The ID of the person whose schedule is being set.
            - `target_positions` (`Union[List[Union[int, Tuple[int, int]]], Union[int, Tuple[int, int]]]`):
              A list of AOI or POI IDs or tuples of (AOI ID, POI ID) that the person will visit.
            - `departure_times` (`Optional[List[float]]`): Departure times for each trip in the schedule.
              If not provided, current time will be used for all trips.
            - `modes` (`Optional[List[int]]`): Travel modes for each trip.
              Defaults to `TRIP_MODE_DRIVE_ONLY` if not specified.
        """
        cur_time = float(self.get_tick())
        if not isinstance(target_positions, list):
            target_positions = [target_positions]
        if departure_times is None:
            departure_times = [cur_time for _ in range(len(target_positions))]
        else:
            for _ in range(len(target_positions) - len(departure_times)):
                departure_times.append(cur_time)
        if modes is None:
            modes = [
                TripMode.TRIP_MODE_DRIVE_ONLY for _ in range(len(target_positions))
            ]
        else:
            for _ in range(len(target_positions) - len(modes)):
                modes.append(TripMode.TRIP_MODE_DRIVE_ONLY)
        _schedules = []
        for target_pos, _time, _mode in zip(target_positions, departure_times, modes):
            if isinstance(target_pos, int):
                if target_pos >= POI_START_ID:
                    poi_id = target_pos
                    end = {
                        "aoi_position": {
                            "aoi_id": self.poi_id_2_aoi_id[poi_id],
                            "poi_id": poi_id,
                        }
                    }
                else:
                    aoi_id = target_pos
                    end = {
                        "aoi_position": {
                            "aoi_id": aoi_id,
                        }
                    }
            else:
                aoi_id, poi_id = target_pos
                end = {"aoi_position": {"aoi_id": aoi_id, "poi_id": poi_id}}
                # activity = ""
            trips = [
                {
                    "mode": _mode,
                    "end": end,
                    "departure_time": _time,
                },
            ]
            _schedules.append(
                {"trips": trips, "loop_count": 1, "departure_time": _time}
            )
        req = {"person_id": person_id, "schedules": _schedules}
        await self.city_client.person_service.SetSchedule(req)

    async def reset_person_position(
        self,
        person_id: int,
        aoi_id: Optional[int] = None,
        poi_id: Optional[int] = None,
        lane_id: Optional[int] = None,
        s: Optional[float] = None,
    ):
        """
        Reset the position of a person within the simulation.

        - **Args**:
            - `person_id` (`int`): The ID of the person whose position is being reset.
            - `aoi_id` (`Optional[int]`): The ID of the Area of Interest (AOI) where the person should be placed.
            - `poi_id` (`Optional[int]`): The ID of the Point of Interest (POI) within the AOI.
            - `lane_id` (`Optional[int]`): The ID of the lane on which the person should be placed.
            - `s` (`Optional[float]`): The longitudinal position along the lane.
        """
        reset_position = {}
        if aoi_id is not None:
            reset_position["aoi_position"] = {"aoi_id": aoi_id}
            if poi_id is not None:
                reset_position["aoi_position"]["poi_id"] = poi_id
            get_logger().debug(
                f"Setting person {person_id} pos to AoiPosition {reset_position}"
            )
            await self.city_client.person_service.ResetPersonPosition(
                {"person_id": person_id, "position": reset_position}
            )
        elif lane_id is not None:
            reset_position["lane_position"] = {
                "lane_id": lane_id,
                "s": 0.0,
            }
            if s is not None:
                reset_position["lane_position"]["s"] = s
            get_logger().debug(
                f"Setting person {person_id} pos to LanePosition {reset_position}"
            )
            await self.city_client.person_service.ResetPersonPosition(
                {"person_id": person_id, "position": reset_position}
            )
        else:
            get_logger().debug(
                f"Neither aoi or lane pos provided for person {person_id} position reset!!"
            )

    def get_around_poi(
        self,
        center: Union[tuple[float, float], Point],
        radius: float,
        poi_type: Union[str, list[str]],
    ) -> list[dict]:
        """
        Get Points of Interest (POIs) around a central point based on type.

        - **Args**:
            - `center` (`Union[Tuple[float, float], Point]`): The central point as a tuple or Point object.
            - `radius` (`float`): The search radius in meters.
            - `poi_type` (`Union[str, List[str]]`): The category or categories of POIs to filter by.

        - **Returns**:
            - `List[Dict]`: A list of dictionaries containing information about the POIs found.
        """
        if isinstance(poi_type, str):
            poi_type = [poi_type]
        transformed_poi_type: list[str] = []
        for t in poi_type:
            if t not in self.poi_cate:
                transformed_poi_type.append(t)
            else:
                transformed_poi_type += self.poi_cate[t]
        poi_type_set = set(transformed_poi_type)
        # query pois within the radius
        assert self._map is not None
        _pois: list[dict] = self._map.query_pois(
            center=center,
            radius=radius,
            return_distance=False,
        )
        # Filter out POIs that do not meet the category prefix
        pois = []
        for poi in _pois:
            catg = poi["category"]
            if catg.split("|")[-1] not in poi_type_set:
                continue
            pois.append(poi)
        return pois


class EnvironmentStarter(Environment):
    """
    The entrypoint of the simulator, used to initialize the simulator and map.

    - **Description**:
        - This class is the core of the simulator, responsible for initializing and managing the simulation environment.
        - It reads parameters from a configuration dictionary, initializes map data, and starts or connects to a simulation server as needed.
    """

    def __init__(
        self,
        map_config: MapConfig,
        environment_config: EnvironmentConfig,
        s3config: S3Config,
        log_dir: str,
        home_dir: str,
    ):
        """
        Environment config

        - **Args**:
            - `map_config` (MapConfig): Map config
            - `simulator_config` (SimulatorConfig): Simulator config
            - `environment_config` (EnvironmentConfig): Environment config
        """
        self._sim_bin_path = download_binary(home_dir)
        self._map_config = map_config
        self._environment_config = environment_config
        self._s3config = s3config
        self._log_dir = log_dir
        self._home_dir = home_dir
        mapdata = MapData(map_config, s3config)

        super().__init__(mapdata, None, environment_config)

        self._last_metric_tick = -1e999

        # type annotation
        self._sim_proc: Optional[Popen] = None

    def to_init_args(self):
        return {
            "map_data": self._map,
            "server_addr": self._server_addr,
            "environment_config": self._environment_config,
            "citizen_ids": self.economy_client._citizen_ids,
            "firm_ids": self.economy_client._firm_ids,
            "bank_ids": self.economy_client._bank_ids,
            "nbs_ids": self.economy_client._nbs_ids,
            "government_ids": self.economy_client._government_ids,
        }

    @property
    def syncer(self):
        assert self._syncer is not None, "Syncer not initialized"
        return self._syncer

    async def init(self):
        """
        Initialize the environment including the syncer and the simulator.
        """
        # =========================
        # init syncer
        # =========================
        sim_port, syncer_port = find_free_ports(2)
        syncer_addr = f"localhost:{syncer_port}"
        self._syncer = Syncer(syncer_addr)
        await self._syncer.init()

        # =========================
        # init simulator
        # =========================

        # if s3 enabled, download the map from s3
        file_path = self._map_config.file_path
        if self._s3config.enabled:
            client = S3Client(self._s3config)
            map_bytes = client.download(self._map_config.file_path)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".map") as tmp:
                tmp.write(map_bytes)
                file_path = tmp.name

        config_base64 = encode_to_base64(_generate_yaml_config(file_path))
        self._server_addr = f"localhost:{sim_port}"
        self._sim_proc = Popen(
            [
                self._sim_bin_path,
                "-config-data",
                config_base64,
                "-job",
                "agentsociety",
                "-listen",
                self._server_addr,
                "-syncer",
                "http://" + syncer_addr,
                "-cache",
                "",
                "-log.level",
                "warn",
            ],
            env=os.environ,
        )

        # step 1 tick as the syncer init
        await self.syncer.step()

        get_logger().info(
            f"start agentsociety-sim-oss at {self._server_addr}, PID={self._sim_proc.pid}"
        )

        # remove the temporary file
        if self._s3config.enabled:
            os.remove(file_path)

        super().init()

    async def close(self):
        """
        Terminate the simulation process if it's running.
        """
        if self._syncer is not None:
            await self._syncer.close()
            self._syncer = None
        if self._sim_proc is not None and self._sim_proc.poll() is None:
            get_logger().info(
                f"Terminating agentsociety-sim-oss at {self._server_addr}, PID={self._sim_proc.pid}, please ignore the PANIC message"
            )
            self._sim_proc.kill()
            # wait for the process to terminate
            self._sim_proc.wait()
        self._sim_proc = None

    async def step(self, n: int):
        assert n > 0, "`n` must >=1!"
        for _ in range(n):
            await self.syncer.step()
            self._tick += 1

    async def get_metrics(self) -> list[Tuple[str, float, int]]:
        """
        Get the metrics of the environment for recording.

        - **Returns**:
            - `List[Tuple[str, float, int]]`: A list of tuples, each containing the metric name, value, and step.
        """
        if (
            self._last_metric_tick + self._environment_config.metric_interval
            > self._tick
        ):
            return []

        # Add mobility metrics
        # 1. cumulative travel distance
        # 2. cumulative number of trips
        stat = await self._city_client.person_service.GetGlobalStatistics({}, True)
        num_completed_trips = stat["num_completed_trips"]
        total_travel_time = stat["running_total_travel_time"]
        total_travel_distance = stat["running_total_travel_distance"]

        self._last_metric_tick = self._tick

        return [
            ("num_completed_trips", num_completed_trips, self._tick),
            ("total_travel_time (sec)", total_travel_time, self._tick),
            ("total_travel_distance (m)", total_travel_distance, self._tick),
        ]


def _generate_yaml_config(map_file) -> str:
    config_dict = {
        "input": {"map": {"file": os.path.abspath(map_file)}},
        "control": {
            "step": {"start": 0, "total": int(2**31 - 1), "interval": 1},
            "prefer_fixed_light": True,
        },
    }
    return yaml.dump(config_dict, allow_unicode=True)
