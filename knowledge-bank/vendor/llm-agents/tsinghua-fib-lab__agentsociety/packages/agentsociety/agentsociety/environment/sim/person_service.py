from collections.abc import Awaitable, Coroutine
from typing import Any, Literal, Union, cast, overload

import grpc
from google.protobuf.json_format import ParseDict
from pycityproto.city.person.v2 import person_pb2 as person_pb2
from pycityproto.city.person.v2 import person_service_pb2 as person_service
from pycityproto.city.person.v2 import person_service_pb2_grpc as person_grpc
from pycityproto.city.person.v2.person_pb2 import (
    BikeAttribute,
    EmissionAttribute,
    PedestrianAttribute,
    Person,
    PersonAttribute,
    PersonType,
    VehicleAttribute,
    VehicleEngineEfficiency,
    VehicleEngineType,
)

from ..utils.protobuf import async_parse, pb2dict

__all__ = ["PersonService"]


def default_person_template_generator() -> Person:
    return Person(
        attribute=PersonAttribute(),
        type=PersonType.PERSON_TYPE_NORMAL,
        vehicle_attribute=VehicleAttribute(
            length=5,
            width=2,
            max_speed=150 / 3.6,
            max_acceleration=3,
            max_braking_acceleration=-10,
            usual_acceleration=2,
            usual_braking_acceleration=-4.5,
            headway=1.5,
            lane_max_speed_recognition_deviation=1.0,
            lane_change_length=10,
            min_gap=1,
            emission_attribute=EmissionAttribute(
                weight=2100,
                type=VehicleEngineType.VEHICLE_ENGINE_TYPE_FUEL,
                coefficient_drag=0.251,
                lambda_s=0.29,
                frontal_area=2.52,
                fuel_efficiency=VehicleEngineEfficiency(
                    energy_conversion_efficiency=0.27 * 0.049,
                    c_ef=66.98,
                ),
            ),
            model="normal",
        ),
        pedestrian_attribute=PedestrianAttribute(speed=1.34, model="normal"),
        bike_attribute=BikeAttribute(speed=5, model="normal"),
    )


class PersonService:
    """
    交通模拟person服务
    Traffic simulation person service
    """

    def __init__(self, aio_channel: grpc.aio.Channel):
        self._aio_stub = person_grpc.PersonServiceStub(aio_channel)

    @overload
    @staticmethod
    def default_person(return_dict: Literal[False]) -> person_pb2.Person: ...

    @overload
    @staticmethod
    def default_person(return_dict: Literal[True]) -> dict: ...

    @staticmethod
    def default_person(return_dict: bool = False) -> Union[person_pb2.Person, dict]:
        """
        获取person基本模板
        Get person basic template

        需要补充的字段有person.home,person.schedules,person.labels
        The fields that need to be supplemented are person.home, person.schedules, person.labels
        """

        person = default_person_template_generator()
        if return_dict:
            return pb2dict(person)
        return person

    @overload
    def GetPerson(
        self,
        req: Union[person_service.GetPersonRequest, dict[str, Any]],
        dict_return: Literal[False],
    ) -> Coroutine[Any, Any, person_service.GetPersonResponse]: ...

    @overload
    def GetPerson(
        self,
        req: Union[person_service.GetPersonRequest, dict[str, Any]],
        dict_return: Literal[True] = True,
    ) -> Coroutine[Any, Any, dict[str, Any]]: ...

    def GetPerson(
        self,
        req: Union[person_service.GetPersonRequest, dict[str, Any]],
        dict_return: bool = True,
    ) -> Coroutine[Any, Any, Union[dict[str, Any], person_service.GetPersonResponse]]:
        """
        获取person信息
        Get person information

        - **Args**:
        - req (dict): https://cityproto.sim.fiblab.net/#city.person.v2.GetPersonRequest

        - **Returns**:
        - https://cityproto.sim.fiblab.net/#city.person.v2.GetPersonResponse
        """
        if not isinstance(req, person_service.GetPersonRequest):
            req = ParseDict(req, person_service.GetPersonRequest())
        res = cast(
            Awaitable[person_service.GetPersonResponse], self._aio_stub.GetPerson(req)
        )
        return async_parse(res, dict_return)

    @overload
    def AddPerson(
        self,
        req: Union[person_service.AddPersonRequest, dict[str, Any]],
        dict_return: Literal[False],
    ) -> Coroutine[Any, Any, person_service.AddPersonResponse]: ...

    @overload
    def AddPerson(
        self,
        req: Union[person_service.AddPersonRequest, dict[str, Any]],
        dict_return: Literal[True] = True,
    ) -> Coroutine[Any, Any, dict[str, Any]]: ...

    def AddPerson(
        self,
        req: Union[person_service.AddPersonRequest, dict[str, Any]],
        dict_return: bool = True,
    ) -> Coroutine[Any, Any, Union[dict[str, Any], person_service.AddPersonResponse]]:
        """
        新增person
        Add a new person

        - **Args**:
        - req (dict): https://cityproto.sim.fiblab.net/#city.person.v2.AddPersonRequest

        - **Returns**:
        - https://cityproto.sim.fiblab.net/#city.person.v2.AddPersonResponse
        """
        if not isinstance(req, person_service.AddPersonRequest):
            req = ParseDict(req, person_service.AddPersonRequest())
        res = cast(
            Awaitable[person_service.AddPersonResponse], self._aio_stub.AddPerson(req)
        )
        return async_parse(res, dict_return)

    def SetSchedule(
        self,
        req: Union[person_service.SetScheduleRequest, dict[str, Any]],
        dict_return: bool = True,
    ) -> Coroutine[Any, Any, Union[dict[str, Any], person_service.SetScheduleResponse]]:
        """
        修改person的schedule
        set person's schedule

        - **Args**:
        - req (dict): https://cityproto.sim.fiblab.net/#city.person.v2.SetScheduleRequest

        - **Returns**:
        - https://cityproto.sim.fiblab.net/#city.person.v2.SetScheduleResponse
        """
        if not isinstance(req, person_service.SetScheduleRequest):
            req = ParseDict(req, person_service.SetScheduleRequest())
        res = cast(
            Awaitable[person_service.SetScheduleResponse],
            self._aio_stub.SetSchedule(req),
        )
        return async_parse(res, dict_return)


    def ResetPersonPosition(
        self,
        req: Union[person_service.ResetPersonPositionRequest, dict[str, Any]],
        dict_return: bool = True,
    ) -> Coroutine[
        Any, Any, Union[dict[str, Any], person_service.ResetPersonPositionResponse]
    ]:
        """
        重置人的位置（将停止当前正在进行的出行，转为sleep状态）
        Reset person's position (stop the current trip and switch to sleep status)

        - **Args**:
        - req (dict): https://cityproto.sim.fiblab.net/#city.person.v2.ResetPersonPositionRequest

        - **Returns**:
        - https://cityproto.sim.fiblab.net/#city.person.v2.ResetPersonPositionResponse
        """
        if not isinstance(req, person_service.ResetPersonPositionRequest):
            req = ParseDict(req, person_service.ResetPersonPositionRequest())
        res = cast(
            Awaitable[person_service.ResetPersonPositionResponse],
            self._aio_stub.ResetPersonPosition(req),
        )
        return async_parse(res, dict_return)

    @overload
    def GetGlobalStatistics(
        self,
        req: Union[person_service.GetGlobalStatisticsRequest, dict[str, Any]],
        dict_return: Literal[False],
    ) -> Coroutine[Any, Any, person_service.GetGlobalStatisticsResponse]: ...

    @overload
    def GetGlobalStatistics(
        self,
        req: Union[person_service.GetGlobalStatisticsRequest, dict[str, Any]],
        dict_return: Literal[True] = True,
    ) -> Coroutine[Any, Any, dict[str, Any]]: ...

    def GetGlobalStatistics(
        self,
        req: Union[person_service.GetGlobalStatisticsRequest, dict[str, Any]],
        dict_return: bool = True,
    ) -> Coroutine[
        Any, Any, Union[dict[str, Any], person_service.GetGlobalStatisticsResponse]
    ]:
        """
        获取全局统计信息
        Get global statistics

        - **Args**:
        - req (dict): https://cityproto.readthedocs.io/en/latest/docs.html#city-person-v2-GetGlobalStatisticsRequest

        - **Returns**:
        - https://cityproto.readthedocs.io/en/latest/docs.html#city-person-v2-GetGlobalStatisticsResponse
        """
        if not isinstance(req, person_service.GetGlobalStatisticsRequest):
            req = ParseDict(req, person_service.GetGlobalStatisticsRequest())
        res = cast(
            Awaitable[person_service.GetGlobalStatisticsResponse],
            self._aio_stub.GetGlobalStatistics(req),
        )
        return async_parse(res, dict_return)