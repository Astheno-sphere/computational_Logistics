from agentsociety.simulation import AgentSociety
from agentsociety.environment import MapData
from agentsociety.configs import Config
import numpy as np


INTENTION_CHECK_POINT = [i*2 for i in range(48)]

INTENTION_MAPPING = {
    "sleep": 1,
    "home activity": 2,
    "other": 3,
    "work": 4,
    "shopping": 5,
    "eating out": 6,
    "leisure and entertainment": 7,
}


def cal_gyration_radius(trajectory_points):
    centroid = np.mean(trajectory_points, axis=0)
    distances = np.sqrt(((trajectory_points - centroid) ** 2).sum(axis=1))
    gyration_radius = np.mean(distances)
    return gyration_radius


def gather_results(results: list[dict], map: MapData):
    # get all aois
    aois = map.aois
    aoi_ids = list(aois.keys())

    # gather agent data
    agent_data = {}
    for entry in results:
        agent_id = entry["id"]
        if agent_id not in agent_data:
            agent_data[agent_id] = []
        agent_data[agent_id].append(entry)
    
    # gather data
    try:
        agent_locations = {}
        agent_points = {}
        agent_intentions = {}
        for agent_id, entries in agent_data.items():
            if agent_id not in agent_locations:
                agent_locations[agent_id] = []
            if agent_id not in agent_points:
                agent_points[agent_id] = []
            if agent_id not in agent_intentions:
                agent_intentions[agent_id] = []
            
            for entry in entries:
                if entry["parent_id"] in aoi_ids and entry["parent_id"] not in agent_locations[agent_id]:
                    agent_locations[agent_id].append(entry["parent_id"])
                    aoi = aois[entry["parent_id"]]
                    centroid = aoi["shapely_xy"].centroid
                    point = [centroid.x, centroid.y]
                    agent_points[agent_id].append(point)
                agent_intentions[agent_id].append(entry["action"])

    except Exception as e:
        print(f"Error gathering data: {e}")
        raise

    # gather results
    try:
        daily_location_numbers = []
        gyration_radius = []
        intention_sequences = []
        intention_proportions = []
        for agent_id, locations in agent_locations.items():
            daily_location_numbers.append(len(locations))
            gyration_radius.append(cal_gyration_radius(agent_points[agent_id]))
            intention_list = [agent_intentions[agent_id][check_point] for check_point in INTENTION_CHECK_POINT]
            intention_list_mapping = []
            intention_proportion = [0] * 7
            for intention in intention_list:
                if intention in INTENTION_MAPPING:
                    intention_list_mapping.append(INTENTION_MAPPING[intention])
                else:
                    intention_list_mapping.append(3)
            for intention in intention_list_mapping:
                intention_proportion[intention-1] += 1
            # normalize
            intention_proportion = [proportion / len(intention_list) for proportion in intention_proportion]
            intention_proportions.append(intention_proportion)
            intention_sequences.append(intention_list_mapping)
    except Exception as e:
        print(f"Error gathering results: {e}")
        raise

    return {
        "daily_location_numbers": daily_location_numbers,
        "gyration_radius": gyration_radius,
        "intention_sequences": intention_sequences,
        "intention_proportions": intention_proportions
    }

async def entry(config: Config, tenant_id: str):
    # ========================    
    # create agentsociety
    # ========================
    agentsociety = AgentSociety.create(config, tenant_id)
    # ========================    
    # init agentsociety
    # ========================
    await agentsociety.init()
    # ========================    
    # run agentsociety
    # ========================
    await agentsociety.run()
    # ========================    
    # get results
    # ========================
    assert agentsociety._database_writer is not None
    results = await agentsociety._database_writer.read_statuses()
    # ========================    
    # gather results
    # ========================
    map = agentsociety.environment.map # type: ignore
    results = gather_results(results, map)
    # ========================    
    # close agentsociety
    # ========================
    await agentsociety.close()
    return results