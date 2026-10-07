from typing import List

from loguru import logger
from inputs.gtfs import GTFSData
from settings import settings
from models import Location, TravelPlan, Transit
import aiohttp
from trip_helper.base import TripHelper
from utils import random_uuid


class SolariTripHelper(TripHelper):
    def __init__(self, endpoint: str = None, gtfs_data: GTFSData = None):
        self.endpoint = endpoint or settings.gtfs.solari_endpoint
        self.gtfs_data = gtfs_data or GTFSData.DEFAULT()

    def _parse_solari_travel_plan(self, travel_plan: dict) -> TravelPlan:
        transits = []
        for it in travel_plan["legs"]:
            _d = it.get("transit", it.get("transfer"))
            if not _d:
                continue
            if _d.get("transit_route"):
                _d["transit_route"] = self.gtfs_data.get_route_id_by_name(_d["transit_route"])
                _d["shape_id"] = self.gtfs_data.get_shape_id_from_route_info(
                    route_id=_d["transit_route"],
                    from_stop_name=_d["start_location"]["stop"],
                    to_stop_name=_d["end_location"]["stop"],
                )
            transits.append(Transit(**_d, is_transfer="transfer" in it))
        return TravelPlan(
            id=random_uuid(),
            start_location=travel_plan["start_location"],
            end_location=travel_plan["end_location"],
            start_time=travel_plan["start_time"],
            end_time=travel_plan["end_time"],
            legs=transits,
        )

    async def get_itineraries(self, origin: Location, destination: Location, departure_time: int, max_transfers: int=6) -> List[TravelPlan]:
        async with aiohttp.ClientSession() as session:
            start_at_ms = departure_time * 1000
            payload = {
                "from": origin.model_dump(),
                "to": destination.model_dump(),
                "start_at": start_at_ms,
                "max_transfers": max_transfers,
            }
            async with session.post(self.endpoint, json=payload, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                assert data.get("status") == "ok", f"Error: {data.get('message')}"
                plans = []
                for item in data["itineraries"]:
                    try:
                        plans.append(self._parse_solari_travel_plan(item))
                    except Exception as e:
                        logger.error(f"Error parsing travel plan: {e}, body: {item}")
                plans = list(filter(lambda x: x.legs, plans))
                logger.debug(f"Payload: {payload}, found {len(plans)} itineraries")
                return plans


if __name__ == '__main__':
    import asyncio
    sth = SolariTripHelper(endpoint="http://localhost:8000/v1/plan")
    loop = asyncio.get_event_loop()
    origin = Location(lon=1.53423130511658, lat=43.586655062927974)
    destination = Location(lon=1.486291134338381, lat=43.54970809807004)
    departure_time = 1742845000
    itineraries = loop.run_until_complete(sth.get_itineraries(origin, destination, departure_time))
    print(itineraries)
