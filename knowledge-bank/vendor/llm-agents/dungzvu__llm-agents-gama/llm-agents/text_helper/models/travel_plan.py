from collections import Counter
from text_helper.templates.repository import \
    get_transit_route_type, \
    tpl_describe_the_travel_plan, \
    tpl_describe_the_travel_plan_lite
from models import TravelPlan

class TravelPlanWrapper(TravelPlan):
    def describe(self) -> str:
        # Describe the trip feedback observation in a human-readable format
        return tpl_describe_the_travel_plan.render(
            plan=self,
        )
    
    @property
    def walking_time(self) -> int:
        return sum(leg.get_duration() for leg in self.legs if leg.is_transfer)
    
    @property
    def walking_distance(self) -> float:
        return sum(leg.get_distance() for leg in self.legs if leg.is_transfer)

    def summary(self) -> str:
        n_transits = len([leg for leg in self.legs if not leg.is_transfer])
        n_transfers = len(self.legs) - n_transits
        transit_types = [get_transit_route_type(leg.transit_route) for leg in self.legs if leg.transit_route]
        counter = Counter(transit_types)
        return f"{n_transits} transits, {n_transfers} transfers, including {', '.join([f'{v} {k}' for k, v in counter.items()])}"

    
class TravelPlanLiteWrapper(TravelPlanWrapper):
    def describe(self) -> str:
        # Describe the trip feedback observation in a human-readable format
        return tpl_describe_the_travel_plan_lite.render(
            plan=self
        )
    