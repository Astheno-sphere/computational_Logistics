import asyncio
import json
import logging
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

# 先加载环境变量，再强制关闭 mem0 和 ChromaDB telemetry，避免导入 PersonAgent 时触发埋点线程。
load_dotenv()
os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from agentsociety2.agent import PersonAgent
from agentsociety2.contrib.env.event_space import EventSpace
from agentsociety2.contrib.env.global_information import GlobalInformationEnv
from agentsociety2.contrib.env.mobility_space import MobilitySpace
from agentsociety2.env import CodeGenRouter
from agentsociety2.logger import get_logger, setup_logging
from agentsociety2.society import AgentSociety


async def main_disaster_mobility(
    logger,
    num_agents: int = 50,
    profile_start_idx: int = 0,
    profiles_path: str | None = None,
    map_path: str | None = None,
):
    """
    灾害对出行影响实验（11天，每小时一步）

    实验设置：
    - Day 1: 正常日常移动
    - Day 3（当日一早）: 广播突发山火
    - Day 4-Day 9: 每天广播“山火还在持续”
    - Day 10（当日一早）: 广播山火已被扑灭

    统计量：
    - 每天所有agent的出行量总和（move_to完成次数）
    """
    logger.info("\n" + "=" * 80)
    logger.info("【灾害对出行影响实验】")
    logger.info("=" * 80)

    # 时间设置：每小时一步，共11天
    start_time = datetime.now().replace(
        year=2026, month=2, day=9, hour=0, minute=0, second=0, microsecond=0
    )
    time_step_seconds = 60 * 60  # 1小时
    total_days = 11
    steps_per_day = 24
    total_steps = total_days * steps_per_day

    # ==================== 加载 Profiles ====================
    logger.info("\n【步骤1/4】加载 agent_profiles_ca_paradise.json...")
    if profiles_path is None:
        profiles_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "../../..", "agent_profiles_ca_paradise.json"
            )
        )
    if not os.path.exists(profiles_path):
        logger.error(f"  ❌ agent profiles 文件不存在: {profiles_path}")
        return

    with open(profiles_path, "r", encoding="utf-8") as f:
        profiles = json.load(f)

    logger.info(f"  ✓ 加载了 {len(profiles)} 个 agent profiles")

    if num_agents > len(profiles):
        logger.warning(
            f"  ⚠ 请求的 agent 数量 ({num_agents}) 超过 profiles 数量 ({len(profiles)})，使用全部 {len(profiles)} 个"
        )
        num_agents = len(profiles)

    profiles_to_use = profiles[profile_start_idx : profile_start_idx + num_agents]

    # ==================== 初始化环境 ====================
    logger.info("\n【步骤2/4】初始化环境...")
    import tempfile

    chroma_base_dir = tempfile.mkdtemp(prefix="chroma_memories_")
    logger.info(f"  ✓ 创建临时chroma目录: {chroma_base_dir}")

    # ==================== 创建 Agents ====================
    logger.info(f"\n【步骤3/4】创建 {num_agents} 个 Agents...")
    agent_args = []
    mobility_persons = []
    date_time_str = datetime.now().strftime("%Y%m%d%H%M%S")

    for idx, profile in enumerate(profiles_to_use, start=1):
        agent_str_id = profile.get("agent_id", f"agent_{idx:04d}")
        agent_id = idx  # 使用连续整数ID，方便MobilitySpace处理

        agent_chroma_path = os.path.join(
            chroma_base_dir, f"agent_{agent_id}_{date_time_str}"
        )
        os.makedirs(agent_chroma_path, exist_ok=True)
        agent_sqlite_path = os.path.join(chroma_base_dir, f"agent_{agent_id}.db")
        os.makedirs(os.path.dirname(agent_sqlite_path), exist_ok=True)

        profile_text = (
            f"My name is {agent_str_id}, "
            f"gender {profile.get('gender', 'Unknown')}, "
            f"race {profile.get('race', 'Unknown')}, "
            f"education {profile.get('education', 'Unknown')}, "
            f"transport_mode {profile.get('transport_mode', 'Unknown')}, "
            f"average_commuting_time {profile.get('average_commuting_time', 'Unknown')}, "
            f"median_income {profile.get('median_income', 'Unknown')}, "
            f"median_age {profile.get('median_age', 'Unknown')}, "
            f"average_household_size {profile.get('average_household_size', 'Unknown')}, "
            f"home at {profile.get('home_aoi_id')}, "
            f"work at {profile.get('work_aoi_id')}"
        )

        agent_args.append(
            {
                "id": agent_id,
                "profile": profile_text,
                "ask_intention_enabled": False,
            }
        )

        mobility_persons.append(
            {
                "id": agent_id,
                "position": {
                    "kind": "aoi",
                    "aoi_id": int(profile["home_aoi_id"]),
                },
            }
        )

    # ==================== 创建环境与路由 ====================
    home_dir = os.path.join(os.path.expanduser("~"), "agentsociety_data")
    if map_path is None:
        map_path = os.path.join(home_dir, "map_us_ca_paradise.pb")
    os.makedirs(home_dir, exist_ok=True)

    mobility_env = MobilitySpace(map_path, home_dir, persons=mobility_persons)
    event_space = EventSpace()
    global_info_env = GlobalInformationEnv()

    env_router = CodeGenRouter(
        env_modules=[mobility_env, event_space, global_info_env],
    )

    world_description = await env_router.generate_world_description_from_tools()
    print("--------------------------------")
    print(world_description)
    print("--------------------------------")

    agents = [PersonAgent(**args) for args in agent_args]
    society = AgentSociety(
        agent_specs=[
            {"id": a.id, "profile": a._profile, "config": a._config} for a in agents
        ],
        agent_class_name="PersonAgent",
        env_router=env_router,
        start_t=start_time,
    )
    await society.init()

    # 广播内容设置
    await global_info_env.set("今天一切正常")

    # ==================== 运行仿真并统计出行量 ====================
    daily_move_counts = [0 for _ in range(total_days)]

    for step_idx in range(total_steps):
        # Day 3 当日一早广播“突发山火”
        if step_idx == 2 * steps_per_day:
            await global_info_env.set(
                "紧急广播：极端寒潮袭击我市，请广大民众注意适当减少非必要出行"
            )
        # Day 4 到 Day 9 每天开始时广播“山火还在持续”
        elif (
            step_idx % steps_per_day == 0
            and 3 * steps_per_day <= step_idx < 9 * steps_per_day
        ):
            await global_info_env.set(
                "广播：寒潮仍在持续，请广大民众注意适当减少非必要出行"
            )
        # Day 10 当日一早广播灾害结束
        elif step_idx == 9 * steps_per_day:
            await global_info_env.set("广播：寒潮已经结束，可恢复正常秩序")

        # 手动执行一步（复制 AgentSociety.step 的逻辑）
        society._t += timedelta(seconds=time_step_seconds)
        society._env_router.set_current_time(society._t)
        tasks = [agent.step(time_step_seconds, society._t) for agent in society._agents]
        await asyncio.gather(*tasks)

        # 在环境 step 前记录当前移动中的人
        moving_before_env = {
            pid
            for pid, person in mobility_env._persons.items()
            if person.status == "moving"
        }

        await society._env_router.step(time_step_seconds, society._t)
        society._step_count += 1

        # 统计本步完成的出行（move_to完成）
        completed_moves = 0
        for pid in moving_before_env:
            person = mobility_env._persons.get(pid)
            if person is not None and person.status == "idle":
                completed_moves += 1

        day_index = step_idx // steps_per_day
        daily_move_counts[day_index] += completed_moves

        if (step_idx + 1) % steps_per_day == 0:
            logger.info(
                f"  ✓ Day {day_index + 1} 出行量总和: {daily_move_counts[day_index]}"
            )

    # ==================== 保存统计结果 ====================
    output_dir = "benchmark_results"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(
        output_dir, f"disaster_mobility_daily_moves_{timestamp}.json"
    )
    save_data = {
        "daily_move_counts": daily_move_counts,
        "metadata": {
            "num_agents": num_agents,
            "total_days": total_days,
            "steps_per_day": steps_per_day,
            "time_step_seconds": time_step_seconds,
            "start_time": start_time.isoformat(),
            "profiles_path": profiles_path,
            "map_path": map_path,
            "timestamp": timestamp,
        },
    }
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    logger.info(f"  ✓ 统计结果已保存到: {result_file}")

    await society.close()


if __name__ == "__main__":
    setup_logging(
        log_file=f"logs_disaster_ca/disaster_mobility-{datetime.now().strftime('%Y%m%d%H%M%S')}.log",
        log_level=logging.DEBUG,
    )
    asyncio.run(main_disaster_mobility(logger=get_logger()))
