import numpy as np
from scipy.spatial import cKDTree
from inputs.population.base import Filter
from models import Location
from utils import world_projection


class PersonCloseToTheStopFilter(Filter):
    def __init__(self, max_distance: float, stop_locations: list[Location]):
        self.max_distance = max_distance
        self.stop_locations = stop_locations

        points = [np.array(world_projection(stop)) for stop in stop_locations]
        self.tree = cKDTree(points)

    def is_valid(self, person) -> bool:
        activitie_locations = [world_projection(activity.location) for activity in person.identity.activities if activity.location]
        for loc in activitie_locations:
            cands = self.tree.query_ball_point(loc, self.max_distance)
            if not cands:
                return False
        return True
