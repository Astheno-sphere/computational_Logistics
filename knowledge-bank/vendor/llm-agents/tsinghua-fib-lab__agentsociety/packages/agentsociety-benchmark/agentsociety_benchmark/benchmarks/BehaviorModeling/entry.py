from agentsociety.simulation import AgentSociety
from agentsociety.configs import IndividualConfig

async def entry(config: IndividualConfig, tenant_id: str):
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
    results = await agentsociety._database_writer.read_task_results()
    # ========================    
    # close agentsociety
    # ========================
    await agentsociety.close()
    return results