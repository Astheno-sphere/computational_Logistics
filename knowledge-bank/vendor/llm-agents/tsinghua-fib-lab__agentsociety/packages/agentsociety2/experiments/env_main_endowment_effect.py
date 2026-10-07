#!/usr/bin/env python
"""
Endowment Effect Experiment - Main Entry Point
Run Endowment Effect experiment using participant profiles from txt files
"""

import asyncio
import glob
import json
import logging
import os
import re
from datetime import datetime

from dotenv import load_dotenv

# Disable telemetry before any imports
os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

load_dotenv()

from agentsociety2.agent import PersonAgent
from agentsociety2.contrib.env.endowment_effect import EndowmentEffectEnv
from agentsociety2.env import CodeGenRouter
from agentsociety2.logger import get_logger, setup_logging
from agentsociety2.society import AgentSociety


def extract_profile_summary(profile_path: str) -> str:
    """Extract Profile Summary section from txt file"""
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        summary_start_idx = None
        for i, line in enumerate(lines):
            if line.strip() == "## Profile Summary":
                summary_start_idx = i
                break

        if summary_start_idx is None:
            raise ValueError(f"Profile Summary section not found in {profile_path}")

        summary_lines = lines[summary_start_idx:]
        profile_summary = "".join(summary_lines).strip()

        return profile_summary
    except Exception as e:
        raise Exception(f"Failed to extract profile summary from {profile_path}: {e}")


def get_participant_id_from_filename(filename: str) -> int:
    """Extract participant ID from filename"""
    match = re.search(r"P(\d+)_profile\.txt", filename)
    if match:
        return int(match.group(1))
    raise ValueError(f"Cannot extract participant ID from filename: {filename}")


def create_default_profile(agent_id: int) -> str:
    """Create default profile summary for an agent when profile file is not available"""
    return """## Profile Summary

This participant is a typical individual with average personality traits and characteristics. 
They demonstrate moderate levels of extraversion, agreeableness, conscientiousness, neuroticism, and openness. 
Their self-concept is balanced, showing neither extreme self-enhancement nor excessive modesty. 
They approach decisions with reasonable consideration of their own interests and values."""


def load_profiles_from_directory(
    profiles_dir: str,
    participant_ids: list[int] | None = None,
    start_idx: int = 0,
    num_agents: int | None = None,
) -> list[dict]:
    """Load participant profiles from directory"""
    profile_files = sorted(glob.glob(os.path.join(profiles_dir, "P*_profile.txt")))

    if not profile_files:
        raise ValueError(f"No profile files found in directory: {profiles_dir}")

    profiles = []
    for filepath in profile_files:
        filename = os.path.basename(filepath)
        participant_id = get_participant_id_from_filename(filename)
        profile_summary = extract_profile_summary(filepath)

        profiles.append(
            {
                "id": participant_id,
                "profile_text": profile_summary,
                "filename": filename,
            }
        )

    profiles.sort(key=lambda x: x["id"])

    if participant_ids:
        profile_dict = {p["id"]: p for p in profiles}
        selected_profiles = []
        for pid in participant_ids:
            if pid in profile_dict:
                selected_profiles.append(profile_dict[pid])
            else:
                logging.warning(f"Participant ID {pid} not found in profiles")
        profiles = selected_profiles

    elif num_agents is not None:
        profiles = profiles[start_idx : start_idx + num_agents]

    return profiles


async def main(
    logger,
    num_agents: int = 5,
    profile_start_idx: int = 0,
    participant_ids: list[int] | None = None,
    profiles_dir: str | None = None,
    num_steps: int = 20,
    tick_seconds: int = 60,
):
    """
    Run Endowment Effect (EE) experiment.

    Experiment setup:
    - Simulation start: 9:00:00 AM (UTC) on current day
    - Time step: Configurable (default: 60 seconds)
    - Total steps: Configurable (default: 20 steps, providing sufficient time for all evaluations)

    Args:
        logger: Logger instance
        num_agents: Number of agents (if participant_ids not specified)
        profile_start_idx: Start index (if participant_ids not specified)
        participant_ids: Specified participant ID list (optional, e.g., [101, 102, 103])
        profiles_dir: Profile files directory path (optional, default uses relative path)
        num_steps: Total simulation steps (default: 20)
        tick_seconds: Time length per step in seconds (default: 60)
    """
    logger.info("\n" + "=" * 80)
    logger.info("Endowment Effect (EE) Experiment")
    logger.info("=" * 80)
    logger.info("Experiment Configuration:")
    logger.info("  - Start time: 9:00:00 AM (UTC)")
    logger.info(f"  - Time step: {tick_seconds} seconds")
    logger.info(f"  - Total steps: {num_steps}")
    logger.info(
        f"  - Agent count: {num_agents if participant_ids is None else len(participant_ids)}"
    )
    logger.info("=" * 80)

    # Experiment parameters
    START_TIME = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    TIME_STEP_SECONDS = tick_seconds
    TOTAL_STEPS = num_steps

    # Storage for cleanup
    env_router = None
    agents = []
    ee_env = None

    # ==================== Load Profiles ====================
    logger.info("\n[Step 1/5] Loading profile txt files...")

    # Determine profile directory path
    if profiles_dir is None:
        # Default path: relative to current file, pointing to Self_bias_dataset directory
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        workspace_root = os.path.dirname(
            os.path.dirname(os.path.dirname(current_file_dir))
        )
        profiles_dir = os.path.join(
            workspace_root,
            "Self_bias_dataset",
            "0.Self_reported_scales",
            "Participant_profiles",
        )

    # Load profiles (extracting Profile Summary section)
    profiles = []
    use_default_profiles = False

    if not os.path.exists(profiles_dir):
        logger.warning(f"  [WARNING] Profile directory does not exist: {profiles_dir}")
        logger.info("  [INFO] Will use default agent profiles")
        use_default_profiles = True
    else:
        logger.info(f"  [OK] Profile directory: {profiles_dir}")

        try:
            profiles = load_profiles_from_directory(
                profiles_dir=profiles_dir,
                participant_ids=participant_ids,
                start_idx=profile_start_idx,
                num_agents=num_agents if participant_ids is None else None,
            )
        except Exception as e:
            logger.warning(f"  [WARNING] Failed to load profile files: {e}")
            logger.info("  [INFO] Will use default agent profiles")
            use_default_profiles = True

    # If no profiles loaded, create default profiles
    if use_default_profiles or not profiles:
        logger.info("  [INFO] Creating default agent profiles")
        if participant_ids:
            target_agent_count = len(participant_ids)
            agent_ids = participant_ids
        elif num_agents is not None:
            target_agent_count = num_agents
            agent_ids = [1000 + i for i in range(target_agent_count)]
        else:
            target_agent_count = 5  # Default to 5 agents
            agent_ids = [1000 + i for i in range(target_agent_count)]

        for agent_id in agent_ids:
            default_profile = create_default_profile(agent_id)
            profiles.append(
                {
                    "id": agent_id,
                    "profile_text": default_profile,
                    "filename": f"default_agent_{agent_id}.txt",
                }
            )

    logger.info(
        f"  [OK] Loaded {len(profiles)} agent profiles (Profile Summary extracted)"
    )

    # Get actual agent IDs
    actual_agent_ids = [p["id"] for p in profiles]
    logger.info(f"  [OK] Actual Agent IDs: {actual_agent_ids}")
    logger.info(f"  [OK] Profile files used: {[p['filename'] for p in profiles]}")

    # ==================== Initialize Environment ====================
    logger.info("\n[Step 2/5] Initializing environment...")

    # Create EndowmentEffectEnv
    ee_env = EndowmentEffectEnv(agent_ids=actual_agent_ids)

    # Create CodeGenRouter
    env_router = CodeGenRouter(env_modules=[ee_env])

    # Generate world description
    world_description = await env_router.generate_world_description_from_tools()

    logger.info("  [OK] Environment initialized successfully")
    logger.info("\nWorld Description:")
    logger.info("-" * 80)
    logger.info(world_description)
    logger.info("-" * 80)

    # ==================== Create Agents ====================
    logger.info(f"\n[Step 3/5] Creating {len(profiles)} agents...")

    agent_args = []
    for profile in profiles:
        agent_id = profile["id"]
        profile_text = profile["profile_text"]  # Profile Summary section

        # Create agent (using Profile Summary section)
        agent_args.append(
            {
                "id": agent_id,
                "profile": profile_text,
            }
        )
        logger.info(f"  [OK] Created Agent {agent_id} configuration")

    # Initialize agents
    # Note: world_description will be automatically set in agent.init() from env_router
    agents = [PersonAgent(**args) for args in agent_args]
    logger.info(f"  [OK] Successfully created {len(agents)} agents")

    # ==================== Run Experiment ====================
    logger.info("\n[Step 4/5] Running experiment...")
    logger.info(f"  - Total steps: {TOTAL_STEPS}")
    logger.info(f"  - Time step: {TIME_STEP_SECONDS} seconds")

    society = AgentSociety(
        agent_specs=[
            {"id": a.id, "profile": a._profile, "config": a._config} for a in agents
        ],
        agent_class_name="PersonAgent",
        env_router=env_router,
        start_t=START_TIME,
    )
    await society.init()

    await society.run(num_steps=TOTAL_STEPS, tick=TIME_STEP_SECONDS)

    # ==================== Collect Results ====================
    logger.info("\n[Step 5/5] Collecting results...")

    # Get all evaluation results from environment
    results = ee_env.get_results()

    # Convert to format aligned with original data
    output_data = []
    for agent_id in actual_agent_ids:
        agent_evaluations = results.get(agent_id, {})

        # Build output row
        row = {
            "ID": agent_id,
        }

        # Add WTA and WTP values (if exist)
        for item in ["pen", "plate", "glass", "doll"]:
            if item in agent_evaluations:
                row[f"WTA_{item}"] = agent_evaluations[item]["wta"]
                row[f"WTP_{item}"] = agent_evaluations[item]["wtp"]
            else:
                row[f"WTA_{item}"] = None
                row[f"WTP_{item}"] = None

        output_data.append(row)

        # Log each agent's evaluation status
        logger.info(f"  Agent {agent_id}:")
        evaluated_items = list(agent_evaluations.keys())
        if evaluated_items:
            logger.info(f"    - Evaluated items: {evaluated_items}")
            for item in evaluated_items:
                logger.info(
                    f"      {item}: WTA={agent_evaluations[item]['wta']:.2f}, WTP={agent_evaluations[item]['wtp']:.2f}"
                )
        else:
            logger.warning("    - [WARNING] No items evaluated")

    # ==================== Save Results ====================
    logger.info("\n[Saving Results]")

    output_dir = "endowment_effect_results"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save as JSON format
    json_file = os.path.join(output_dir, f"ee_results_{timestamp}.json")
    json_data = {
        "results": output_data,
        "metadata": {
            "num_agents": len(profiles),
            "actual_agent_ids": actual_agent_ids,
            "total_steps": TOTAL_STEPS,
            "time_step_seconds": TIME_STEP_SECONDS,
            "start_time": START_TIME.isoformat(),
            "timestamp": timestamp,
            "profiles_dir": profiles_dir,
            "profile_files": [p["filename"] for p in profiles],
        },
    }

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    logger.info(f"  [OK] JSON results saved to: {json_file}")

    # Save as CSV format (for analysis)
    csv_file = os.path.join(output_dir, f"ee_results_{timestamp}.csv")
    import csv

    if output_data:
        fieldnames = (
            ["ID"]
            + [f"WTA_{item}" for item in ["pen", "plate", "glass", "doll"]]
            + [f"WTP_{item}" for item in ["pen", "plate", "glass", "doll"]]
        )
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in output_data:
                writer.writerow(row)
        logger.info(f"  [OK] CSV results saved to: {csv_file}")

    # Statistics
    logger.info("\n[Statistics]")
    total_evaluations = sum(
        len(results.get(agent_id, {})) for agent_id in actual_agent_ids
    )
    expected_evaluations = (
        len(actual_agent_ids) * 4
    )  # Each agent should evaluate 4 items
    completion_rate = (
        (total_evaluations / expected_evaluations * 100)
        if expected_evaluations > 0
        else 0
    )
    logger.info(f"  - Total evaluations: {total_evaluations}/{expected_evaluations}")
    logger.info(f"  - Completion rate: {completion_rate:.1f}%")

    await society.close()

    logger.info("\n" + "=" * 80)
    logger.info("Experiment completed!")
    logger.info("=" * 80)


if __name__ == "__main__":
    # Create log directory
    log_dir = "logs/experiment"
    os.makedirs(log_dir, exist_ok=True)

    # Setup log file path
    log_file = os.path.join(
        log_dir, f"ee_experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    setup_logging(
        log_file=log_file,
        log_level=logging.DEBUG,
    )

    # Example 1: Use default settings (load 5 agents starting from index 0)
    # asyncio.run(main(logger=get_logger(), num_agents=5, profile_start_idx=0))

    # Example 2: Specify participant IDs
    # asyncio.run(main(logger=get_logger(), participant_ids=[101, 102, 103, 104, 105]))

    # Example 3: Test run
    asyncio.run(
        main(
            logger=get_logger(),
            num_agents=20,
            profile_start_idx=0,
            num_steps=20,
            tick_seconds=150,
        )
    )
