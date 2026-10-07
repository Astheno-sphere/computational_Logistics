#!/usr/bin/env python
"""
Self-Enhancement (SE) Experiment - Main Entry Point
Run SE experiment using agentsociety2 framework with profile txt files
"""

import asyncio
import glob
import json
import logging
import os
import re
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv

# Disable telemetry before any imports
os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

load_dotenv()

from agentsociety2.agent import PersonAgent
from agentsociety2.contrib.env.self_enhancement import SelfEnhancementEnv
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


def load_real_se_data(se_data_path: str) -> pd.DataFrame:
    """
    Load real SE experiment data from Excel file

    Args:
        se_data_path: Path to Summary_SE.xlsx

    Returns:
        DataFrame with real SE data
    """
    try:
        df = pd.read_excel(se_data_path)
        return df
    except Exception as e:
        logging.warning(f"Failed to load real SE data from {se_data_path}: {e}")
        return pd.DataFrame()


def compare_with_real_data(
    simulated_results: dict[int, dict[str, int]], real_data: pd.DataFrame, logger
) -> dict:
    """
    Compare simulated results with real SE data

    Args:
        simulated_results: Dict mapping agent_id to rankings
        real_data: DataFrame with real SE data

    Returns:
        Comparison statistics
    """
    if real_data.empty:
        logger.warning("  [WARNING] Real data not available for comparison")
        return {}

    dimensions = [
        "INTELLIGENCE",
        "COOPERATION",
        "APPEARANCE",
        "MORALITY",
        "SOCIABILITY",
        "HEALTH",
        "HONESTY",
        "GENEROSITY",
    ]

    comparison = {
        "agent_comparisons": {},
        "dimension_statistics": {},
        "overall_statistics": {},
    }

    # Compare each agent if ID matches
    for agent_id, rankings in simulated_results.items():
        if "ID" in real_data.columns:
            real_row = real_data[real_data["ID"] == agent_id]
            if not real_row.empty:
                agent_comp = {
                    "dimension_comparisons": {},
                    "mean_absolute_error": 0,
                    "correlation": 0,
                }

                sim_values = []
                real_values = []

                for dim in dimensions:
                    col_name = f"Percentile_ranking_{dim}"
                    if col_name in real_data.columns:
                        sim_val = rankings.get(dim, None)
                        real_val = (
                            real_row[col_name].iloc[0]
                            if not pd.isna(real_row[col_name].iloc[0])
                            else None
                        )

                        if sim_val is not None and real_val is not None:
                            diff = abs(sim_val - real_val)
                            agent_comp["dimension_comparisons"][dim] = {
                                "simulated": sim_val,
                                "real": real_val,
                                "difference": diff,
                            }
                            sim_values.append(sim_val)
                            real_values.append(real_val)

                if sim_values and real_values:
                    import numpy as np

                    agent_comp["mean_absolute_error"] = np.mean(
                        [abs(s - r) for s, r in zip(sim_values, real_values)]
                    )
                    if len(sim_values) > 1:
                        agent_comp["correlation"] = np.corrcoef(
                            sim_values, real_values
                        )[0, 1]

                comparison["agent_comparisons"][agent_id] = agent_comp

    # Overall dimension statistics
    for dim in dimensions:
        col_name = f"Percentile_ranking_{dim}"
        if col_name in real_data.columns:
            sim_values = [
                rankings.get(dim)
                for rankings in simulated_results.values()
                if dim in rankings
            ]
            real_values = real_data[col_name].dropna().tolist()

            if sim_values and real_values:
                import numpy as np

                comparison["dimension_statistics"][dim] = {
                    "simulated_mean": np.mean(sim_values),
                    "simulated_std": np.std(sim_values),
                    "real_mean": np.mean(real_values),
                    "real_std": np.std(real_values),
                    "mean_difference": np.mean(sim_values) - np.mean(real_values),
                }

    # Overall statistics
    all_sim_values = []
    all_real_values = []
    for dim in dimensions:
        col_name = f"Percentile_ranking_{dim}"
        if col_name in real_data.columns:
            all_sim_values.extend(
                [
                    rankings.get(dim)
                    for rankings in simulated_results.values()
                    if dim in rankings
                ]
            )
            all_real_values.extend(real_data[col_name].dropna().tolist())

    if all_sim_values and all_real_values:
        import numpy as np

        comparison["overall_statistics"] = {
            "simulated_mean": np.mean(all_sim_values),
            "simulated_std": np.std(all_sim_values),
            "real_mean": np.mean(all_real_values),
            "real_std": np.std(all_real_values),
            "mean_difference": np.mean(all_sim_values) - np.mean(all_real_values),
        }

    return comparison


async def main(
    logger,
    num_agents: int = 5,
    profile_start_idx: int = 0,
    participant_ids: list[int] | None = None,
    profiles_dir: str | None = None,
    num_steps: int = 10,
    tick_seconds: int = 60,
    real_data_path: str | None = None,
):
    """
    Run Self-Enhancement experiment with enhanced tracking and analysis
    """
    logger.info("\n" + "=" * 80)
    logger.info("Self-Enhancement (SE) Experiment")
    logger.info("=" * 80)
    logger.info("Experiment Configuration:")
    logger.info(f"  - Number of steps: {num_steps}")
    logger.info(f"  - Seconds per step: {tick_seconds}")
    logger.info(
        f"  - Agent count: {num_agents if participant_ids is None else len(participant_ids)}"
    )
    logger.info("=" * 80)

    START_TIME = datetime.now()
    TIME_STEP_SECONDS = tick_seconds
    TOTAL_STEPS = num_steps

    se_env = None
    env_router = None
    agents = []

    # ==================== Load Profiles ====================
    logger.info(
        "\n[Step 1/4] Loading profile txt files (Profile Summary section only)..."
    )

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

    # Load profiles
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
            _target_agent_count = len(participant_ids)
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

    logger.info(f"  [OK] Loaded {len(profiles)} agent profiles")

    # Get actual agent IDs
    actual_agent_ids = [p["id"] for p in profiles]
    logger.info(f"  [OK] Actual Agent IDs: {actual_agent_ids}")
    logger.info(f"  [OK] Profile files used: {[p['filename'] for p in profiles]}")

    # Show sample profile summary
    if profiles:
        logger.info("  [OK] Profile Summary sample (first 200 characters):")
        sample_summary = profiles[0]["profile_text"][:200]
        logger.info(f"    {sample_summary}...")

    # ==================== Initialize Environment ====================
    logger.info("\n[Step 2/4] Initializing environment...")

    # ==================== Create Agents ====================
    logger.info(f"\n[Step 3/4] Creating {len(profiles)} agents...")

    agent_args = []
    for profile in profiles:
        agent_id = profile["id"]
        profile_text = profile["profile_text"]
        agent_args.append(
            {
                "id": agent_id,
                "profile": profile_text,
            }
        )

    # Create SelfEnhancementEnv
    se_env = SelfEnhancementEnv(agent_ids=actual_agent_ids)

    # Create CodeGenRouter
    env_router = CodeGenRouter(env_modules=[se_env])

    # Generate world description
    world_description = await env_router.generate_world_description_from_tools()

    logger.info("--------------------------------")
    logger.info("World Description:")
    logger.info(world_description)
    logger.info("--------------------------------")

    # Actually initialize agents
    # Note: world_description will be automatically set in agent.init() from env_router
    agents = [PersonAgent(**args) for args in agent_args]

    # ==================== Run Experiment ====================
    logger.info(
        f"\n[Step 4/4] Running experiment ({TOTAL_STEPS} steps, {TIME_STEP_SECONDS} seconds per step)..."
    )

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

    # ==================== Extract Results ====================
    logger.info("\n[Extracting Results]")

    # Get all rankings from environment
    results = se_env.get_results()

    logger.info(f"  [OK] Extracted results from {len(results)} agents")

    # Check completion status
    for agent_id, rankings in results.items():
        num_completed = len(rankings)
        logger.info(f"  Agent {agent_id}: {num_completed}/8 dimensions completed")
        if num_completed < 8:
            missing = [
                dim
                for dim in [
                    "INTELLIGENCE",
                    "COOPERATION",
                    "APPEARANCE",
                    "MORALITY",
                    "SOCIABILITY",
                    "HEALTH",
                    "HONESTY",
                    "GENEROSITY",
                ]
                if dim not in rankings
            ]
            logger.warning(f"    [WARNING] Missing dimensions: {', '.join(missing)}")

    # ==================== Load Real SE Data for Comparison ====================
    # Load real data for comparison (optional, doesn't affect experiment flow)
    if real_data_path is None:
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        workspace_root = os.path.dirname(
            os.path.dirname(os.path.dirname(current_file_dir))
        )
        real_data_path = os.path.join(
            workspace_root,
            "Self_bias_dataset",
            "8.Self_enhancement_(SE)",
            "Summary_SE.xlsx",
        )

    real_data = load_real_se_data(real_data_path)
    if not real_data.empty:
        logger.info(
            f"\n  [OK] Loaded real SE data for comparison: {len(real_data)} participants"
        )
    else:
        logger.info(
            f"\n  [WARNING] Real SE data not found (optional): {real_data_path}"
        )

    # ==================== Compare with Real Data ====================
    comparison = {}
    if not real_data.empty:
        logger.info("\n[Comparison with Real Data]")
        comparison = compare_with_real_data(results, real_data, logger)

    if comparison:
        if "overall_statistics" in comparison:
            stats = comparison["overall_statistics"]
            logger.info("Overall statistics comparison:")
            logger.info(
                f"  - Simulated data mean: {stats.get('simulated_mean', 0):.2f} ± {stats.get('simulated_std', 0):.2f}"
            )
            logger.info(
                f"  - Real data mean: {stats.get('real_mean', 0):.2f} ± {stats.get('real_std', 0):.2f}"
            )
            logger.info(f"  - Mean difference: {stats.get('mean_difference', 0):.2f}")

        if "agent_comparisons" in comparison:
            logger.info("\nIndividual comparison:")
            for agent_id, comp in comparison["agent_comparisons"].items():
                logger.info(f"  Agent {agent_id}:")
                logger.info(
                    f"    - Mean absolute error: {comp.get('mean_absolute_error', 0):.2f}"
                )
                logger.info(
                    f"    - Correlation coefficient: {comp.get('correlation', 0):.2f}"
                )

    # ==================== Save Results ====================
    logger.info("\n[Saving Results]")

    # Create output directory if it doesn't exist
    output_dir = "se_experiment_results"
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"  Results directory: {os.path.abspath(output_dir)}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save as JSON with comparison
    json_file = os.path.join(output_dir, f"se_results_{timestamp}.json")
    json_data = {
        "results": {
            agent_id: {
                f"Percentile_ranking_{dim}": percentile
                for dim, percentile in rankings.items()
            }
            for agent_id, rankings in results.items()
        },
        "comparison": comparison,
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

    # Save as CSV (aligned with original SE data format)
    import csv

    csv_file = os.path.join(output_dir, f"se_results_{timestamp}.csv")

    # Prepare CSV data
    csv_rows = []
    for agent_id, rankings in results.items():
        row = {
            "ID": agent_id,
            "Percentile_ranking_INTELLIGENCE": rankings.get("INTELLIGENCE", ""),
            "Percentile_ranking_COOPERATION": rankings.get("COOPERATION", ""),
            "Percentile_ranking_APPEARANCE": rankings.get("APPEARANCE", ""),
            "Percentile_ranking_MORALITY": rankings.get("MORALITY", ""),
            "Percentile_ranking_SOCIABILITY": rankings.get("SOCIABILITY", ""),
            "Percentile_ranking_HEALTH": rankings.get("HEALTH", ""),
            "Percentile_ranking_HONESTY": rankings.get("HONESTY", ""),
            "Percentile_ranking_GENEROSITY": rankings.get("GENEROSITY", ""),
        }
        csv_rows.append(row)

    # Write CSV
    if csv_rows:
        fieldnames = ["ID"] + [
            f"Percentile_ranking_{dim}"
            for dim in [
                "INTELLIGENCE",
                "COOPERATION",
                "APPEARANCE",
                "MORALITY",
                "SOCIABILITY",
                "HEALTH",
                "HONESTY",
                "GENEROSITY",
            ]
        ]
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

    logger.info(f"  [OK] CSV results saved to: {csv_file}")

    # Print summary statistics
    logger.info("\n[Statistics]")
    all_percentiles = []
    for rankings in results.values():
        all_percentiles.extend(rankings.values())

    if all_percentiles:
        import numpy as np

        logger.info(f"  - Total evaluations: {len(all_percentiles)}")
        logger.info(f"  - Average percentile: {np.mean(all_percentiles):.2f}")
        logger.info(f"  - Median percentile: {np.median(all_percentiles):.2f}")
        logger.info(f"  - Standard deviation: {np.std(all_percentiles):.2f}")
        logger.info(f"  - Minimum: {np.min(all_percentiles)}")
        logger.info(f"  - Maximum: {np.max(all_percentiles)}")

    await society.close()

    logger.info("\n" + "=" * 80)
    logger.info("Experiment completed!")
    logger.info("=" * 80)

    return json_data


if __name__ == "__main__":
    # Create log directory
    log_dir = "logs/experiment"
    os.makedirs(log_dir, exist_ok=True)

    # Setup log file path
    log_file = os.path.join(
        log_dir, f"se_experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
