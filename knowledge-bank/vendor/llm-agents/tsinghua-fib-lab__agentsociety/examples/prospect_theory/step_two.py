import asyncio

from agentsociety.cityagent import (
    SocietyAgent,
    default,
)
from agentsociety.configs import (
    AgentsConfig,
    Config,
    EnvConfig,
    ExpConfig,
    LLMConfig,
    MapConfig,
)
from agentsociety.configs.agent import AgentConfig
from agentsociety.configs.exp import (
    AgentFilterConfig,
    WorkflowStepConfig,
    WorkflowType,
)
from agentsociety.environment import EnvironmentConfig
from agentsociety.llm import LLMProviderType
from agentsociety.simulation import AgentSociety
from agentsociety.storage import DatabaseConfig

from surveys import happiness_survey


config = Config(
    llm=[
        LLMConfig(
            provider=LLMProviderType.Qwen,
            base_url=None,
            api_key="<YOUR-API-KEY>",
            model="<YOUR-MODEL>",
            concurrency=200,
            timeout=60,
        )
    ],
    env=EnvConfig(
        db=DatabaseConfig(
            enabled=True,
            db_type="sqlite",
            pg_dsn=None,
        ),
    ),
    map=MapConfig(
        file_path="<MAP-FILE-PATH>",
    ),
    agents=AgentsConfig(
        citizens=[
            AgentConfig(
                agent_class="citizen",
                number=100,
                memory_from_file="./profiles/citizen_profile_with_personality.json",
            )
        ],
    ),  # type: ignore
    exp=ExpConfig(
        name="prospect_theory_step_two",
        workflow=[
            WorkflowStepConfig(
                type=WorkflowType.SURVEY,
                survey=happiness_survey(),
                target_agent=AgentFilterConfig(
                    agent_class=(SocietyAgent,)
                )
            ),
            WorkflowStepConfig(
                type=WorkflowType.MESSAGE_INTERVENE,
                target_agent=AgentFilterConfig(
                    filter_str="${profile.personality} == '风险规避者'"
                ),
                intervene_message="恭喜您在最近的一次抽奖活动中获得了1000元！"
            ),
            WorkflowStepConfig(
                type=WorkflowType.MESSAGE_INTERVENE,
                target_agent=AgentFilterConfig(
                    filter_str="${profile.personality} == '风险寻求者 - 好运者'"
                ),
                intervene_message="恭喜您在最近的一次抽奖活动中获得了2500元！"
            ),
            WorkflowStepConfig(
                type=WorkflowType.MESSAGE_INTERVENE,
                target_agent=AgentFilterConfig(
                    filter_str="${profile.personality} == '风险寻求者 - 厄运者'"
                ),
                intervene_message="很遗憾，您在最近的一次抽奖活动中没有获得任何奖励。"
            ),
            WorkflowStepConfig(
                type=WorkflowType.SURVEY,
                survey=happiness_survey(),
                target_agent=AgentFilterConfig(
                    agent_class=(SocietyAgent,)
                )
            ),
        ],
        environment=EnvironmentConfig(
            start_tick=6 * 60 * 60,
        ),
    ),
)
config = default(config)


async def main():
    agentsociety = AgentSociety.create(config)
    try:
        await agentsociety.init()
        await agentsociety.run()
    finally:
        await agentsociety.close()


if __name__ == "__main__":
    asyncio.run(main())