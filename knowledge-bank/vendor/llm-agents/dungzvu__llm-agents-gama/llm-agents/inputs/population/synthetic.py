import json
import random
from typing import Optional
from faker import Faker
import os
import pandas as pd
import numpy as np
import geopandas as gpd
from settings import settings
from models import Activity, Location, Person, PersonalIdentity, BBox
from inputs.population.base import Filter, PopulationLoader
from utils import random_uuid

NAN_TIME_VALUE = -1
fake = Faker("fr_FR")

TRAIT_FILE_PATH = os.path.join(os.path.dirname(__file__), "traits.json")

def generate_name_by_gender(gender):
    gender = gender.lower()
    if gender == 'male':
        return fake.name_male()
    elif gender == 'female':
        return fake.name_female()
    return fake.name()

class SyntheticPopulationLoader(PopulationLoader):
    def __init__(self, filters: Optional[list[Filter]] = None):
        self.filters = filters
        
    def make_sure_time_valid(self, time) -> float:
        if np.isnan(time):
            return NAN_TIME_VALUE
        return float(time)
    
    @classmethod
    def merge_duplicated_activities(cls, activities: list[Activity]) -> list[Activity]:
        l = []
        cur = None
        for activity in activities:
            if cur is None or cur.purpose != activity.purpose:
                cur = activity
                l.append(cur)
                continue
            cur.end_time = max(cur.end_time, activity.end_time)
        return l
    
    def load_population(self, max_size: int, bbox: Optional[BBox]=None) -> list[Person]:
        persons_df = pd.read_csv(
            os.path.join(settings.data.synthetic_dir, f"{settings.data.synthetic_file_prefix}persons.csv"),
            delimiter=';',
        )
        if max_size is None:
            size = len(persons_df)
        else:
            size = min(max_size, len(persons_df))

        households_df = pd.read_csv(
            os.path.join(settings.data.synthetic_dir, f"{settings.data.synthetic_file_prefix}households.csv"),
            delimiter=';',
        )
        activities_df = gpd.read_file(
            os.path.join(settings.data.synthetic_dir, f"{settings.data.synthetic_file_prefix}activities.gpkg"),
        ).to_crs(settings.world.geo_crs)

        if bbox is not None:
            activities_df = activities_df.cx[bbox.min_lon:bbox.max_lon, bbox.min_lat:bbox.max_lat]
            person_ids = activities_df[activities_df["purpose"] == "home"]["person_id"].unique()
            persons_df = persons_df[persons_df["person_id"].isin(person_ids)]

        # if size < len(persons_df):
        #     persons_df = persons_df.sample(size, random_state=1)

        persons_df = persons_df.merge(households_df, on="household_id")

        traits = json.load(open(TRAIT_FILE_PATH))  

        people_dict = {}
        for _, row in persons_df.iterrows():
            trait = random.choice(traits)
            trait = json.loads(json.dumps(trait, ensure_ascii=False))
            trait["name"] = generate_name_by_gender(trait["gender"])
            person = Person(
                person_id=str(row["person_id"]),
                identity=PersonalIdentity(
                    name=trait["name"],
                    traits_json=trait,
                    activities=[],
                ),
                purpose="home",
            )
            people_dict[person.person_id] = person

        # Append activities to people
        for _, row in activities_df.iterrows():
            person_id = str(row["person_id"])
            if person_id not in people_dict:
                continue
            person = people_dict[person_id]
            activity = Activity(
                id=random_uuid(),
                start_time=self.make_sure_time_valid(row["start_time"]),
                end_time=self.make_sure_time_valid(row["end_time"]),
                purpose=row["purpose"],
                location=Location(
                    lon=row["geometry"].x, lat=row["geometry"].y),
            )
            if activity.purpose == "home":
                people_dict[person_id].identity.home = activity.location
            if activity.purpose == "other":
                continue
            person.identity.activities.append(activity)
        # Merge duplicated activities
        for person in people_dict.values():
            person.identity.activities = self.merge_duplicated_activities(person.identity.activities)
            person.identity.activities.sort(key=lambda x: x.start_time)

        people = list(people_dict.values())

        # Require people with at least 3 activities
        people = [
            person for person in people 
            if len(person.identity.activities) > 3 and \
                next((activity for activity in person.identity.activities if activity.purpose in ["work", "education"]), None)
        ]

        # Apply filter if provided
        if self.filters is not None:
            for filter in self.filters:
                before_len = len(people)
                people = [person for person in people if filter.is_valid(person)]
                print(f"Filtered {before_len - len(people)} people by filter {filter.__class__.__name__}, total remaining: {len(people)}")

        if size < len(people):
            people = np.random.choice(people, size, replace=False)

        print(f"Loaded {len(people)} people from synthetic population data")

        return people
