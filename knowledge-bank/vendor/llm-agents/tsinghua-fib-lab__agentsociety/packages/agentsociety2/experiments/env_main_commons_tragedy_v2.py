#!/usr/bin/env python
"""
Tragedy of the Commons Game - V2 Framework Implementation
Main entry point for running Commons Tragedy game using V2 framework
"""

import asyncio
import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Disable telemetry before any imports
os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

# V2 framework imports
from agentsociety2.contrib.env.commons_tragedy import CommonsTragedyEnv
from agentsociety2.env import CodeGenRouter
from agentsociety2.society import AgentSociety

# Ensure results directory exists
os.makedirs("result_commons_tragedy", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("llm_api_log.txt"), logging.StreamHandler()],
)


def calculate_and_print_statistics(
    per_game_payoffs,
    total_extractions,
    round_extractions,
    pool_resources_history,
    agent_names,
    save_dir,
):
    """Calculate and print statistics"""
    try:
        # Calculate total payoffs
        total_payoffs = {name: 0 for name in agent_names}
        for payoffs in per_game_payoffs:
            for name in agent_names:
                total_payoffs[name] += payoffs.get(name, 0)

        # Calculate average extraction
        average_extraction = (
            sum(total_extractions) / len(total_extractions) if total_extractions else 0
        )

        # Calculate average extraction per round
        round_avg_extractions = {}
        for round_num, extractions in round_extractions.items():
            round_avg_extractions[round_num] = (
                sum(extractions) / len(extractions) if extractions else 0
            )

        # Print statistics
        print("\n===== Extraction Statistics =====")
        print(f"Total games: {len(per_game_payoffs)}")
        print(f"Total rounds: {len(total_extractions) // len(agent_names)}")
        print(f"Average extraction per agent per round: {average_extraction:.2f} units")

        print("\nRound average extractions:")
        for round_num in sorted(round_avg_extractions.keys()):
            print(
                f"  Round {round_num}: {round_avg_extractions[round_num]:.2f} units/agent"
            )

        print("\nTotal payoffs across all games:")
        for name in agent_names:
            print(f"  {name}: {total_payoffs[name]} points")
        overall_total = sum(total_payoffs.values())
        print(f"  Overall total: {overall_total} points")

        # Create statistics dictionary
        statistics = {
            "total_rounds": len(total_extractions) // len(agent_names),
            "total_games": len(per_game_payoffs),
            "average_extraction_per_agent_per_round": average_extraction,
            "round_average_extractions": round_avg_extractions,
            "total_payoffs": total_payoffs,
            "overall_total_payoff": overall_total,
            "pool_resources_history": pool_resources_history,
        }

        # Save statistics to file
        stats_file_path = os.path.join(save_dir, "statistics.json")
        try:
            with open(stats_file_path, "w", encoding="utf-8") as f:
                json.dump(statistics, f, indent=2, ensure_ascii=False, default=str)
            logging.info(f"Statistics saved to {stats_file_path}")
        except Exception as e:
            logging.error(f"Failed to save statistics: {e}")

        return statistics

    except Exception as e:
        logging.error(f"Error calculating statistics: {e}")
        return None


async def main():
    """Main entry point for Commons Tragedy game using V2 framework"""
    # ------- Create main results directory and current experiment directory -------
    experiment_time = input(
        "Please enter experiment folder name (e.g., 'ToC_v2_test1'): "
    ).strip()
    if not experiment_time:
        experiment_time = datetime.now().strftime("%m%d_%H%M%S_ToC_v2")
    base_result_dir = "result_commons_tragedy"
    experiment_result_dir = os.path.join(base_result_dir, f"result_{experiment_time}")
    os.makedirs(experiment_result_dir, exist_ok=True)
    logging.info(f"Experiment results will be saved to: {experiment_result_dir}")

    # ------- Set game parameters -------
    NUM_GAMES = 5
    NUM_ROUNDS = 10
    NUM_AGENTS = 4
    INITIAL_POOL_RESOURCES = 100
    MAX_EXTRACTION_PER_AGENT = 10

    # Record experiment configuration
    experiment_config = {
        "experiment_type": "v2_framework_commons_tragedy",
        "experiment_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "num_games": NUM_GAMES,
        "num_rounds_per_game": NUM_ROUNDS,
        "num_agents": NUM_AGENTS,
        "initial_pool_resources": INITIAL_POOL_RESOURCES,
        "max_extraction_per_agent": MAX_EXTRACTION_PER_AGENT,
        "result_dir": experiment_result_dir,
    }

    # Save experiment configuration
    config_path = os.path.join(experiment_result_dir, "experiment_config.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(experiment_config, f, indent=2, ensure_ascii=False)
        logging.info(f"Experiment configuration saved to: {config_path}")
    except Exception as e:
        logging.error(f"Failed to save experiment configuration: {e}")

    # ------- Statistical variables -------
    total_extractions = []
    round_extractions = defaultdict(list)
    per_game_payoffs = []
    total_payoffs = defaultdict(int)
    pool_resources_history_per_game = []

    # ------- Game loop -------
    for game_num in range(1, NUM_GAMES + 1):
        print(f"\n================ Game {game_num} ===============\n")
        logging.info(f"Starting game {game_num}/{NUM_GAMES}")

        # Create environment module
        env_module = CommonsTragedyEnv(
            num_agents=NUM_AGENTS,
            initial_pool_resources=INITIAL_POOL_RESOURCES,
            max_extraction_per_agent=MAX_EXTRACTION_PER_AGENT,
        )

        # Create environment router
        env_router = CodeGenRouter(env_modules=[env_module])
        # Create agent specs (workspace-bound; no direct Agent(...))
        agent_names = [f"Agent {i + 1}" for i in range(NUM_AGENTS)]
        agent_specs = [
            {"id": i + 1, "profile": {"id": i + 1, "name": name}, "config": {}}
            for i, name in enumerate(agent_names)
        ]

        # Create AgentSociety
        start_time = datetime.now()
        society = None
        try:
            # Create replay writer for this game
            game_run_dir = Path(experiment_result_dir) / f"game_{game_num}"
            game_run_dir.mkdir(parents=True, exist_ok=True)

            from agentsociety2.storage import ReplayWriter

            replay_writer = ReplayWriter(game_run_dir / "replay.db")
            await replay_writer.init()

            society = AgentSociety(
                agent_specs=agent_specs,
                agent_class_name="CommonsTragedyAgent",
                env_router=env_router,
                start_t=start_time,
                run_dir=game_run_dir,
                enable_replay=True,
            )
            await society.init()

            log_records = []
            current_game_pool_history = []
            game_payoffs = {name: 0 for name in agent_names}
            _game_round_results = []

            # ------- Round loop -------
            for round_num in range(1, NUM_ROUNDS + 1):
                print(f"\n--- Round {round_num} of Game {game_num} ---")

                # Get current pool resources before round
                ctx = {}
                ctx, pool_response = await env_router.ask(
                    ctx,
                    "Please call get_pool_resources() to get the current pool resources.",
                    readonly=True,
                )

                # Parse pool resources
                import re

                pool_before = INITIAL_POOL_RESOURCES
                try:
                    json_match = re.search(r"\{[^}]+\}", pool_response)
                    if json_match:
                        data = json.loads(json_match.group(0))
                        if isinstance(data, dict):
                            pool_before = data.get(
                                "current_pool_resources", INITIAL_POOL_RESOURCES
                            )
                except Exception:
                    pass

                print(f"Resource pool before round: {pool_before} units")
                logging.info(
                    f"Game {game_num} Round {round_num} started, resource pool: {pool_before} units"
                )

                try:
                    # Execute one step - agents will submit extractions via step() method
                    # Each agent's step() will query environment and submit extraction
                    # Society.step() will call all agents' step() first, then environment's step()
                    await asyncio.wait_for(
                        society.step(tick=1),  # tick=1 for one round
                        timeout=300.0,  # 5 minute timeout per round
                    )

                    # After step, directly access environment module's round history
                    # This is more reliable than parsing string responses
                    latest_round = None
                    try:
                        # Directly access the environment module's round history
                        if (
                            env_module.round_history
                            and len(env_module.round_history) > 0
                        ):
                            # Find the round matching current round_num
                            for r in reversed(env_module.round_history):
                                if r.get("round") == round_num:
                                    latest_round = r
                                    break
                            # If not found, use the latest round
                            if latest_round is None:
                                latest_round = env_module.round_history[-1]
                        else:
                            logging.warning(
                                f"Game {game_num} Round {round_num}: No round history available"
                            )
                    except Exception as e:
                        logging.warning(f"Failed to get round history: {e}")
                        import traceback

                        traceback.print_exc()

                    if latest_round:
                        _round_num_from_env = latest_round.get("round", round_num)
                        actual_extractions = latest_round.get("extractions", {})
                        pool_after = latest_round.get("pool_after_round", pool_before)
                        payoffs = latest_round.get("payoffs", {})

                        # Update statistics
                        for agent_name in agent_names:
                            actual_extraction = actual_extractions.get(agent_name, 0)
                            total_extractions.append(actual_extraction)
                            round_extractions[round_num].append(actual_extraction)
                            game_payoffs[agent_name] += actual_extraction
                            total_payoffs[agent_name] += actual_extraction

                        # Record resource pool history
                        current_game_pool_history.append(pool_after)

                        # Build log records
                        agent_round_data = {}
                        for agent_name in agent_names:
                            agent_round_data[agent_name] = {
                                "actual_extraction": actual_extractions.get(
                                    agent_name, 0
                                ),
                                "payoff": payoffs.get(agent_name, 0),
                            }
                            print(
                                f"{agent_name}: Extracted {actual_extractions.get(agent_name, 0)} units "
                                f"({payoffs.get(agent_name, 0)} points)"
                            )

                        log_records.append(
                            {
                                "round": round_num,
                                "pool_before_round": pool_before,
                                "current_pool_after_round": pool_after,
                                "agents_data": agent_round_data,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                        print(
                            f"Resource pool after round {round_num}: {pool_after} units"
                        )
                        logging.info(
                            f"Game {game_num} Round {round_num} ended, remaining resource pool: {pool_after} units"
                        )
                    else:
                        logging.warning(
                            f"Game {game_num} Round {round_num}: Could not parse round result from history"
                        )

                except TimeoutError:
                    logging.error(
                        f"Game {game_num} Round {round_num} execution timeout"
                    )
                    print(
                        f"[Error] Round {round_num} execution timeout, skipping this round"
                    )
                    continue
                except Exception as e:
                    logging.error(
                        f"Game {game_num} Round {round_num} execution error: {e}"
                    )
                    print(f"[Error] Round {round_num} execution error: {e!s}")
                    import traceback

                    traceback.print_exc()
                    continue

            # ------- Save each game's logs -------
            game_log_path = os.path.join(
                experiment_result_dir, f"game_{game_num}_logs.json"
            )
            try:
                with open(game_log_path, "w", encoding="utf-8") as f:
                    json.dump(log_records, f, indent=2, ensure_ascii=False)
                logging.info(f"Game {game_num} logs saved to: {game_log_path}")
            except Exception as e:
                logging.error(f"Failed to save game {game_num} logs: {e}")

            print(f"\nGame {game_num} completed.")

            # Save this game's payoffs
            per_game_payoffs.append(game_payoffs.copy())
            total_game_payoff_sum = sum(game_payoffs.values())
            print(f"Game {game_num} payoffs:")
            for agent_name in agent_names:
                print(f"  {agent_name} = {game_payoffs[agent_name]} points")
            print(f"  Total points for this game = {total_game_payoff_sum} points")
            pool_resources_history_per_game.append(current_game_pool_history)

        finally:
            # Clean up
            if society:
                await society.close()

    # After all games are completed, print total payoff summary
    print("\n========== All Games Summary ==========")
    for idx, payoffs in enumerate(per_game_payoffs, 1):
        total_game_payoff_sum = sum(payoffs.values())
        print(
            f"Game {idx}: "
            + ", ".join([f"{name}={pts} points" for name, pts in payoffs.items()])
            + f", Total = {total_game_payoff_sum} points"
        )

    print("\nTotal payoffs across all games:")
    overall_total_payoff_sum = sum(total_payoffs.values())
    for agent_name in agent_names:
        print(f"  {agent_name} total: {total_payoffs[agent_name]} points")
    print(f"  Overall total: {overall_total_payoff_sum} points")

    # Calculate and print statistics
    statistics = calculate_and_print_statistics(
        per_game_payoffs,
        total_extractions,
        round_extractions,
        pool_resources_history_per_game,
        agent_names,
        experiment_result_dir,
    )

    if statistics:
        logging.info("Experiment statistics calculated and saved")

    # Save overall experiment summary
    summary_path = os.path.join(experiment_result_dir, "experiment_summary.json")
    try:
        summary_data = experiment_config.copy()
        summary_data.update(
            {
                "total_payoffs": dict(total_payoffs),
                "per_game_payoffs": per_game_payoffs,
                "statistics": statistics,
            }
        )
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
        logging.info(f"Experiment summary saved to: {summary_path}")
    except Exception as e:
        logging.error(f"Failed to save experiment summary: {e}")

    print(f"\nExperiment completed! All results saved to: {experiment_result_dir}")
    logging.info("Experiment execution completed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted by user")
    except Exception as e:
        print(f"Program error occurred: {e}")
        import traceback

        traceback.print_exc()
