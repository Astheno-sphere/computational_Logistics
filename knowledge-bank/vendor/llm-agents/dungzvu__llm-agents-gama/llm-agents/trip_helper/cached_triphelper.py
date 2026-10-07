from collections import defaultdict
import os
import pickle
from trip_helper import TripHelper
from models import Location, TravelPlan
from world import WorldModel
from utils import square_distance, random_uuid
from settings import settings
from loguru import logger
import asyncio

class CachedTripHelper(TripHelper):
    def __init__(self, 
                 world_model: WorldModel,
                 trip_helper: TripHelper):
        super().__init__()
        self.trip_helper = trip_helper
        self.world_grid = world_model.world_grid
        self.time_grid = world_model.time_grid
        self.cache_size_per_grid = settings.gtfs.n_trip_in_grid  # max number of results per grid cell
        # cache top k results for each origin-destination pair
        if settings.gtfs.solari_cache_file and os.path.exists(settings.gtfs.solari_cache_file):
            with open(settings.gtfs.solari_cache_file, 'rb') as f:
                self.cache = pickle.load(f)
        else:
            self.cache = defaultdict(list)
        self.recursion_search_depth = settings.gtfs.recursion_search_depth
        self.max_transfers = 5
        # blacklist pair of (orig, dest) if no route is found, avoid to spam the GTFS server
        self.blacklist = set()
        # cache statistics
        self.cache_enabled = settings.gtfs.cache_enabled
        self._stats_cache_hit = (0, 0)
        self._stats_new_cache = 0
        self._dump_cache_after = 10000
        self._cache_last_hour = None
        self._cache_duration = 900 # 15 minutes cache duration
        self._notfound_cache_last_hour = None
        self._notfound_cache_duration = 1800  # 30 minutes cache duration for not found itineraries

        if not self.cache_enabled:
            logger.warning("[CachedTripHelper]: Cache is disabled, all requests will go to the trip_helper directly.")

        # choose the strategy based on settings
        if settings.gtfs.recursion_search_depth > 0:
            logger.warning(f"[CachedTripHelper]: Using recursive search strategy with depth {settings.gtfs.recursion_search_depth}")
            self.do_get_iteraries = self.do_get_iteraries_v1
        else:
            logger.warning(f"[CachedTripHelper]: Using time-range expanded based search strategy")
            self.do_get_iteraries = self.do_get_iteraries_v2

    def dump_cache_to_file(self):
        # cache_file = settings.gtfs.solari_cache_file

        # with open(cache_file, 'wb') as f:
        #     pickle.dump(self.cache, f)  
        # logger.info(f"Cache dumped to {cache_file}")
        # TODO: don't need to dump cache
        pass

    def get_unique_itineraries(self, itineraries: list[TravelPlan]) -> list[TravelPlan]:
        """
        Get unique itineraries by comparing the start and end locations, and the legs of the itinerary.
        """
        unique_itineraries = {}
        for it in itineraries:
            transits = [leg for leg in it.legs if not leg.is_transfer]
            key = (tuple((leg.transit_route, leg.start_location.stop, leg.end_location.stop) for leg in transits))
            if key not in unique_itineraries:
                unique_itineraries[key] = it
        return list(unique_itineraries.values())
    
    def is_circular_route(self, itinerary: TravelPlan) -> bool:
        """
        Check if the itinerary is circular, meaning the start and end locations are the same.
        """
        all_transits = [leg for leg in itinerary.legs if not leg.is_transfer]
        keys = [
            (leg.start_location.stop, leg.end_location.stop, leg.transit_route)
            for leg in all_transits
        ]
        return len(set(keys)) < len(keys)  # if there are duplicates, it's circular
    
    async def do_get_iteraries_v2(self, origin: Location, destination: Location, departure_time: int) -> list[TravelPlan]:
        max_transfers = self.max_transfers
        time_step = settings.world.time_step
        departure_time = departure_time // time_step * time_step  # round down to the nearest time step
        tasks = []
        for i in settings.gtfs.trip_query_range:
            adjusted_time = departure_time + i * 60
            tasks.append(
                self.trip_helper.get_itineraries(
                    origin=origin,
                    destination=destination,
                    departure_time=adjusted_time,
                    max_transfers=max_transfers
                )
            )
        results = await asyncio.gather(*tasks)

        # Get max candidates from all results
        bl = set()
        rs = []
        for plan in [plan for plans in results for plan in plans]:
            code = plan.get_code()
            if code in bl:
                continue
            bl.add(code)
            rs.append(plan)
            if len(rs) >= settings.gtfs.max_trip_candidates:
                break

        itineraries = rs
        logger.debug(f"[CachedTripHelper]: Number of calls to trip_helper: {5}, ")
        return itineraries

    async def do_get_iteraries_v1(self,
                               origin: Location,
                               destination: Location,
                               departure_time: int) -> list[TravelPlan]:
        max_transfers = self.max_transfers
        recursion_search_depth = self.recursion_search_depth
        itineraries: list[TravelPlan] = await self.trip_helper.get_itineraries(origin, destination, departure_time, max_transfers=max_transfers)
        if not itineraries:
            return []
        
        _stats_number_of_calls = 1
        
        first_index = -1
        while recursion_search_depth > 0 and max_transfers > 2:
            # Itinerary includes transfers and transits. For example if the itinerary has 3 transits, for each depth
            # we will try to keep the previous transits and find new ways from this transit to the destination, then 
            # combine them together.
            new_itineraries = []
            max_transfers -= 1
            recursion_search_depth -= 1
            first_index += 1

            tasks = []
            for it in itineraries:
                # find the first transit in the itinerary
                all_transits = [leg for leg in it.legs if not leg.is_transfer]
                if len(all_transits) <= first_index:
                    continue
                first_transit = all_transits[first_index]

                # find the index of the first transit
                first_transit_index = it.legs.index(first_transit)
                # prepare the coroutine for concurrent execution
                tasks.append((
                    it,
                    first_transit_index,
                    self.trip_helper.get_itineraries(
                        origin=first_transit.end_location,
                        destination=destination,
                        departure_time=first_transit.end_time // 1000,  # convert to seconds
                        max_transfers=max_transfers
                    )
                ))

            # Run all get_itineraries concurrently
            results = await asyncio.gather(*(task[2] for task in tasks))
            _stats_number_of_calls += len(results)

            for (it, first_transit_index, _), new_ways in zip(tasks, results):
                if not new_ways:
                    continue
                for new_way in new_ways:
                    # combine the first part of the itinerary with the new way
                    combined_itinerary = TravelPlan(
                        id=random_uuid(),
                        start_location=it.start_location,
                        end_location=new_way.end_location,
                        start_time=it.start_time,
                        end_time=new_way.end_time,
                        legs=it.legs[:first_transit_index] + new_way.legs
                    )
                    if not self.is_circular_route(combined_itinerary):
                        new_itineraries.append(combined_itinerary)
                
            # merge all itineraries
            itineraries = self.get_unique_itineraries(new_itineraries + itineraries)

        logger.debug(f"[CachedTripHelper]: Number of calls to trip_helper: {_stats_number_of_calls}, ")
            
        return itineraries

    async def get_itineraries(self,
                              origin: Location,
                              destination: Location, 
                              departure_time: int) -> list[TravelPlan]:
        grid_origin = self.world_grid.get_location_grid(origin)
        grid_destination = self.world_grid.get_location_grid(destination)
        time_slot = self.time_grid.get_time_slot(departure_time)

        # Only save cache for the current hour, because the GTFS data is updated hourly
        day_and_hour = departure_time // self._cache_duration # e.g. 15 minutes cache duration
        if self._cache_last_hour is None or self._cache_last_hour != day_and_hour:
            self.cache.clear()
            logger.debug(f"[CachedTripHelper]: Cache cleared for new hour {day_and_hour}")
        self._cache_last_hour = day_and_hour

        day_and_hour = departure_time // self._notfound_cache_duration  # e.g. 30 minutes cache duration for not found itineraries
        if self._notfound_cache_last_hour is None or self._notfound_cache_last_hour != day_and_hour:
            self.blacklist.clear()
            logger.debug(f"[CachedTripHelper]: Blacklist cleared for new hour {day_and_hour}")
        self._notfound_cache_last_hour = day_and_hour

        key = "_".join([str(it) for it in (*grid_origin, *grid_destination, time_slot, day_and_hour)])
        bl_key = (origin.lon, origin.lat, destination.lon, destination.lat)

        cache_hit = self.cache_enabled
        cache_hit = cache_hit and (key not in self.cache or len(self.cache[key]) < self.cache_size_per_grid)
        cache_hit = cache_hit and (bl_key not in self.blacklist)

        if not cache_hit:
            itineraries = await self.do_get_iteraries(origin, destination, departure_time)
            if itineraries:
                # identify each itinerary with a unique id
                for it in itineraries:
                    it.id = random_uuid()
                self.cache[key].append({
                    'id': random_uuid(),
                    'origin': origin,
                    'destination': destination,
                    'departure_time': departure_time,
                    'itineraries': itineraries,
                })
                self.cache[key] = self.cache[key][:self.cache_size_per_grid]
                self._stats_cache_hit = (self._stats_cache_hit[0], self._stats_cache_hit[1] + 1)
                self._stats_new_cache += 1
            else:
                self.blacklist.add(bl_key)
        else:
            self._stats_cache_hit = (self._stats_cache_hit[0] + 1, self._stats_cache_hit[1] + 1)
            logger.debug(f"[CachedTripHelper]: Cache hit for key {key}, ratio: {self._stats_cache_hit[0] / self._stats_cache_hit[1]:.2f}")

        # Dump cache if needed
        if self._stats_new_cache >= self._dump_cache_after:
            self._stats_new_cache = 0
            self.dump_cache_to_file()

        # Find the closest itinerary to the origin and destination
        candidates = self.cache.get(key, [])
        if not candidates:
            return []
        candidates = sorted(candidates, key=lambda x: (square_distance(x['origin'], origin), square_distance(x['destination'], destination)))
        itineraries = candidates[0]['itineraries']

        # Modify the start and end location of the itinerary
        for itinerary in itineraries:
            itinerary.start_location = origin
            itinerary.end_location = destination
            # patch the all time values
            departure_time_ms = departure_time * 1000
            dt = departure_time_ms - itinerary.start_time
            itinerary.start_time = departure_time_ms
            itinerary.end_time = itinerary.end_time + dt
            for leg in itinerary.legs:
                leg.start_time = leg.start_time + dt
                leg.end_time = leg.end_time + dt

        return itineraries
