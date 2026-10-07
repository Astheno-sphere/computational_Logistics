from collections import defaultdict
from typing import Optional
from scipy.sparse import coo_matrix
from inputs.gtfs.reader import GTFSData
from pydantic import BaseModel
import gtfs_kit.helpers as gh
import datetime
import tqdm
import json
import os

DURATION_24H = 24 * 60 * 60


class TripInfo(BaseModel):
    trip_id: str
    shape_id: str
    route_id: str
    service_id: str
    route_type: Optional[int] = None
    stop_times: list[tuple[int, int]]
    shape_index: Optional[int] = None
    shape_segments: Optional[list[int]] = None


class GamaGTFS:
    def __init__(self, gtfs_data: GTFSData):
        self.gtfs_data = gtfs_data

    @classmethod
    def load_data(cls, file_path: str):
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    
    def build_calendar_sparse_matrix(self):
        # TODO: this function only works for exception_type = 1 and empty calendar.txt
        calendar_dates = self.gtfs_data.calendar_dates
        # Build the matrix of service_id and date
        min_date = gh.datestr_to_date(calendar_dates['date'].min())
        max_date = gh.datestr_to_date(calendar_dates['date'].max())
        all_dates: list[datetime.datetime] = [min_date + datetime.timedelta(days=i) 
              for i in range((max_date - min_date).days + 1)]
        all_dates = sorted([date.strftime("%Y%m%d") for date in all_dates])
        _map_dates = {date: i for i, date in enumerate(all_dates)}
        all_service_ids = sorted(calendar_dates['service_id'].unique())
        # create matrix of 0 of size (len(all_service_ids), len(all_dates))
        row = []
        col = []
        grouped_service__calendar_dates = calendar_dates.groupby('service_id').agg({'date': list}).reset_index()
        for i, service_id in tqdm.tqdm(enumerate(all_service_ids), desc="Build Service-Calendar sparse matrix", total=len(all_service_ids)):
            all_dates_of_service = sorted(grouped_service__calendar_dates[grouped_service__calendar_dates['service_id'] == service_id]['date'].values[0])
            if all_dates_of_service:
                for date in all_dates_of_service:
                    row.append(i)
                    col.append(_map_dates[date])
        # Total number of elements
        total_elements = len(all_service_ids) * len(all_dates)
        non_zero = len(row)
        # Sparsity percentage
        sparsity = (1 - non_zero / total_elements) * 100
        print(f"Sparsity: {sparsity:.2f}%")

        return {
            "dates": all_dates,
            "service_ids": all_service_ids,
            "row": row,
            "col": col,
            "shape": (len(all_service_ids), len(all_dates)),
        }
    
    def build_calendar_binary_map(self):
        # TODO: this function only works for exception_type = 1 and empty calendar.txt
        calendar_dates = self.gtfs_data.calendar_dates
        # Build the matrix of service_id and date
        min_date = gh.datestr_to_date(calendar_dates['date'].min())
        max_date = gh.datestr_to_date(calendar_dates['date'].max())
        all_dates: list[datetime.datetime] = [min_date + datetime.timedelta(days=i) 
              for i in range((max_date - min_date).days + 1)]
        all_dates = sorted([date.strftime("%Y%m%d") for date in all_dates])
        assert len(all_dates) <= 64, f"Number of dates is too large to use binary map: {len(all_dates)}. Please use build_calendar_sparse_matrix instead."
        _map_dates = {date: i for i, date in enumerate(all_dates)}
        all_service_ids = sorted(calendar_dates['service_id'].unique())
        _map_service_ids = defaultdict(int)
        grouped_service__calendar_dates = calendar_dates.groupby('service_id').agg({'date': list}).reset_index()
        for i, service_id in tqdm.tqdm(enumerate(all_service_ids), desc="Build Service-Calendar sparse matrix", total=len(all_service_ids)):
            all_dates_of_service = sorted(grouped_service__calendar_dates[grouped_service__calendar_dates['service_id'] == service_id]['date'].values[0])
            if all_dates_of_service:
                for date in all_dates_of_service:
                    idx = _map_dates[date]
                    _map_service_ids[service_id] |= (1 << idx)
        # Total number of elements
        total_elements = len(all_service_ids) * len(all_dates)
        non_zero = len(calendar_dates)
        # Sparsity percentage
        sparsity = (1 - non_zero / total_elements) * 100
        print(f"Sparsity: {sparsity:.2f}%")

        return {
            "dates": all_dates,
            "data": _map_service_ids,
        }
        
    def build_trips(self, use_cache=True):
        # Build trips data from GTFS data to use in GAMA Platform
        trips = self.gtfs_data.trips.copy()
        routes = self.gtfs_data.routes
        trips = trips.merge(routes[['route_id', 'route_type']], on='route_id', how='left')

        stop_times = self.gtfs_data.stop_times[['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'shape_dist_traveled']]
        shapes = self.gtfs_data.shapes[['shape_id', 'shape_dist_traveled']]

        stop_times = stop_times.groupby('trip_id').agg(list).reset_index()
        shapes = shapes.groupby('shape_id').agg(list).reset_index()

        # We know for each (route_id, direction_id) pair, there is only one shape_id
        # we can cache the shape_segments for these pairs
        # to avoid recomputing them for each trip
        cache_ = {}
        shape_segments_list = []

        trip_list = []
        for _, trip in tqdm.tqdm(trips.iterrows(), total=len(trips)):
            trip_id = trip['trip_id']
            route_id = trip['route_id']
            shape_id = trip['shape_id']
            service_id = trip['service_id']

            # check if the shape segments are already cached
            cache_key = (shape_id, route_id, trip['direction_id'])
            shape_index = None
            if use_cache and cache_key in cache_:
                shape_index = cache_[cache_key]
            else:
                 # get the stop times for the trip
                arrival_time, departure_time, stop_dist_traveled_list = stop_times[stop_times['trip_id'] == trip_id][['arrival_time', 'departure_time', 'shape_dist_traveled']].values.tolist()[0]
                # convert time to int
                stop_times_list = [
                    (gh.timestr_to_seconds(arrival), gh.timestr_to_seconds(departure)) 
                    for arrival, departure in zip(arrival_time, departure_time)
                ]

                assert len(stop_dist_traveled_list) == len(stop_times_list), \
                    f"Stop times and shape distances do not match for trip {trip_id} with shape {shape_id}"

                # split the shape segments according to the stop times
                # stop_dist_traveled_list = stop_times[stop_times['trip_id'] == trip_id]['shape_dist_traveled'].iloc[0]
                shape_dist_traveled_list = shapes[shapes['shape_id'] == shape_id]['shape_dist_traveled'].iloc[0]

                # find the segments for the shape
                shape_segments = []
                idx = 0
                for stop_dist in stop_dist_traveled_list[1:]:
                    seg = []
                    for i in range(idx, len(shape_dist_traveled_list)):
                        seg.append(i)
                        idx = i
                        if shape_dist_traveled_list[i] >= stop_dist and len(seg) >= 2:
                            break
                    shape_segments.append(seg[-1])

                assert shape_segments[-1] == len(shape_dist_traveled_list) - 1, \
                    f"Shape segments do not match for trip {trip_id} with shape {shape_id}, calculated end at {seg[-1]}, expected {len(shape_dist_traveled_list) - 1}"
                    
                if use_cache:
                    shape_segments_list.append(shape_segments)
                    shape_index = len(shape_segments_list) - 1
                    cache_[cache_key] = shape_index

            if use_cache:
                assert len(shape_segments_list[shape_index]) == len(stop_times_list)-1, f"Shape segments and stop times do not match for trip {trip_id} with shape {shape_id}"

            trip_list.append(TripInfo(
                trip_id=trip_id,
                shape_id=shape_id,
                route_id=route_id,
                service_id=service_id,
                route_type=trip['route_type'],
                stop_times=stop_times_list,
                shape_index=shape_index,
                shape_segments=shape_segments,
            ))
            # break

        # sort the trip list by the start time
        trip_list.sort(key=lambda x: x.stop_times[0][0])

        return {
            'trip_list': trip_list,
            'shape_segments_list': shape_segments_list,
        }
    
    def build_data(self, use_cache=True):
        # Build the data for GAMA Platform
        print("Build trips data ...")
        trip_data = self.build_trips(use_cache=use_cache)
        print("Build calendar sparse matrix ...")
        calendar = self.build_calendar_binary_map()
        return {
            'trip_list': trip_data['trip_list'],
            'shape_segments_list': trip_data['shape_segments_list'],
            'calendar': calendar,
        }

if __name__ == '__main__':
    # Example usage
    gtfs = GTFSData.from_gtfs_files("../data/gtfs/")
    gama_gtfs = GamaGTFS(gtfs)
    trip_data = gama_gtfs.build_data(use_cache=False)
    trip_data['trip_list'] = [trip.model_dump() for trip in trip_data['trip_list']]

    output_dir = "../data/exports/gtfs/"
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, 'trip_info.json'), 'w') as f:
        json.dump(trip_data, f)
