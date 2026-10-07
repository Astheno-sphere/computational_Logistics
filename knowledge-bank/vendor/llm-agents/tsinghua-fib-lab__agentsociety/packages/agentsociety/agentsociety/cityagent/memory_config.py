import random
from collections import deque
from typing import Optional

import numpy as np

from ..agent.distribution import (
    ChoiceDistribution,
    Distribution,
    UniformIntDistribution,
    sample_field_value,
)
from ..agent.memory_config_generator import MemoryConfig, MemoryAttribute
from ..environment.economy import EconomyEntityType

pareto_param = 8
payment_max_skill_multiplier_base = 950
payment_max_skill_multiplier = float(payment_max_skill_multiplier_base)
pmsm = payment_max_skill_multiplier
pareto_samples = np.random.pareto(pareto_param, size=(1000, 10))
clipped_skills = np.minimum(pmsm, (pmsm - 1) * pareto_samples + 1)
sorted_clipped_skills = np.sort(clipped_skills, axis=1)
agent_skills = list(sorted_clipped_skills.mean(axis=0))

__all__ = [
    "memory_config_societyagent",
    "memory_config_firm",
    "memory_config_government",
    "memory_config_bank",
    "memory_config_nbs",
    "DEFAULT_DISTRIBUTIONS",
]


# Default distributions for different profile fields
DEFAULT_DISTRIBUTIONS: dict[str, Distribution] = {
    "name": ChoiceDistribution(
        choices=[
            "Alice",
            "Bob",
            "Charlie",
            "David",
            "Eve",
            "Frank",
            "Grace",
            "Helen",
            "Ivy",
            "Jack",
            "Kelly",
            "Lily",
            "Mike",
            "Nancy",
            "Oscar",
            "Peter",
            "Queen",
            "Rose",
            "Sam",
            "Tom",
            "Ulysses",
            "Vicky",
            "Will",
            "Xavier",
            "Yvonne",
            "Zack",
        ]
    ),
    "gender": ChoiceDistribution(choices=["Male", "Female"]),
    "age": UniformIntDistribution(min_value=18, max_value=65),
    "education": ChoiceDistribution(
        choices=["Doctor", "Master", "Bachelor", "College", "High School"]
    ),
    "occupation": ChoiceDistribution(
        choices=[
            "Student",
            "Teacher",
            "Doctor",
            "Engineer",
            "Manager",
            "Businessman",
            "Artist",
            "Athlete",
            "Other",
        ]
    ),
    "marriage_status": ChoiceDistribution(
        choices=["Not married", "Married", "Divorced", "Widowed"]
    ),
}


def memory_config_societyagent(
    distributions: dict[str, Distribution],
    class_config: Optional[list[MemoryAttribute]] = None,
) -> MemoryConfig:
    """Generate memory configuration for society agents."""
    attributes = {
        "type": MemoryAttribute(
            name="type",
            type=str,
            default_or_value="citizen",
            description="agent type",
            whether_embedding=False,
        ),
        # Needs Model
        "hunger_satisfaction": MemoryAttribute(
            name="hunger_satisfaction",
            type=float,
            default_or_value=0.9,
            description="hunger satisfaction",
            whether_embedding=False,
        ),
        "energy_satisfaction": MemoryAttribute(
            name="energy_satisfaction",
            type=float,
            default_or_value=0.9,
            description="energy satisfaction",
            whether_embedding=False,
        ),
        "safety_satisfaction": MemoryAttribute(
            name="safety_satisfaction",
            type=float,
            default_or_value=0.4,
            description="safety satisfaction",
            whether_embedding=False,
        ),
        "social_satisfaction": MemoryAttribute(
            name="social_satisfaction",
            type=float,
            default_or_value=0.6,
            description="social satisfaction",
            whether_embedding=False,
        ),
        "current_need": MemoryAttribute(
            name="current_need",
            type=str,
            default_or_value="none",
            description="current need",
            whether_embedding=False,
        ),
        # Plan Behavior Model
        "current_plan": MemoryAttribute(
            name="current_plan",
            type=dict,
            default_or_value={},
            description="current plan",
            whether_embedding=False,
        ),
        "execution_context": MemoryAttribute(
            name="execution_context",
            type=dict,
            default_or_value={},
            description="execution context",
            whether_embedding=False,
        ),
        "plan_history": MemoryAttribute(
            name="plan_history",
            type=list,
            default_or_value=[],
            description="plan history",
            whether_embedding=False,
        ),
        # cognition
        "emotion": MemoryAttribute(
            name="emotion",
            type=dict,
            default_or_value={
                "sadness": 5,
                "joy": 5,
                "fear": 5,
                "disgust": 5,
                "anger": 5,
                "surprise": 5,
            },
            description="emotion state",
            whether_embedding=False,
        ),
        "attitude": MemoryAttribute(
            name="attitude",
            type=dict,
            default_or_value={},
            description="attitude",
            whether_embedding=True,
        ),
        "thought": MemoryAttribute(
            name="thought",
            type=str,
            default_or_value="Currently nothing good or bad is happening",
            description="current thought",
            whether_embedding=True,
        ),
        "emotion_types": MemoryAttribute(
            name="emotion_types",
            type=str,
            default_or_value="Relief",
            description="emotion types",
            whether_embedding=True,
        ),
        # economy
        "work_skill": MemoryAttribute(
            name="work_skill",
            type=float,
            default_or_value=random.choice(agent_skills),
            description="work skill",
            whether_embedding=True,
        ),
        "tax_paid": MemoryAttribute(
            name="tax_paid",
            type=float,
            default_or_value=0.0,
            description="tax paid",
            whether_embedding=False,
        ),
        "consumption_currency": MemoryAttribute(
            name="consumption_currency",
            type=float,
            default_or_value=0.0,
            description="consumption currency",
            whether_embedding=False,
        ),
        "goods_demand": MemoryAttribute(
            name="goods_demand",
            type=int,
            default_or_value=0,
            description="goods demand",
            whether_embedding=False,
        ),
        "goods_consumption": MemoryAttribute(
            name="goods_consumption",
            type=int,
            default_or_value=0,
            description="goods consumption",
            whether_embedding=False,
        ),
        "work_propensity": MemoryAttribute(
            name="work_propensity",
            type=float,
            default_or_value=0.0,
            description="work propensity",
            whether_embedding=False,
        ),
        "consumption_propensity": MemoryAttribute(
            name="consumption_propensity",
            type=float,
            default_or_value=0.0,
            description="consumption propensity",
            whether_embedding=False,
        ),
        "to_consumption_currency": MemoryAttribute(
            name="to_consumption_currency",
            type=float,
            default_or_value=0.0,
            description="to consumption currency",
            whether_embedding=False,
        ),
        "firm_id": MemoryAttribute(
            name="firm_id",
            type=int,
            default_or_value=0,
            description="firm id",
            whether_embedding=False,
        ),
        "government_id": MemoryAttribute(
            name="government_id",
            type=int,
            default_or_value=0,
            description="government id",
            whether_embedding=False,
        ),
        "bank_id": MemoryAttribute(
            name="bank_id",
            type=int,
            default_or_value=0,
            description="bank id",
            whether_embedding=False,
        ),
        "nbs_id": MemoryAttribute(
            name="nbs_id",
            type=int,
            default_or_value=0,
            description="nbs id",
            whether_embedding=False,
        ),
        "dialog_queue": MemoryAttribute(
            name="dialog_queue",
            type=deque,
            default_or_value=deque(maxlen=3),
            description="dialog queue",
            whether_embedding=False,
        ),
        "firm_forward": MemoryAttribute(
            name="firm_forward",
            type=int,
            default_or_value=0,
            description="firm forward",
            whether_embedding=False,
        ),
        "bank_forward": MemoryAttribute(
            name="bank_forward",
            type=int,
            default_or_value=0,
            description="bank forward",
            whether_embedding=False,
        ),
        "nbs_forward": MemoryAttribute(
            name="nbs_forward",
            type=int,
            default_or_value=0,
            description="nbs forward",
            whether_embedding=False,
        ),
        "government_forward": MemoryAttribute(
            name="government_forward",
            type=int,
            default_or_value=0,
            description="government forward",
            whether_embedding=False,
        ),
        "forward": MemoryAttribute(
            name="forward",
            type=int,
            default_or_value=0,
            description="forward",
            whether_embedding=False,
        ),
        "depression": MemoryAttribute(
            name="depression",
            type=float,
            default_or_value=0.0,
            description="depression",
            whether_embedding=False,
        ),
        "ubi_opinion": MemoryAttribute(
            name="ubi_opinion",
            type=list,
            default_or_value=[],
            description="ubi opinion",
            whether_embedding=False,
        ),
        "working_experience": MemoryAttribute(
            name="working_experience",
            type=list,
            default_or_value=[],
            description="working experience",
            whether_embedding=False,
        ),
        "work_hour_month": MemoryAttribute(
            name="work_hour_month",
            type=float,
            default_or_value=160,
            description="work hour month",
            whether_embedding=False,
        ),
        "work_hour_finish": MemoryAttribute(
            name="work_hour_finish",
            type=float,
            default_or_value=0,
            description="work hour finish",
            whether_embedding=False,
        ),
        # social
        "friends": MemoryAttribute(
            name="friends",
            type=list,
            default_or_value=[],
            description="friends list",
            whether_embedding=False,
        ),
        "public_friends": MemoryAttribute(
            name="public_friends",
            type=list,
            default_or_value=[],
            description="public friends list",
            whether_embedding=False,
        ),
        "relationships": MemoryAttribute(
            name="relationships",
            type=dict,
            default_or_value={},
            description="relationship strength with each friend",
            whether_embedding=False,
        ),
        "relation_types": MemoryAttribute(
            name="relation_types",
            type=dict,
            default_or_value={},
            description="relation types",
            whether_embedding=False,
        ),
        "chat_histories": MemoryAttribute(
            name="chat_histories",
            type=dict,
            default_or_value={},
            description="all chat histories",
            whether_embedding=False,
        ),
        "interactions": MemoryAttribute(
            name="interactions",
            type=dict,
            default_or_value={},
            description="all interaction records",
            whether_embedding=False,
        ),
        # mobility
        "number_poi_visited": MemoryAttribute(
            name="number_poi_visited",
            type=int,
            default_or_value=1,
            description="number of poi visited",
            whether_embedding=False,
        ),
        "location_knowledge": MemoryAttribute(
            name="location_knowledge",
            type=dict,
            default_or_value={},
            description="location knowledge",
            whether_embedding=False,
        ),
    }

    # Add profile attributes
    profile_attributes = {
        "name": MemoryAttribute(
            name="name",
            type=str,
            default_or_value=sample_field_value(distributions, "name"),
            description="agent's name",
            whether_embedding=True,
        ),
        "gender": MemoryAttribute(
            name="gender",
            type=str,
            default_or_value=sample_field_value(distributions, "gender"),
            description="agent's gender",
            whether_embedding=True,
        ),
        "age": MemoryAttribute(
            name="age",
            type=int,
            default_or_value=sample_field_value(distributions, "age"),
            description="agent's age group",
            whether_embedding=True,
        ),
        "education": MemoryAttribute(
            name="education",
            type=str,
            default_or_value=sample_field_value(distributions, "education"),
            description="agent's education level",
            whether_embedding=True,
        ),
        "skill": MemoryAttribute(
            name="skill",
            type=str,
            default_or_value="unknown",
            description="agent's skills",
            whether_embedding=True,
        ),
        "occupation": MemoryAttribute(
            name="occupation",
            type=str,
            default_or_value=sample_field_value(distributions, "occupation"),
            description="agent's occupation",
            whether_embedding=True,
        ),
        "family_consumption": MemoryAttribute(
            name="family_consumption",
            type=str,
            default_or_value="unknown",
            description="agent's family consumption pattern",
            whether_embedding=True,
        ),
        "consumption": MemoryAttribute(
            name="consumption",
            type=str,
            default_or_value="unknown",
            description="agent's consumption pattern",
            whether_embedding=True,
        ),
        "personality": MemoryAttribute(
            name="personality",
            type=str,
            default_or_value="unknown",
            description="agent's personality",
            whether_embedding=True,
        ),
        "income": MemoryAttribute(
            name="income",
            type=float,
            default_or_value=5000,
            description="agent's income",
            whether_embedding=True,
        ),
        "currency": MemoryAttribute(
            name="currency",
            type=float,
            default_or_value=30000,
            description="agent's currency",
            whether_embedding=True,
        ),
        "residence": MemoryAttribute(
            name="residence",
            type=str,
            default_or_value="unknown",
            description="agent's residence",
            whether_embedding=True,
        ),
        "city": MemoryAttribute(
            name="city",
            type=str,
            default_or_value="unknown",
            description="agent's city",
            whether_embedding=True,
        ),
        "race": MemoryAttribute(
            name="race",
            type=str,
            default_or_value="unknown",
            description="agent's race",
            whether_embedding=True,
        ),
        "religion": MemoryAttribute(
            name="religion",
            type=str,
            default_or_value="unknown",
            description="agent's religion",
            whether_embedding=True,
        ),
        "marriage_status": MemoryAttribute(
            name="marriage_status",
            type=str,
            default_or_value=sample_field_value(distributions, "marriage_status"),
            description="agent's marriage status",
            whether_embedding=True,
        ),
        "background_story": MemoryAttribute(
            name="background_story",
            type=str,
            default_or_value="No background story",
            description="agent's background story",
            whether_embedding=True,
        ),
    }

    # Add base attributes
    base_attributes = {
        "home": MemoryAttribute(
            name="home",
            type=dict,
            default_or_value={
                "aoi_position": {
                    "aoi_id": sample_field_value(distributions, "home_aoi_id")
                }
            },
            description="agent's home location",
            whether_embedding=False,
        ),
        "work": MemoryAttribute(
            name="work",
            type=dict,
            default_or_value={
                "aoi_position": {
                    "aoi_id": sample_field_value(distributions, "work_aoi_id")
                }
            },
            description="agent's work location",
            whether_embedding=False,
        ),
    }

    # Merge all attributes
    all_attributes = {**attributes, **profile_attributes, **base_attributes}

    # Add class-specific attributes if provided
    if class_config:
        for attr in class_config:
            if attr.name in all_attributes:
                continue
            all_attributes[attr.name] = attr

    return MemoryConfig(attributes=all_attributes)


def memory_config_firm(
    distributions: dict[str, Distribution],
    class_config: Optional[list[MemoryAttribute]] = None,
) -> MemoryConfig:
    """Generate memory configuration for firm agents."""
    attributes = {
        "type": MemoryAttribute(
            name="type",
            type=int,
            default_or_value=EconomyEntityType.Firm,
            description="agent type",
            whether_embedding=False,
        ),
        "location": MemoryAttribute(
            name="location",
            type=dict,
            default_or_value={
                "aoi_position": {
                    "aoi_id": sample_field_value(distributions, "aoi_id")
                }
            },
            description="firm location",
            whether_embedding=False,
        ),
        "price": MemoryAttribute(
            name="price",
            type=float,
            default_or_value=float(np.mean(agent_skills)),
            description="firm price",
            whether_embedding=False,
        ),
        "inventory": MemoryAttribute(
            name="inventory",
            type=int,
            default_or_value=0,
            description="firm inventory",
            whether_embedding=False,
        ),
        "employees": MemoryAttribute(
            name="employees",
            type=list,
            default_or_value=[],
            description="firm employees",
            whether_embedding=False,
        ),
        "employees_agent_id": MemoryAttribute(
            name="employees_agent_id",
            type=list,
            default_or_value=[],
            description="firm employees agent id",
            whether_embedding=False,
        ),
        "nominal_gdp": MemoryAttribute(
            name="nominal_gdp",
            type=list,
            default_or_value=[],
            description="nominal gdp",
            whether_embedding=False,
        ),
        "real_gdp": MemoryAttribute(
            name="real_gdp",
            type=list,
            default_or_value=[],
            description="real gdp",
            whether_embedding=False,
        ),
        "unemployment": MemoryAttribute(
            name="unemployment",
            type=list,
            default_or_value=[],
            description="unemployment",
            whether_embedding=False,
        ),
        "wages": MemoryAttribute(
            name="wages",
            type=list,
            default_or_value=[],
            description="wages",
            whether_embedding=False,
        ),
        "demand": MemoryAttribute(
            name="demand",
            type=int,
            default_or_value=0,
            description="demand",
            whether_embedding=False,
        ),
        "sales": MemoryAttribute(
            name="sales",
            type=int,
            default_or_value=0,
            description="sales",
            whether_embedding=False,
        ),
        "prices": MemoryAttribute(
            name="prices",
            type=list,
            default_or_value=[float(np.mean(agent_skills))],
            description="prices",
            whether_embedding=False,
        ),
        "working_hours": MemoryAttribute(
            name="working_hours",
            type=list,
            default_or_value=[],
            description="working hours",
            whether_embedding=False,
        ),
        "depression": MemoryAttribute(
            name="depression",
            type=list,
            default_or_value=[],
            description="depression",
            whether_embedding=False,
        ),
        "consumption_currency": MemoryAttribute(
            name="consumption_currency",
            type=list,
            default_or_value=[],
            description="consumption currency",
            whether_embedding=False,
        ),
        "income_currency": MemoryAttribute(
            name="income_currency",
            type=list,
            default_or_value=[],
            description="income currency",
            whether_embedding=False,
        ),
        "locus_control": MemoryAttribute(
            name="locus_control",
            type=list,
            default_or_value=[],
            description="locus control",
            whether_embedding=False,
        ),
        "bracket_cutoffs": MemoryAttribute(
            name="bracket_cutoffs",
            type=list,
            default_or_value=list(np.array([0, 9875, 40125, 85525, 163300, 207350, 518400]) / 12),
            description="bracket cutoffs",
            whether_embedding=False,
        ),
        "bracket_rates": MemoryAttribute(
            name="bracket_rates",
            type=list,
            default_or_value=[0.1, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37],
            description="bracket rates",
            whether_embedding=False,
        ),
        "interest_rate": MemoryAttribute(
            name="interest_rate",
            type=float,
            default_or_value=0.03,
            description="interest rate",
            whether_embedding=False,
        ),
        "citizen_ids": MemoryAttribute(
            name="citizen_ids",
            type=list,
            default_or_value=[],
            description="citizen ids",
            whether_embedding=False,
        ),
        "firm_id": MemoryAttribute(
            name="firm_id",
            type=int,
            default_or_value=0,
            description="firm id",
            whether_embedding=False,
        ),
        "currency": MemoryAttribute(
            name="currency",
            type=float,
            default_or_value=1e12,
            description="firm currency",
            whether_embedding=False,
        ),
    }

    # Add class-specific attributes if provided
    if class_config:
        for attr in class_config:
            if attr.name in attributes:
                continue
            attributes[attr.name] = attr

    return MemoryConfig(attributes=attributes)


def memory_config_government(
    distributions: dict[str, Distribution],
    class_config: Optional[list[MemoryAttribute]] = None,
) -> MemoryConfig:
    """Generate memory configuration for government agents."""
    attributes = {
        "type": MemoryAttribute(
            name="type",
            type=int,
            default_or_value=EconomyEntityType.Government,
            description="agent type",
            whether_embedding=False,
        ),
        "bracket_cutoffs": MemoryAttribute(
            name="bracket_cutoffs",
            type=list,
            default_or_value=list(np.array([0, 9875, 40125, 85525, 163300, 207350, 518400]) / 12),
            description="bracket cutoffs",
            whether_embedding=False,
        ),
        "bracket_rates": MemoryAttribute(
            name="bracket_rates",
            type=list,
            default_or_value=[0.1, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37],
            description="bracket rates",
            whether_embedding=False,
        ),
        "citizen_ids": MemoryAttribute(
            name="citizen_ids",
            type=list,
            default_or_value=[],
            description="citizen ids",
            whether_embedding=False,
        ),
        "citizens_agent_id": MemoryAttribute(
            name="citizens_agent_id",
            type=list,
            default_or_value=[],
            description="citizens agent id",
            whether_embedding=False,
        ),
        "nominal_gdp": MemoryAttribute(
            name="nominal_gdp",
            type=list,
            default_or_value=[],
            description="nominal gdp",
            whether_embedding=False,
        ),
        "real_gdp": MemoryAttribute(
            name="real_gdp",
            type=list,
            default_or_value=[],
            description="real gdp",
            whether_embedding=False,
        ),
        "unemployment": MemoryAttribute(
            name="unemployment",
            type=list,
            default_or_value=[],
            description="unemployment",
            whether_embedding=False,
        ),
        "wages": MemoryAttribute(
            name="wages",
            type=list,
            default_or_value=[],
            description="wages",
            whether_embedding=False,
        ),
        "prices": MemoryAttribute(
            name="prices",
            type=list,
            default_or_value=[float(np.mean(agent_skills))],
            description="prices",
            whether_embedding=False,
        ),
        "working_hours": MemoryAttribute(
            name="working_hours",
            type=list,
            default_or_value=[],
            description="working hours",
            whether_embedding=False,
        ),
        "depression": MemoryAttribute(
            name="depression",
            type=list,
            default_or_value=[],
            description="depression",
            whether_embedding=False,
        ),
        "consumption_currency": MemoryAttribute(
            name="consumption_currency",
            type=list,
            default_or_value=[],
            description="consumption currency",
            whether_embedding=False,
        ),
        "income_currency": MemoryAttribute(
            name="income_currency",
            type=list,
            default_or_value=[],
            description="income currency",
            whether_embedding=False,
        ),
        "locus_control": MemoryAttribute(
            name="locus_control",
            type=list,
            default_or_value=[],
            description="locus control",
            whether_embedding=False,
        ),
        "inventory": MemoryAttribute(
            name="inventory",
            type=int,
            default_or_value=0,
            description="inventory",
            whether_embedding=False,
        ),
        "interest_rate": MemoryAttribute(
            name="interest_rate",
            type=float,
            default_or_value=0.03,
            description="interest rate",
            whether_embedding=False,
        ),
        "price": MemoryAttribute(
            name="price",
            type=float,
            default_or_value=float(np.mean(agent_skills)),
            description="price",
            whether_embedding=False,
        ),
        "employees": MemoryAttribute(
            name="employees",
            type=list,
            default_or_value=[],
            description="employees",
            whether_embedding=False,
        ),
        "firm_id": MemoryAttribute(
            name="firm_id",
            type=int,
            default_or_value=0,
            description="firm id",
            whether_embedding=False,
        ),
        "currency": MemoryAttribute(
            name="currency",
            type=float,
            default_or_value=1e12,
            description="government currency",
            whether_embedding=False,
        ),
    }

    # Add class-specific attributes if provided
    if class_config:
        for attr in class_config:
            if attr.name in attributes:
                continue
            attributes[attr.name] = attr

    return MemoryConfig(attributes=attributes)


def memory_config_bank(
    distributions: dict[str, Distribution],
    class_config: Optional[list[MemoryAttribute]] = None,
) -> MemoryConfig:
    """Generate memory configuration for bank agents."""
    attributes = {
        "type": MemoryAttribute(
            name="type",
            type=int,
            default_or_value=EconomyEntityType.Bank,
            description="agent type",
            whether_embedding=False,
        ),
        "interest_rate": MemoryAttribute(
            name="interest_rate",
            type=float,
            default_or_value=0.03,
            description="interest rate",
            whether_embedding=False,
        ),
        "citizen_ids": MemoryAttribute(
            name="citizen_ids",
            type=list,
            default_or_value=[],
            description="citizen ids",
            whether_embedding=False,
        ),
        "bracket_cutoffs": MemoryAttribute(
            name="bracket_cutoffs",
            type=list,
            default_or_value=list(np.array([0, 9875, 40125, 85525, 163300, 207350, 518400]) / 12),
            description="bracket cutoffs",
            whether_embedding=False,
        ),
        "bracket_rates": MemoryAttribute(
            name="bracket_rates",
            type=list,
            default_or_value=[0.1, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37],
            description="bracket rates",
            whether_embedding=False,
        ),
        "inventory": MemoryAttribute(
            name="inventory",
            type=int,
            default_or_value=0,
            description="inventory",
            whether_embedding=False,
        ),
        "nominal_gdp": MemoryAttribute(
            name="nominal_gdp",
            type=list,
            default_or_value=[],
            description="nominal gdp",
            whether_embedding=False,
        ),
        "real_gdp": MemoryAttribute(
            name="real_gdp",
            type=list,
            default_or_value=[],
            description="real gdp",
            whether_embedding=False,
        ),
        "unemployment": MemoryAttribute(
            name="unemployment",
            type=list,
            default_or_value=[],
            description="unemployment",
            whether_embedding=False,
        ),
        "wages": MemoryAttribute(
            name="wages",
            type=list,
            default_or_value=[],
            description="wages",
            whether_embedding=False,
        ),
        "prices": MemoryAttribute(
            name="prices",
            type=list,
            default_or_value=[float(np.mean(agent_skills))],
            description="prices",
            whether_embedding=False,
        ),
        "working_hours": MemoryAttribute(
            name="working_hours",
            type=list,
            default_or_value=[],
            description="working hours",
            whether_embedding=False,
        ),
        "depression": MemoryAttribute(
            name="depression",
            type=list,
            default_or_value=[],
            description="depression",
            whether_embedding=False,
        ),
        "consumption_currency": MemoryAttribute(
            name="consumption_currency",
            type=list,
            default_or_value=[],
            description="consumption currency",
            whether_embedding=False,
        ),
        "income_currency": MemoryAttribute(
            name="income_currency",
            type=list,
            default_or_value=[],
            description="income currency",
            whether_embedding=False,
        ),
        "locus_control": MemoryAttribute(
            name="locus_control",
            type=list,
            default_or_value=[],
            description="locus control",
            whether_embedding=False,
        ),
        "price": MemoryAttribute(
            name="price",
            type=float,
            default_or_value=float(np.mean(agent_skills)),
            description="price",
            whether_embedding=False,
        ),
        "employees": MemoryAttribute(
            name="employees",
            type=list,
            default_or_value=[],
            description="employees",
            whether_embedding=False,
        ),
        "firm_id": MemoryAttribute(
            name="firm_id",
            type=int,
            default_or_value=0,
            description="firm id",
            whether_embedding=False,
        ),
        "currency": MemoryAttribute(
            name="currency",
            type=float,
            default_or_value=1e12,
            description="bank currency",
            whether_embedding=False,
        ),
    }

    # Add class-specific attributes if provided
    if class_config:
        for attr in class_config:
            if attr.name in attributes:
                continue
            attributes[attr.name] = attr

    return MemoryConfig(attributes=attributes)


def memory_config_nbs(
    distributions: dict[str, Distribution],
    class_config: Optional[list[MemoryAttribute]] = None,
) -> MemoryConfig:
    """Generate memory configuration for NBS agents."""
    attributes = {
        "type": MemoryAttribute(
            name="type",
            type=int,
            default_or_value=EconomyEntityType.NBS,
            description="agent type",
            whether_embedding=False,
        ),
        "citizen_ids": MemoryAttribute(
            name="citizen_ids",
            type=list,
            default_or_value=[],
            description="citizen ids",
            whether_embedding=False,
        ),
        "nominal_gdp": MemoryAttribute(
            name="nominal_gdp",
            type=dict,
            default_or_value={},
            description="nominal gdp",
            whether_embedding=False,
        ),
        "real_gdp": MemoryAttribute(
            name="real_gdp",
            type=dict,
            default_or_value={},
            description="real gdp",
            whether_embedding=False,
        ),
        "real_gdp_metric": MemoryAttribute(
            name="real_gdp_metric",
            type=float,
            default_or_value=0.0,
            description="real gdp metric",
            whether_embedding=False,
        ),
        "unemployment": MemoryAttribute(
            name="unemployment",
            type=dict,
            default_or_value={},
            description="unemployment",
            whether_embedding=False,
        ),
        "wages": MemoryAttribute(
            name="wages",
            type=dict,
            default_or_value={},
            description="wages",
            whether_embedding=False,
        ),
        "prices": MemoryAttribute(
            name="prices",
            type=dict,
            default_or_value={"0": float(np.mean(agent_skills))},
            description="prices",
            whether_embedding=False,
        ),
        "working_hours": MemoryAttribute(
            name="working_hours",
            type=dict,
            default_or_value={},
            description="working hours",
            whether_embedding=False,
        ),
        "working_hours_metric": MemoryAttribute(
            name="working_hours_metric",
            type=float,
            default_or_value=0.0,
            description="working hours metric",
            whether_embedding=False,
        ),
        "depression": MemoryAttribute(
            name="depression",
            type=dict,
            default_or_value={},
            description="depression",
            whether_embedding=False,
        ),
        "depression_metric": MemoryAttribute(
            name="depression_metric",
            type=float,
            default_or_value=0.0,
            description="depression metric",
            whether_embedding=False,
        ),
        "consumption_currency": MemoryAttribute(
            name="consumption_currency",
            type=dict,
            default_or_value={},
            description="consumption currency",
            whether_embedding=False,
        ),
        "consumption_currency_metric": MemoryAttribute(
            name="consumption_currency_metric",
            type=float,
            default_or_value=0.0,
            description="consumption currency metric",
            whether_embedding=False,
        ),
        "income_currency": MemoryAttribute(
            name="income_currency",
            type=dict,
            default_or_value={},
            description="income currency",
            whether_embedding=False,
        ),
        "income_currency_metric": MemoryAttribute(
            name="income_currency_metric",
            type=float,
            default_or_value=0.0,
            description="income currency metric",
            whether_embedding=False,
        ),
        "locus_control": MemoryAttribute(
            name="locus_control",
            type=dict,
            default_or_value={},
            description="locus control",
            whether_embedding=False,
        ),
        "firm_id": MemoryAttribute(
            name="firm_id",
            type=int,
            default_or_value=0,
            description="firm id",
            whether_embedding=False,
        ),
        "bracket_cutoffs": MemoryAttribute(
            name="bracket_cutoffs",
            type=list,
            default_or_value=list(np.array([0, 9875, 40125, 85525, 163300, 207350, 518400]) / 12),
            description="bracket cutoffs",
            whether_embedding=False,
        ),
        "bracket_rates": MemoryAttribute(
            name="bracket_rates",
            type=list,
            default_or_value=[0.1, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37],
            description="bracket rates",
            whether_embedding=False,
        ),
        "inventory": MemoryAttribute(
            name="inventory",
            type=int,
            default_or_value=0,
            description="inventory",
            whether_embedding=False,
        ),
        "interest_rate": MemoryAttribute(
            name="interest_rate",
            type=float,
            default_or_value=0.03,
            description="interest rate",
            whether_embedding=False,
        ),
        "price": MemoryAttribute(
            name="price",
            type=float,
            default_or_value=float(np.mean(agent_skills)),
            description="price",
            whether_embedding=False,
        ),
        "price_metric": MemoryAttribute(
            name="price_metric",
            type=float,
            default_or_value=0.0,
            description="price metric",
            whether_embedding=False,
        ),
        "employees": MemoryAttribute(
            name="employees",
            type=list,
            default_or_value=[],
            description="employees",
            whether_embedding=False,
        ),
        "forward_times": MemoryAttribute(
            name="forward_times",
            type=int,
            default_or_value=0,
            description="forward times",
            whether_embedding=False,
        ),
        "currency": MemoryAttribute(
            name="currency",
            type=float,
            default_or_value=1e12,
            description="nbs currency",
            whether_embedding=False,
        ),
    }

    # Add class-specific attributes if provided
    if class_config:
        for attr in class_config:
            if attr.name in attributes:
                continue
            attributes[attr.name] = attr

    return MemoryConfig(attributes=attributes)
