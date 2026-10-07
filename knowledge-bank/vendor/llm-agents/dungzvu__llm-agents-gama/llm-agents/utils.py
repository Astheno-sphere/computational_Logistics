from faker import Faker
from pyproj import Transformer
from models import Location
from settings import settings

fake = Faker("fr_FR")

def random_name():
    return fake.name()

def random_uuid():
    return fake.uuid4()

def random_choices(elements, length):
    return fake.random_choices(
        elements=elements,
        length=length,
    )

transformer = Transformer.from_crs(settings.world.geo_crs, settings.world.geo_projection) 
def world_projection(location: Location) -> tuple[float, float]:
    """
    Project a point from WGS84 to Web Mercator
    """
    return transformer.transform(location.lon, location.lat)

def square_distance(p1: Location, p2: Location) -> float:
    """
    Calculate the square distance between two points
    """
    x1, y1 = world_projection(p1)
    x2, y2 = world_projection(p2)
    return (x1 - x2) ** 2 + (y1 - y2) ** 2    

def get_json_part(text: str) -> str:
    """
    Extract the JSON part from a string
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    return text[start:end + 1]
