#!/usr/bin/env python
"""
Self-Reference Effect (SRE) Experiment - Main Entry Point
Run SRE experiment using agentsociety2 framework with profile txt files
"""

import asyncio
import csv
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
from agentsociety2.contrib.env.self_reference_effect import SelfReferenceEffectEnv
from agentsociety2.env import CodeGenRouter
from agentsociety2.logger import get_logger, setup_logging
from agentsociety2.society import AgentSociety


def extract_profile_summary(profile_path: str) -> str:
    """
    Extract Profile Summary section from txt file (lines starting from "## Profile Summary").

    Args:
        profile_path: Path to the profile txt file

    Returns:
        Profile Summary text (lines starting from "## Profile Summary")
    """
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Find the line index of "## Profile Summary"
        summary_start_idx = None
        for i, line in enumerate(lines):
            if line.strip() == "## Profile Summary":
                summary_start_idx = i
                break

        if summary_start_idx is None:
            raise ValueError(f"Profile Summary section not found in {profile_path}")

        # Extract from "## Profile Summary" to the end
        summary_lines = lines[summary_start_idx:]
        profile_summary = "".join(summary_lines).strip()

        return profile_summary
    except Exception as e:
        raise Exception(f"Failed to extract profile summary from {profile_path}: {e}")


def get_participant_id_from_filename(filename: str) -> int:
    """
    Extract participant ID from filename (e.g., P101_profile.txt -> 101)

    Args:
        filename: Filename

    Returns:
        Participant ID (integer)
    """
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
    """
    Load participant profiles from directory, extracting only Profile Summary section.

    Args:
        profiles_dir: Profile files directory path
        participant_ids: Specified participant ID list (optional)
        start_idx: Start index (if participant_ids not specified)
        num_agents: Number of agents to load (if participant_ids not specified)

    Returns:
        List of dictionaries containing profile information:
        - id: Participant ID
        - profile_text: Profile Summary text
        - filename: Filename
    """
    # Get all profile files
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

    # Sort by ID
    profiles.sort(key=lambda x: x["id"])

    # Filter by participant_ids if specified
    if participant_ids:
        profile_dict = {p["id"]: p for p in profiles}
        selected_profiles = []
        for pid in participant_ids:
            if pid in profile_dict:
                selected_profiles.append(profile_dict[pid])
            else:
                logging.warning(f"Participant ID {pid} not found in profiles")
        profiles = selected_profiles

    # Slice if start_idx and num_agents specified
    elif num_agents is not None:
        profiles = profiles[start_idx : start_idx + num_agents]

    return profiles


def load_sre_traits_from_data(
    participant_id: int, sre_data_dir: str | None = None
) -> tuple[list[dict], list[str]]:
    """
    Load SRE traits from actual data files (optional).
    If data file not found, returns None to use default traits.

    Args:
        participant_id: Participant ID
        sre_data_dir: Directory containing SRE data CSV files

    Returns:
        Tuple of (encoding_traits, recognition_traits) or (None, None) if not found
    """
    if sre_data_dir is None:
        # Default path: relative to workspace root
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        workspace_root = os.path.dirname(
            os.path.dirname(os.path.dirname(current_file_dir))
        )
        sre_data_dir = os.path.join(
            workspace_root,
            "Self_bias_dataset",
            "1.Self_reference_effect_(SRE)",
            "Data_of_each_participant",
        )

    # Try to find CSV file for this participant
    pattern = os.path.join(sre_data_dir, f"{participant_id}_SRE_*.csv")
    csv_files = glob.glob(pattern)

    if not csv_files:
        return None, None

    # Use the first matching file
    csv_file = csv_files[0]

    try:
        encoding_traits = []
        recognition_traits = []
        encoding_trait_set = set()

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                trait = row.get("trait", "").strip()
                phase = row.get("phase", "").strip()

                if not trait:
                    continue

                # Encoding phase
                if phase == "encoding":
                    identity_name = row.get("identity_name", "").strip()
                    valence = row.get("valence", "").strip()

                    if identity_name in ["self", "friend", "other"]:
                        encoding_traits.append(
                            {
                                "trait": trait,
                                "identity": identity_name,
                                "valence": int(valence) if valence else 1,
                            }
                        )
                        encoding_trait_set.add(trait)

                # Recognition phase - collect all unique traits
                elif phase == "recognition":
                    if trait not in recognition_traits:
                        recognition_traits.append(trait)

        # If recognition traits not found in recognition phase, use encoding traits
        if not recognition_traits:
            recognition_traits = list(encoding_trait_set)

        return encoding_traits, recognition_traits

    except Exception as e:
        logging.warning(f"Failed to load SRE traits from {csv_file}: {e}")
        return None, None


async def main(
    logger,
    num_agents: int = 5,
    profile_start_idx: int = 0,
    participant_ids: list[int] | None = None,
    profiles_dir: str | None = None,
    num_steps: int = 20,
    tick_seconds: int = 60,
    use_data_traits: bool = False,
):
    """
    Run Self-Reference Effect experiment using txt profile files.

    Experiment setup:
    - Encoding Phase: Agents rate trait adjectives (1-5) associated with identities
    - Recognition Phase: Agents judge whether traits were in encoding phase (old/new)
    - Results are saved to JSON and CSV files

    Args:
        logger: Logger instance
        num_agents: Number of agents (if participant_ids not specified)
        profile_start_idx: Start index (if participant_ids not specified)
        participant_ids: Specified participant ID list (optional, e.g., [101, 102, 103])
        profiles_dir: Profile files directory path (optional, default uses relative path)
        num_steps: Number of simulation steps (default: 20)
        tick_seconds: Seconds per step (default: 60)
        use_data_traits: Whether to load traits from actual SRE data files (default: False)
    """
    logger.info("\n" + "=" * 80)
    logger.info("Self-Reference Effect (SRE) Experiment")
    logger.info("=" * 80)
    logger.info("Experiment Configuration:")
    logger.info(f"  - Number of steps: {num_steps}")
    logger.info(f"  - Seconds per step: {tick_seconds}")
    logger.info(
        f"  - Agent count: {num_agents if participant_ids is None else len(participant_ids)}"
    )
    logger.info(f"  - Use data traits: {use_data_traits}")
    logger.info("=" * 80)

    # Experiment parameters
    START_TIME = datetime.now()
    TIME_STEP_SECONDS = tick_seconds
    TOTAL_STEPS = num_steps

    # Storage for cleanup
    sre_env = None
    env_router = None
    agents = []

    # ==================== Load Profiles ====================
    logger.info(
        "\n[Step 1/5] Loading profile txt files (Profile Summary section only)..."
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

    # ==================== Load SRE Traits ====================
    logger.info("\n[Step 2/5] Loading SRE traits list...")

    encoding_traits = None
    recognition_traits = None

    if use_data_traits and participant_ids:
        # Try to load traits from first participant's data file
        first_pid = participant_ids[0]
        encoding_traits, recognition_traits = load_sre_traits_from_data(first_pid)

        if encoding_traits:
            logger.info(
                f"  [OK] Loaded {len(encoding_traits)} encoding traits from data file"
            )
            logger.info(
                f"  [OK] Loaded {len(recognition_traits)} recognition traits from data file"
            )
        else:
            logger.info("  [WARNING] Data file not found, will use default traits list")
    else:
        logger.info("  [OK] Using default traits list")

    # ==================== Initialize Environment ====================
    logger.info("\n[Step 3/5] Initializing environment...")

    # Create temporary directory for chroma memories
    import tempfile

    chroma_base_dir = tempfile.mkdtemp(prefix="chroma_sre_")
    logger.info(f"  [OK] Created temporary chroma directory: {chroma_base_dir}")

    # Create SelfReferenceEffectEnv
    sre_env = SelfReferenceEffectEnv(
        agent_ids=actual_agent_ids,
        encoding_traits=encoding_traits,
        recognition_traits=recognition_traits,
    )

    logger.info(f"  [OK] Encoding traits count: {len(sre_env.encoding_traits)}")
    logger.info(f"  [OK] Recognition traits count: {len(sre_env.recognition_traits)}")

    # ==================== Create Agents ====================
    logger.info(f"\n[Step 4/5] Creating {len(profiles)} agents...")

    agent_args = []

    for profile in profiles:
        agent_id = profile["id"]
        profile_text = profile["profile_text"]  # Only Profile Summary section

        # Create agent (using only Profile Summary section)
        agent_args.append(
            {
                "id": agent_id,
                "profile": profile_text,  # Only Profile Summary
            }
        )

    # Create CodeGenRouter
    env_router = CodeGenRouter(env_modules=[sre_env])

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
        f"\n[Step 5/5] Running experiment ({TOTAL_STEPS} steps, {TIME_STEP_SECONDS} seconds per step)..."
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

    # Get all results from environment
    results = sre_env.get_results()

    encoding_ratings = results["encoding_ratings"]
    recognition_judgments = results["recognition_judgments"]

    logger.info(
        f"  [OK] Extracted encoding results from {len(encoding_ratings)} agents"
    )
    logger.info(
        f"  [OK] Extracted recognition results from {len(recognition_judgments)} agents"
    )

    # Check completion status
    for agent_id in actual_agent_ids:
        encoding_count = len(encoding_ratings.get(agent_id, []))
        recognition_count = len(recognition_judgments.get(agent_id, []))
        logger.info(
            f"  Agent {agent_id}: Encoding {encoding_count}/{len(sre_env.encoding_traits)}, Recognition {recognition_count}/{len(sre_env.recognition_traits)}"
        )

        if encoding_count < len(sre_env.encoding_traits):
            logger.warning("    [WARNING] Encoding phase not completed")
        if recognition_count < len(sre_env.recognition_traits):
            logger.warning("    [WARNING] Recognition phase not completed")

    # ==================== Save Results ====================
    logger.info("\n[Saving Results]")

    output_dir = "sre_experiment_results"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save as JSON
    json_file = os.path.join(output_dir, f"sre_results_{timestamp}.json")
    json_data = {
        "results": {
            "encoding_ratings": {
                str(agent_id): ratings for agent_id, ratings in encoding_ratings.items()
            },
            "recognition_judgments": {
                str(agent_id): judgments
                for agent_id, judgments in recognition_judgments.items()
            },
        },
        "metadata": {
            "num_agents": len(profiles),
            "actual_agent_ids": actual_agent_ids,
            "total_steps": TOTAL_STEPS,
            "time_step_seconds": TIME_STEP_SECONDS,
            "start_time": START_TIME.isoformat(),
            "timestamp": timestamp,
            "profiles_dir": profiles_dir,
            "profile_files": [p["filename"] for p in profiles],
            "encoding_traits_count": len(sre_env.encoding_traits),
            "recognition_traits_count": len(sre_env.recognition_traits),
        },
    }

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    logger.info(f"  [OK] JSON results saved to: {json_file}")

    # Save as CSV (aligned with original SRE data format)
    csv_file = os.path.join(output_dir, f"sre_results_{timestamp}.csv")

    # Prepare CSV data - flatten results for each agent
    csv_rows = []
    for agent_id in actual_agent_ids:
        # Encoding phase data
        agent_encoding = encoding_ratings.get(agent_id, [])
        for rating_data in agent_encoding:
            row = {
                "ID": agent_id,
                "phase": "encoding",
                "trait": rating_data["trait"],
                "identity": rating_data["identity"],
                "rating_encoding.response": rating_data["rating"],
            }
            csv_rows.append(row)

        # Recognition phase data
        agent_recognition = recognition_judgments.get(agent_id, [])
        for judgment_data in agent_recognition:
            row = {
                "ID": agent_id,
                "phase": "recognition",
                "trait": judgment_data["trait"],
                "judge_type": judgment_data["judge_type"],
                "key_resp_recognition.corr": 1 if judgment_data["is_correct"] else 0,
                "RK_type": judgment_data.get("rk_type", ""),
            }
            csv_rows.append(row)

    # Write CSV
    if csv_rows:
        fieldnames = [
            "ID",
            "phase",
            "trait",
            "identity",
            "rating_encoding.response",
            "judge_type",
            "key_resp_recognition.corr",
            "RK_type",
        ]
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

    logger.info(f"  [OK] CSV results saved to: {csv_file}")

    # Print summary statistics
    logger.info("\n[Statistics]")
    all_encoding_ratings = []
    all_recognition_correct = []
    for agent_id in actual_agent_ids:
        agent_encoding = encoding_ratings.get(agent_id, [])
        agent_recognition = recognition_judgments.get(agent_id, [])

        all_encoding_ratings.extend([r["rating"] for r in agent_encoding])
        all_recognition_correct.extend([j["is_correct"] for j in agent_recognition])

    if all_encoding_ratings:
        import numpy as np

        logger.info(f"  - Total encoding ratings: {len(all_encoding_ratings)}")
        logger.info(f"  - Average encoding rating: {np.mean(all_encoding_ratings):.2f}")
        logger.info(f"  - Encoding rating std dev: {np.std(all_encoding_ratings):.2f}")

    if all_recognition_correct:
        import numpy as np

        logger.info(f"  - Total recognition judgments: {len(all_recognition_correct)}")
        logger.info(f"  - Recognition accuracy: {np.mean(all_recognition_correct):.2%}")

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
        log_dir, f"sre_experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
            num_steps=20,
            tick_seconds=150,
            use_data_traits=False,
        )
    )
