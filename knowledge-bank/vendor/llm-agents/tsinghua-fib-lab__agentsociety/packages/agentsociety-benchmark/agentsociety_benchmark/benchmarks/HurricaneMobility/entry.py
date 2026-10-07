from agentsociety.simulation import AgentSociety
from agentsociety.environment import MapData
from agentsociety.configs import Config

def gather_results(results: list[dict], map: MapData):
    aois = map.aois
    aoi_ids = list(aois.keys())

    pre_hurricane_agent_entries = {}
    mid_hurricane_agent_entries = {}
    post_hurricane_agent_entries = {}
    try:
        for result in results:
            agent_id = result["id"]
            if agent_id not in pre_hurricane_agent_entries:
                pre_hurricane_agent_entries[agent_id] = []
            if agent_id not in mid_hurricane_agent_entries:
                mid_hurricane_agent_entries[agent_id] = []
            if agent_id not in post_hurricane_agent_entries:
                post_hurricane_agent_entries[agent_id] = []
            if result["day"] == 0:
                pre_hurricane_agent_entries[agent_id].append(result)
            elif result["day"] == 1:
                mid_hurricane_agent_entries[agent_id].append(result)
            elif result["day"] == 2:
                post_hurricane_agent_entries[agent_id].append(result)
            else:
                continue
    except Exception as e:
        print(f"HurricaneMobility, error gather statuses: {e}")
        raise e
    
    total_travel_times = [0, 0, 0]
    hourly_travel_times = [[0 for _ in range(24)] for _ in range(3)]
    try:
        for agent_id, entries in pre_hurricane_agent_entries.items():
            pre_aoi_id = 0
            pre_id = 0
            for entry in entries:
                # counting total travel times
                if entry["parent_id"] in aoi_ids:
                    if pre_aoi_id == 0:
                        pre_aoi_id = entry["parent_id"]
                    if pre_aoi_id != entry["parent_id"]:
                        total_travel_times[0] += 1
                        pre_aoi_id = entry["parent_id"]
                elif pre_id in aoi_ids:
                    departure_time = entry["t"]
                    hour = int(departure_time // (60 * 60))
                    hourly_travel_times[0][hour] += 1
                pre_id = entry["parent_id"]
    except Exception as e:
        print(f"HurricaneMobility, error gather pre_hurricane_agent_entries: {e}")
        raise e
        
    try:
        for agent_id, entries in mid_hurricane_agent_entries.items():
            pre_aoi_id = 0
            pre_id = 0
            for entry in entries:
                if entry["parent_id"] in aoi_ids:
                    if pre_aoi_id == 0:
                        pre_aoi_id = entry["parent_id"]
                    if pre_aoi_id != entry["parent_id"]:
                        total_travel_times[1] += 1
                        pre_aoi_id = entry["parent_id"]
                elif pre_id in aoi_ids:
                    departure_time = entry["t"]
                    hour = int(departure_time // (60 * 60))
                    hourly_travel_times[1][hour] += 1
                pre_id = entry["parent_id"]
    except Exception as e:
        print(f"HurricaneMobility, error gather mid_hurricane_agent_entries: {e}")
        raise e
    
    try:
        for agent_id, entries in post_hurricane_agent_entries.items():
            pre_aoi_id = 0
            pre_id = 0
            for entry in entries:
                if entry["parent_id"] in aoi_ids:
                    if pre_aoi_id == 0:
                        pre_aoi_id = entry["parent_id"]
                    if pre_aoi_id != entry["parent_id"]:
                        total_travel_times[2] += 1
                        pre_aoi_id = entry["parent_id"]
                elif pre_id in aoi_ids:
                    departure_time = entry["t"]
                    hour = int(departure_time // (60 * 60))
                    hourly_travel_times[2][hour] += 1
                pre_id = entry["parent_id"]
    except Exception as e:
        print(f"HurricaneMobility, error gather post_hurricane_agent_entries: {e}")
        raise e

    return {
        "total_travel_times": total_travel_times,
        "hourly_travel_times": hourly_travel_times,
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