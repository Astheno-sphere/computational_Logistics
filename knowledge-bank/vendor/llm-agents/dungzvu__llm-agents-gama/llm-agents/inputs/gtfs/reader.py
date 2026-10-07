from collections import defaultdict
from typing import Any
from pydantic import BaseModel
from models import BBox, Location
# from scipy.spatial import KDTree
import zipfile
import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
from settings import settings


STRING_COLUMNS = [
    'route_id', 'service_id', 'trip_id', 'shape_id', 'stop_id', 'date',
]


class Stop(BaseModel):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float


def _correct_color_hex_string(value):
    value = str(value)
    if value == 'nan':
        return "#222222"
    if value.startswith('#'):
        return value
    if len(value) == 6:
        return '#' + value
    if len(value) == 3:
        return '#' + ''.join([c * 2 for c in value])
    return value

class GTFSData:
    def __init__(self, **kwargs):
        self.stop_times = kwargs["stop_times"]
        self.stops = kwargs["stops"]
        self.routes = kwargs["routes"]
        self.trips = kwargs["trips"]
        self.shapes = kwargs["shapes"]
        self.calendar_dates = kwargs["calendar_dates"]
        self.calendar = kwargs["calendar"]
        
        # Init lookup maps
        self.init_route_lookup_maps()
        self.init_shape_lookup_maps()

        # init the KDTree for the stops
        # TODO: remove these lines, this is used for python RAPTOR implementation
        # which is deprecated
        # if kwargs.get("index_stop_area") is not True:
        #     self.indexed_stops_df = self.stops[self.stops['location_type'] != 1]
        # else:
        #     self.indexed_stops_df = self.stops.copy()
        # points = self.indexed_stops_df[['stop_lon', 'stop_lat']].values
        # points = points.astype(float)
        # self.stop_kdtree = KDTree(points)

    def init_route_lookup_maps(self):
        self.route_name_id_map = {
            str(row['route_short_name']): str(row['route_id'])
            for _, row in self.routes.iterrows()
        }

        self.route_id_map = {
            str(row['route_id']): {
                "route_short_name": str(row['route_short_name']),
                "route_long_name": str(row['route_long_name']),
                "route_type": settings.gtfs.gtfs_modality_name_map.get(str(row['route_type']), "Unknown"),
            }
            for _, row in self.routes.iterrows()
        }

    def init_shape_lookup_maps(self):
        stops = self.trips.groupby('shape_id').agg({
            'route_id': 'first',
            'trip_id': 'first',
        }).reset_index()\
        .merge(
            self.stop_times[['trip_id', 'stop_sequence', 'stop_id']],
            on='trip_id',
            how='left',
        ).merge(
            self.stops[['stop_id', 'stop_name']],
            on='stop_id',
            how='left',
        )

        m = defaultdict(dict)
        for _, row in stops.iterrows():
            if row['shape_id'] not in m[row['route_id']]:
                m[row['route_id']][row['shape_id']] = {}
            m[row['route_id']][row['shape_id']][row['stop_name']] = row['stop_sequence']
        self.route_id_shape_lookup_map = m

    def load_world_bounding_box(self) -> BBox:
        min_lon, min_lat, max_lon, max_lat = self.get_bounding_box()
        buffer = 0.05  # degrees ~ 5km
        return BBox(
            min_lon=min_lon - buffer,
            min_lat=min_lat - buffer,
            max_lon=max_lon + buffer,
            max_lat=max_lat + buffer,
        )

    def get_shape_id_from_route_info(self, route_id: str, from_stop_name: str, to_stop_name: str) -> list[str]:
        if route_id not in self.route_id_shape_lookup_map:
            raise ValueError(f"Route {route_id} not found")
        
        results = []
        for shape_id, stops in self.route_id_shape_lookup_map[route_id].items():
            if from_stop_name not in stops or to_stop_name not in stops:
                continue
            from_stop_seq = stops[from_stop_name]
            to_stop_seq = stops[to_stop_name]
            if from_stop_seq < to_stop_seq:
                results.append(shape_id)
        if not results:
            raise ValueError(f"Route {route_id} not found for stops {from_stop_name} and {to_stop_name}")
        return results

    def get_route_id_by_name(self, route_name: str) -> str:
        # Get the route id by route name
        if route_name in self.route_name_id_map:
            return self.route_name_id_map[route_name]
        raise ValueError(f"Route {route_name} not found")
    
    def get_route_type_string_by_id(self, route_id: str) -> str:
        return self.route_id_map.get(route_id, {}).get("route_type", "Unknown")
    
    def get_route_long_name_by_id(self, route_id: str) -> str:
        return self.route_id_map.get(route_id, {}).get("route_long_name", "Unknown")
    
    def get_route_short_name_by_id(self, route_id: str) -> str:
        return self.route_id_map.get(route_id, {}).get("route_short_name", "Unknown")

    def get_bounding_box(self) -> tuple[float, float, float, float]:
        # Get the bounding box of the stops
        min_lon = self.stops['stop_lon'].min()
        max_lon = self.stops['stop_lon'].max()
        min_lat = self.stops['stop_lat'].min()
        max_lat = self.stops['stop_lat'].max()
        return min_lon, min_lat, max_lon, max_lat

    # def get_nearest_stops(self, lon, lat, stops_count=5) -> tuple[list[Stop], list[float]]:
    #     # Find the nearest stops using KDTree
    #     distances, indices = self.stop_kdtree.query([lon, lat], k=stops_count)
    #     nearest_stops = self.indexed_stops_df.iloc[indices]
    #     stops = [Stop.model_validate(row) for row in nearest_stops.to_dict(orient="records")]
    #     return stops, distances
    
    def get_stop(self, stop_id: str) -> Stop:
        stop = self.stops[self.stops['stop_id'] == stop_id]
        if stop.empty:
            raise ValueError(f"Stop {stop_id} not found")
        stop = stop.iloc[0]
        return Stop.model_validate(stop.to_dict())
    
    def all_stop_locations(self) -> list[Location]:
        # Get all stop locations
        return [
            Location(lon=row['stop_lon'], lat=row['stop_lat'])
            for _, row in self.stops.iterrows()
        ]

    @classmethod
    def _read_gtfs_file_as_pd(cls, file):
        df = pd.read_csv(file, dtype={col: str for col in STRING_COLUMNS}, low_memory=False)
        return df

    @classmethod
    def read_df_from_zip(cls, zip_path, file_name):
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            if file_name in zip_ref.namelist():
                with zip_ref.open(file_name) as file:
                    df = cls._read_gtfs_file_as_pd(file)
                    return df
            else:
                raise ValueError(f"File {file_name} not found in {zip_path}")
            
    @classmethod
    def read_file(cls, dir, file_name):
        if not os.path.exists(dir):
            raise ValueError(f"Dir {dir} not found")
        
        if os.path.isdir(dir):
            with open(os.path.join(dir, file_name), 'r') as file:
                return cls._read_gtfs_file_as_pd(file)
        if os.path.isfile(dir) and dir.endswith('.zip'):
            return cls.read_df_from_zip(dir, file_name)
        
        raise ValueError(f"Dir {dir} is not a directory or a zip file")

    @classmethod
    def from_gtfs_files(cls, dir):
        data = GTFSData(**{
            # 'agency': read_file(dir, 'agency.txt'),
            'stops': cls.read_file(dir, 'stops.txt'),
            'shapes': cls.read_file(dir, 'shapes.txt'),
            'trips': cls.read_file(dir, 'trips.txt'),
            'stop_times': cls.read_file(dir, 'stop_times.txt'),
            'routes': cls.read_file(dir, 'routes.txt'),
            # TODO: support calendar.txt
            # for now, we pretend that all services are available, and calendar.txt file is empty
            'calendar_dates': cls.read_file(dir, 'calendar_dates.txt'),
            'calendar': cls.read_file(dir, 'calendar.txt'),
        })
        assert len(data.calendar) == 0, "calendar.txt is not supported yet"
        assert data.calendar_dates['exception_type'].unique().tolist() == [1], "calendar_dates.txt only supports exception_type = 1"

        return data
    
    @classmethod
    def DEFAULT(cls):
        # Get the GTFS data from the settings
        if not hasattr(cls, "_instance"):
            cls._instance = GTFSData.from_gtfs_files(settings.gtfs.gtfs_file)
        return cls._instance

    def to_stops_shape_file(self, output_path, crs=4326):
        stops_df = self.stops.copy()        
        routes_df = self.routes[['route_id', 'route_type']]
        trips_df = self.trips[['route_id', 'trip_id']]
        stop_times_df = self.stop_times[['stop_id', 'trip_id']]

        route_type_df = trips_df.merge(routes_df, on='route_id', how='left')
        stop_times_df = stop_times_df.merge(route_type_df, on='trip_id', how='left')
        stop_times_df = stop_times_df.groupby('stop_id').agg({'route_type': 'min'}).reset_index()

        stops_df = stops_df[['stop_id', 'stop_name', 'location_type', 'wheelchair_boarding', 'stop_lon', 'stop_lat']]
        stops_df = stops_df.merge(stop_times_df[['stop_id', 'route_type']], on='stop_id', how='left')
        # stops_df['route_type'] = stops_df['route_type'].fillna(-1).astype(float)
        stops_df.dropna(subset=['route_type'], inplace=True)
        gdf = gpd.GeoDataFrame(
            stops_df, geometry=gpd.points_from_xy(stops_df['stop_lon'], stops_df['stop_lat'], z=0)
        )
        gdf.set_crs(epsg=crs, inplace=True)

        gdf.drop(columns=['stop_lon', 'stop_lat'], inplace=True)

        # Save as Shapefile
        gdf.to_file(os.path.join(output_path, 'stops.shp'))
        gdf.to_file(os.path.join(output_path, 'stops.geojson'), driver='GeoJSON')

    def to_route_shape_file(self, output_path, crs=4326):
        shapes_df = self.shapes
        routes_df = self.routes
        trips_df = self.trips

        shapes_list = shapes_df.groupby("shape_id").apply(
            lambda l: LineString(zip(l['shape_pt_lon'], l['shape_pt_lat']))
        )
        shapes_all = pd.DataFrame({
            'shape_id': shapes_list.index,
            'geometry': shapes_list.values
        })
        
        trips_df = trips_df[['route_id', 'service_id', 'trip_id', 'shape_id']].groupby("shape_id").agg(lambda x: x.iloc[0])
        shapes_all = shapes_all.merge(trips_df, on='shape_id', how='left')
        shapes_all = shapes_all.merge(routes_df, on='route_id', how='left')

        # compact the column names
        shapes_all.rename(columns={
            'shape_id': 'shape_id',
            'route_id': 'route_id',
            'service_id': 'service_id',
            'trip_id': 'trip_id',
            'route_short_name': 'short_name',
            'route_long_name': 'long_name',
            'route_color': 'color',
            'route_text_color': 'text_color',
            'route_type': 'route_type',
        }, inplace=True)

        # correct the color hex string
        shapes_all['color'] = shapes_all['color'].apply(_correct_color_hex_string)
        shapes_all['text_color'] = shapes_all['text_color'].apply(_correct_color_hex_string)

        gdf = gpd.GeoDataFrame(shapes_all)
        gdf.set_crs(epsg=crs, inplace=True)

        # Save as Shapefile
        gdf.to_file(os.path.join(output_path, 'routes.shp'))
        gdf.to_file(os.path.join(output_path, 'routes.geojson'), driver='GeoJSON')


if __name__ == '__main__':
    gtfs = GTFSData.from_gtfs_files("../data/gtfs/")

    output_dir = "../data/exports/gtfs/"
    os.makedirs(output_dir, exist_ok=True)
    gtfs.to_stops_shape_file(output_dir)
    gtfs.to_route_shape_file(output_dir)
