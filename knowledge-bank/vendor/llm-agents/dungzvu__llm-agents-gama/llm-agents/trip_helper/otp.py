import json
from typing import List, Optional

from datetime import datetime, timezone
from loguru import logger
from helper import to_24h_timestamp, to_timestamp_based_on_day
from inputs.gtfs import GTFSData
from settings import settings
from models import Location, TransitLocation, TravelPlan, Transit
import aiohttp
import asyncio
from trip_helper.base import TripHelper
from utils import random_uuid
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


QUERY = """
query trip($accessEgressPenalty: [PenaltyForStreetMode!], $alightSlackDefault: Int, $alightSlackList: [TransportModeSlack], $arriveBy: Boolean, $banned: InputBanned, $bicycleOptimisationMethod: BicycleOptimisationMethod, $bikeSpeed: Float, $boardSlackDefault: Int, $boardSlackList: [TransportModeSlack], $bookingTime: DateTime, $dateTime: DateTime, $filters: [TripFilterInput!], $from: Location!, $ignoreRealtimeUpdates: Boolean, $includePlannedCancellations: Boolean, $includeRealtimeCancellations: Boolean, $itineraryFilters: ItineraryFilters, $locale: Locale, $maxAccessEgressDurationForMode: [StreetModeDurationInput!], $maxDirectDurationForMode: [StreetModeDurationInput!], $maximumAdditionalTransfers: Int, $maximumTransfers: Int, $modes: Modes, $numTripPatterns: Int, $pageCursor: String, $relaxTransitGroupPriority: RelaxCostInput, $searchWindow: Int, $timetableView: Boolean, $to: Location!, $transferPenalty: Int, $transferSlack: Int, $triangleFactors: TriangleFactors, $useBikeRentalAvailabilityInformation: Boolean, $via: [TripViaLocationInput!], $waitReluctance: Float, $walkReluctance: Float, $walkSpeed: Float, $wheelchairAccessible: Boolean, $whiteListed: InputWhiteListed) {
  trip(
    accessEgressPenalty: $accessEgressPenalty
    alightSlackDefault: $alightSlackDefault
    alightSlackList: $alightSlackList
    arriveBy: $arriveBy
    banned: $banned
    bicycleOptimisationMethod: $bicycleOptimisationMethod
    bikeSpeed: $bikeSpeed
    boardSlackDefault: $boardSlackDefault
    boardSlackList: $boardSlackList
    bookingTime: $bookingTime
    dateTime: $dateTime
    filters: $filters
    from: $from
    ignoreRealtimeUpdates: $ignoreRealtimeUpdates
    includePlannedCancellations: $includePlannedCancellations
    includeRealtimeCancellations: $includeRealtimeCancellations
    itineraryFilters: $itineraryFilters
    locale: $locale
    maxAccessEgressDurationForMode: $maxAccessEgressDurationForMode
    maxDirectDurationForMode: $maxDirectDurationForMode
    maximumAdditionalTransfers: $maximumAdditionalTransfers
    maximumTransfers: $maximumTransfers
    modes: $modes
    numTripPatterns: $numTripPatterns
    pageCursor: $pageCursor
    relaxTransitGroupPriority: $relaxTransitGroupPriority
    searchWindow: $searchWindow
    timetableView: $timetableView
    to: $to
    transferPenalty: $transferPenalty
    transferSlack: $transferSlack
    triangleFactors: $triangleFactors
    useBikeRentalAvailabilityInformation: $useBikeRentalAvailabilityInformation
    via: $via
    waitReluctance: $waitReluctance
    walkReluctance: $walkReluctance
    walkSpeed: $walkSpeed
    wheelchairAccessible: $wheelchairAccessible
    whiteListed: $whiteListed
  ) {
    previousPageCursor
    nextPageCursor
    tripPatterns {
      aimedStartTime
      aimedEndTime
      expectedEndTime
      expectedStartTime
      duration
      distance
      legs {
        id
        mode
        aimedStartTime
        aimedEndTime
        expectedEndTime
        expectedStartTime
        realtime
        distance
        duration
        fromPlace {
          name
          quay {
            id
          }
        }
        toPlace {
          name
          quay {
            id
          }
        }
        toEstimatedCall {
          destinationDisplay {
            frontText
          }
        }
        line {
          publicCode
          name
          id
          presentation {
            colour
          }
        }
        authority {
          name
          id
        }
        pointsOnLink {
          points
        }
        interchangeTo {
          staySeated
        }
        interchangeFrom {
          staySeated
        }
      }
      systemNotices {
        tag
      }
    }
  }
}
"""

class OTPPlace(BaseModel):
    name: str
    quay: Optional[dict] = None

class OTPEstimatedCall(BaseModel):
    destinationDisplay: Optional[dict] = None

class OTPLine(BaseModel):
    publicCode: Optional[str] = None
    name: Optional[str] = None
    id: Optional[str] = None
    presentation: Optional[dict] = None

class OTPAuthority(BaseModel):
    name: Optional[str] = None
    id: Optional[str] = None

class OTPPointsOnLink(BaseModel):
    points: str

class OTPInterchange(BaseModel):
    staySeated: Optional[bool] = None

class OTPLeg(BaseModel):
    id: Optional[str] = None
    mode: str
    aimedStartTime: str
    aimedEndTime: str
    expectedEndTime: str
    expectedStartTime: str
    realtime: bool
    distance: float
    duration: int
    fromPlace: OTPPlace
    toPlace: OTPPlace
    toEstimatedCall: Optional[OTPEstimatedCall] = None
    line: Optional[OTPLine] = None
    authority: Optional[OTPAuthority] = None
    pointsOnLink: Optional[OTPPointsOnLink] = None
    interchangeTo: Optional[OTPInterchange] = None
    interchangeFrom: Optional[OTPInterchange] = None

class OTPSystemNotice(BaseModel):
    tag: str

class OTPTripPattern(BaseModel):
    aimedStartTime: str
    aimedEndTime: str
    expectedEndTime: str
    expectedStartTime: str
    duration: int
    distance: float
    legs: List[OTPLeg]
    systemNotices: Optional[List[OTPSystemNotice]] = []


class OTPTripHelper(TripHelper):
    SUPPORTED_MODES = ["foot", "bus", "metro", "tram", "cableway"]

    def __init__(self, endpoint: str = None, gtfs_data: GTFSData = None):
        self.endpoint = endpoint or settings.gtfs.otp_endpoint
        self.fixed_day: datetime = datetime.strptime(settings.gtfs.fixed_day, '%Y%m%d') if settings.gtfs.fixed_day else None
        self.gtfs_data = gtfs_data or GTFSData.DEFAULT()

    def timestamp_from_isoformat(self, iso_format: str) -> int:
        dt = datetime.fromisoformat(iso_format)
        return int(dt.timestamp())
    
    def parse_gtfs_entity_id(self, name: str) -> str:
        # this is based on the GTFS data of Toulouse
        # it could be changed with other data
        if name.count(":") >= 2:
            return name.split(":", 1)[1]
        return name

    def _parse_otp_travel_plan(self, 
                               travel_plan: dict, 
                               start_location: Optional[Location], 
                               end_location: Optional[Location],
                               real_day: Optional[datetime] = None) -> TravelPlan:
        obj = OTPTripPattern.model_validate(travel_plan)

        def _ptime(iso_time: str) -> int:
            t = self.timestamp_from_isoformat(iso_time)
            if self.fixed_day:
                # revert using real_day
                dt = (real_day - self.fixed_day).days if real_day else 0
                return t + dt * 24 * 60 * 60
            return t

        _proute = self.parse_gtfs_entity_id
        _pstopid = self.parse_gtfs_entity_id

        def _location_from_place(place: OTPPlace) -> TransitLocation:
            if place.name == "Origin":
                return TransitLocation(
                    stop="",
                    lat=start_location.lat,
                    lon=start_location.lon
                )
            elif place.name == "Destination":
                return TransitLocation(
                    stop="",
                    lat=end_location.lat,
                    lon=end_location.lon
                )

            assert place.quay and place.quay.get("id"), f"Invalid place: {place}"

            stop_id = _pstopid(place.quay["id"])
            stop = self.gtfs_data.get_stop(stop_id)
            return TransitLocation(
                stop=stop.stop_name,
                lat=stop.stop_lat,
                lon=stop.stop_lon,
            )


        transits = []
        for leg in obj.legs:
            assert leg.mode in self.SUPPORTED_MODES, f"Unsupported mode: {leg.mode}"
            is_transfer = leg.mode == "foot"

            transit = Transit(
                start_time=_ptime(leg.expectedStartTime),
                end_time=_ptime(leg.expectedEndTime),
                duration=leg.duration,
                distance=leg.distance,
                mode=leg.mode,
                start_location=_location_from_place(leg.fromPlace),
                end_location=_location_from_place(leg.toPlace),
                is_transfer=is_transfer,
            )
            if not is_transfer and leg.line:
                transit.transit_route = _proute(leg.line.id)
                transit.shape_id = self.gtfs_data.get_shape_id_from_route_info(
                    route_id=transit.transit_route,
                    from_stop_name=transit.start_location.stop,
                    to_stop_name=transit.end_location.stop,
                )
            transits.append(transit)

        return TravelPlan(
            id=random_uuid(),
            start_location=start_location,
            end_location=end_location,
            start_time=_ptime(obj.expectedStartTime),
            end_time=_ptime(obj.expectedEndTime),
            duration=obj.duration,
            distance=obj.distance,
            legs=transits,
        )

    def remove_duplicates(self, trips: List[TravelPlan], max_candidates: int) -> List[TravelPlan]:
        # Get max candidates from all results
        bl = set()
        rs = []
        for plan in trips:
            code = plan.get_code()
            if code in bl:
                continue
            bl.add(code)
            rs.append(plan)
            if len(rs) >= max_candidates:
                break
        return rs
    
    def revert_fixed_date(self, timestamp: int, real_date: int) -> int:
        return 0

    async def get_itineraries(self, 
                              origin: Location, 
                              destination: Location, 
                              departure_time: int, 
                              max_options: int=5, # unused
                              search_window_m: int=30) -> List[TravelPlan]:

        real_day = datetime.fromtimestamp(departure_time) if self.fixed_day else None
        real_departure_time = departure_time
        if self.fixed_day is not None:
            departure_time = self.fixed_day.replace(hour=real_day.hour, minute=real_day.minute, second=real_day.second).timestamp()
            logger.debug(f"Using fixed day {self.fixed_day.date()} for departure_time, real day is {real_day}, new departure_time is {departure_time}")
        real_day = real_day.replace(hour=0, minute=0, second=0, microsecond=0) if real_day else None

        async with aiohttp.ClientSession() as session:
            start_at = datetime.fromtimestamp(departure_time, tz=timezone.utc).isoformat()
            payload = {
                "query": QUERY,
                "variables": {
                    "from": {
                        "coordinates": {
                            "latitude": origin.lat,
                            "longitude": origin.lon
                        }
                    },
                    "to": {
                        "coordinates": {
                            "latitude": destination.lat,
                            "longitude": destination.lon
                        }
                    },
                    "dateTime": start_at,
                    "numTripPatterns": 20,
                    "searchWindow": search_window_m
                },
                "operationName": "trip"
            }

            @retry(
                stop=stop_after_attempt(5),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
            )
            async def make_request():
                async with session.post(self.endpoint, json=payload, timeout=10) as response:
                    response.raise_for_status()
                    return await response.json()
            
            try:
                data = await make_request()
                plans = []
                for item in data["data"]["trip"]["tripPatterns"]:
                    try:
                        p = self._parse_otp_travel_plan(item, start_location=origin, end_location=destination, real_day=real_day)
                        p.start_in = max(0, p.start_time - real_departure_time)
                        plans.append(p)
                    except Exception as e:
                        logger.error(f"Error parsing travel plan: {e}, body: {item}")
                plans = list(filter(lambda x: x.legs, plans))
                plans = self.remove_duplicates(plans, max_candidates=settings.gtfs.max_trip_candidates)
                logger.debug(f"Payload: {json.dumps(payload, ensure_ascii=False)}, found {len(plans)} itineraries")
                return plans
            except Exception as e:
                logger.error(f"Failed to get itineraries after 5 attempts: {e}")
                return []


if __name__ == '__main__':
    import asyncio
    sth = OTPTripHelper(endpoint="http://localhost:8080/otp/transmodel/v3")
    loop = asyncio.get_event_loop()
    origin = Location(lon=1.53423130511658, lat=43.586655062927974)
    destination = Location(lon=1.486291134338381, lat=43.54970809807004)
    departure_time = 1742845000
    itineraries = loop.run_until_complete(sth.get_itineraries(origin, destination, departure_time))
    print(itineraries)
