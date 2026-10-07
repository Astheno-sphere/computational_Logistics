from jinja2 import Environment, FileSystemLoader
from helper import duration_to_bucket_text, format_route_id, humanize_time, humanize_duration, ensure_timestamp_in_seconds, time_to_bucket_text
from inputs.gtfs import GTFSData
from settings import settings
import os

env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'tpl')))

def to_timestamp(t: int) -> int:
    return ensure_timestamp_in_seconds(t)

gtfs_data = GTFSData.DEFAULT()
def get_transit_route_type(route_id: str) -> str:
    return gtfs_data.get_route_type_string_by_id(route_id)

def get_transit_route_name(route_id: str) -> str:
    return gtfs_data.get_route_long_name_by_id(route_id)

def get_transit_route_short_name(route_id: str) -> str:
    return gtfs_data.get_route_short_name_by_id(route_id)

env.filters['humanize_time'] = humanize_time
env.filters['humanize_duration'] = humanize_duration
env.filters['to_timestamp'] = to_timestamp
env.filters['get_transit_route_type'] = get_transit_route_type
env.filters['get_transit_route_long_name'] = get_transit_route_name
# env.filters['format_route_id'] = format_route_id
env.filters['format_route_id'] = get_transit_route_short_name
env.filters['duration_to_bucket_text'] = duration_to_bucket_text if settings.agent.quantify_time_window else humanize_duration
env.filters['time_to_bucket_text'] = time_to_bucket_text
env.filters['humanize_distance'] = lambda distance: f"{distance} meters" if distance else "Unknown distance"


tpl_describe_the_travel_plan = env.get_template('descriptions/travel_plan_describe_v2.j2')
tpl_describe_the_travel_plan_lite = env.get_template('descriptions/travel_plan_describe_lite.j2')
tpl_describe_the_ob_transit = env.get_template('descriptions/ob_transit.j2')
tpl_describe_the_ob_transfer = env.get_template('descriptions/ob_transfer.j2')
tpl_describe_the_ob_trip_feedback = env.get_template('descriptions/ob_trip_feedback.j2')
tpl_describe_the_ob_wait_in_stop = env.get_template('descriptions/ob_wait_in_stop.j2')
