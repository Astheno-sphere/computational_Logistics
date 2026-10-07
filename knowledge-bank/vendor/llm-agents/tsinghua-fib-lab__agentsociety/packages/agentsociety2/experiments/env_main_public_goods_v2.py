#!/usr/bin/env python
"""
Public Goods Game - V2 Framework Implementation
Main entry point for running Public Goods Game using V2 framework
"""

import asyncio
import json
import logging
import os
from collections import defaultdict
from datetime import datetime

import numpy as np

# Disable telemetry before any imports
os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

# V2 framework imports
from agentsociety2.contrib.env.public_goods import PublicGoodsEnv
from agentsociety2.env import CodeGenRouter
from agentsociety2.society import AgentSociety

# Ensure results directory exists
os.makedirs("result_public_goods", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("llm_api_log.txt"), logging.StreamHandler()],
)


def calculate_and_print_statistics(
    per_game_payoffs,
    all_game_round_contributions,
    public_pool_total_contributions_history_per_game,
    agent_names,
    num_rounds,
    initial_endowment,
    save_dir,
):
    """Calculate and print statistics"""
    try:
        # Calculate total payoffs
        total_payoffs = {name: 0 for name in agent_names}
        for payoffs in per_game_payoffs:
            for name in agent_names:
                total_payoffs[name] += payoffs.get(name, 0)

        # Calculate average contribution per round across all games
        avg_contributions_per_round = []
        for round_num in range(1, num_rounds + 1):
            if round_num in all_game_round_contributions:
                contributions = all_game_round_contributions[round_num]
                avg_contrib = np.mean(contributions)
                avg_contributions_per_round.append(avg_contrib)

        # Calculate overall average contribution
        overall_avg_contribution = (
            np.mean(avg_contributions_per_round) if avg_contributions_per_round else 0
        )

        # Print statistics
        print("\n===== Contribution Statistics =====")
        print(f"Total games: {len(per_game_payoffs)}")
        print(f"Total rounds per game: {num_rounds}")
        print(
            f"Overall average contribution per agent per round: {overall_avg_contribution:.2f} coins"
        )

        print("\nRound average contributions:")
        for round_num, avg_contrib in enumerate(avg_contributions_per_round, 1):
            print(f"  Round {round_num}: {avg_contrib:.2f} coins/agent")

        print("\nTotal payoffs across all games:")
        for name in agent_names:
            print(f"  {name}: {total_payoffs[name]:.2f} coins")
        overall_total = sum(total_payoffs.values())
        print(f"  Overall total: {overall_total:.2f} coins")

        # Determine cooperation level
        if overall_avg_contribution <= initial_endowment * 0.2:
            cooperation_level = (
                "Significant free-riding observed (low average contribution)"
            )
        elif overall_avg_contribution >= initial_endowment * 0.8:
            cooperation_level = (
                "Significant cooperation observed (high average contribution)"
            )
        else:
            cooperation_level = "Moderate contribution or contribution decay observed"
        print(f"\nCooperation Level: {cooperation_level}")

        # Create statistics dictionary
        statistics = {
            "total_games": len(per_game_payoffs),
            "total_rounds_per_game": num_rounds,
            "overall_average_contribution_per_agent_per_round": overall_avg_contribution,
            "round_average_contributions": {
                i + 1: avg for i, avg in enumerate(avg_contributions_per_round)
            },
            "total_payoffs": total_payoffs,
            "overall_total_payoff": overall_total,
            "cooperation_level": cooperation_level,
            "public_pool_total_contributions_history_per_game": public_pool_total_contributions_history_per_game,
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
    """Main entry point for Public Goods Game using V2 framework"""
    # ------- Create main results directory and current experiment directory -------
    experiment_time = input(
        "Please enter experiment folder name (e.g., 'PG_v2_test1'): "
    ).strip()
    if not experiment_time:
        experiment_time = datetime.now().strftime("%m%d_%H%M%S_PG_v2")
    base_result_dir = "result_public_goods"
    experiment_result_dir = os.path.join(base_result_dir, f"result_{experiment_time}")
    os.makedirs(experiment_result_dir, exist_ok=True)
    logging.info(f"Experiment results will be saved to: {experiment_result_dir}")

    # ------- Set game parameters -------
    NUM_GAMES = 5
    NUM_ROUNDS = 10
    NUM_AGENTS = 4
    INITIAL_ENDOWMENT = 20
    PUBLIC_POOL_MULTIPLIER = 1.6

    # Record experiment configuration
    experiment_config = {
        "experiment_type": "v2_framework_public_goods",
        "experiment_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "num_games": NUM_GAMES,
        "num_rounds_per_game": NUM_ROUNDS,
        "num_agents": NUM_AGENTS,
        "initial_endowment": INITIAL_ENDOWMENT,
        "public_pool_multiplier": PUBLIC_POOL_MULTIPLIER,
        "result_dir": experiment_result_dir,
    }

    # Save experiment configuration
    config_path = os.path.join(experiment_result_dir, "experiment_settings.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(experiment_config, f, indent=2, ensure_ascii=False)
        logging.info(f"Experiment configuration saved to: {config_path}")
    except Exception as e:
        logging.error(f"Failed to save experiment configuration: {e}")

    # ------- Statistical variables -------
    all_game_round_contributions = defaultdict(
        list
    )  # Stores individual contributions from all agents across all rounds and all games
    per_game_cumulative_payoffs = []  # List of dicts, e.g., [{"Agent A": X, "Agent B": Y, ...}, ...]
    public_pool_total_contributions_history_per_game = []  # List of lists, each sublist is total contributions per round for one game

    # ------- Game loop -------
    for game_num in range(1, NUM_GAMES + 1):
        print(f"\n================ Game {game_num}/{NUM_GAMES} ================")
        logging.info(f"Starting game {game_num}/{NUM_GAMES}")

        # Create environment module
        env_module = PublicGoodsEnv(
            num_agents=NUM_AGENTS,
            initial_endowment=INITIAL_ENDOWMENT,
            public_pool_multiplier=PUBLIC_POOL_MULTIPLIER,
        )

        # Create environment router
        env_router = CodeGenRouter(env_modules=[env_module])

        # Create agent specs
        agent_names = [f"Agent {chr(65 + i)}" for i in range(NUM_AGENTS)]
        agent_specs = [
            {
                "id": i + 1,
                "profile": {"id": i + 1, "name": name},
                "config": {
                    "num_rounds": NUM_ROUNDS,
                    "num_agents": NUM_AGENTS,
                    "initial_endowment": INITIAL_ENDOWMENT,
                    "public_pool_multiplier": PUBLIC_POOL_MULTIPLIER,
                },
            }
            for i, name in enumerate(agent_names)
        ]

        # Create AgentSociety
        start_time = datetime.now()
        society = None
        try:
            society = AgentSociety(
                agent_specs=agent_specs,
                agent_class_name="PublicGoodsAgent",
                env_router=env_router,
                start_t=start_time,
            )
            await society.init()

            log_records = []
            game_cumulative_payoffs = defaultdict(float)
            current_game_total_contributions = []

            # ------- Round loop -------
            for round_num in range(1, NUM_ROUNDS + 1):
                print(f"\n--- Round {round_num}/{NUM_ROUNDS} (Game {game_num}) ---")
                logging.info(f"Game {game_num} Round {round_num} started")

                try:
                    # Execute one step - agents will submit contributions via step() method
                    # Each agent's step() will query environment and submit contribution
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
                        total_contribution = latest_round.get("total_contribution", 0)
                        public_pool_gain = latest_round.get("public_pool_gain", 0.0)
                        contributions = latest_round.get("contributions", {})
                        payoffs = latest_round.get("payoffs", {})

                        # Calculate gain per agent
                        gain_per_agent = (
                            public_pool_gain / NUM_AGENTS if NUM_AGENTS > 0 else 0
                        )

                        # Update statistics
                        for agent_name in agent_names:
                            payoff = payoffs.get(agent_name, 0.0)
                            game_cumulative_payoffs[agent_name] += payoff

                        # Record total contribution for this round
                        current_game_total_contributions.append(total_contribution)

                        # Record individual contributions for all rounds and games
                        for agent_name in agent_names:
                            contribution = contributions.get(agent_name, 0)
                            all_game_round_contributions[round_num].append(contribution)

                        # Build log records
                        agent_round_data = {}
                        for agent_name in agent_names:
                            contribution = contributions.get(agent_name, 0)
                            payoff = payoffs.get(agent_name, 0.0)
                            agent_round_data[agent_name] = {
                                "contribution": contribution,
                                "payoff": payoff,
                                "cumulative_payoff": game_cumulative_payoffs[
                                    agent_name
                                ],
                            }
                            print(
                                f"{agent_name}: Contributed {contribution} coins, gained {payoff:.2f} coins (cumulative: {game_cumulative_payoffs[agent_name]:.2f})"
                            )

                        log_records.append(
                            {
                                "round": round_num,
                                "total_contribution": total_contribution,
                                "public_pool_gain": public_pool_gain,
                                "gain_per_agent": gain_per_agent,
                                "agents_data": agent_round_data,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                        print(f"Total contribution: {total_contribution} coins")
                        print(f"Public pool gain: {public_pool_gain:.2f} coins")
                        print(
                            f"Gain per agent from public pool: {gain_per_agent:.2f} coins"
                        )
                        logging.info(
                            f"Game {game_num} Round {round_num} ended, total contribution: {total_contribution}, public pool gain: {public_pool_gain:.2f}"
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

            print(f"\nGame {game_num} Summary:")
            print("Final Cumulative Payoffs:")
            for agent_name in agent_names:
                print(
                    f"  {agent_name}: {game_cumulative_payoffs[agent_name]:.2f} coins"
                )
            total_game_payoff = sum(game_cumulative_payoffs.values())
            print(f"Total payoff for all agents: {total_game_payoff:.2f} coins")

            # Save this game's payoffs
            per_game_cumulative_payoffs.append(dict(game_cumulative_payoffs))
            public_pool_total_contributions_history_per_game.append(
                current_game_total_contributions
            )

        finally:
            # Clean up
            if society:
                await society.close()

    # ------- End of all games -------
    # Save overall results
    overall_results = {
        "experiment_settings": experiment_config,
        "per_game_cumulative_payoffs": per_game_cumulative_payoffs,
        "public_pool_total_contributions_history_per_game": public_pool_total_contributions_history_per_game,
        "all_game_round_contributions": dict(all_game_round_contributions),
        "experiment_time": experiment_time,
    }

    overall_results_path = os.path.join(experiment_result_dir, "overall_results.json")
    try:
        with open(overall_results_path, "w", encoding="utf-8") as f:
            json.dump(overall_results, f, indent=2, ensure_ascii=False)
        logging.info(f"Overall results saved to: {overall_results_path}")
    except Exception as e:
        logging.error(f"Failed to save overall results: {e}")

    # Print overall summary
    print("\n========== Overall Summary ==========")
    print(f"Number of games: {NUM_GAMES}")
    print(f"Number of rounds per game: {NUM_ROUNDS}")
    print(f"Number of agents: {NUM_AGENTS}")

    # Calculate and print statistics
    statistics = calculate_and_print_statistics(
        per_game_cumulative_payoffs,
        all_game_round_contributions,
        public_pool_total_contributions_history_per_game,
        agent_names,
        NUM_ROUNDS,
        INITIAL_ENDOWMENT,
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
                "per_game_cumulative_payoffs": per_game_cumulative_payoffs,
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
