#!/usr/bin/env python
"""
Volunteer's Dilemma Game - V2 Framework Implementation
Main entry point for running Volunteer's Dilemma game using V2 framework
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
from agentsociety2.contrib.env.volunteer_dilemma import VolunteerDilemmaEnv
from agentsociety2.env import CodeGenRouter
from agentsociety2.society import AgentSociety

# Ensure results directory exists
os.makedirs("result_volunteer_dilemma", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("llm_api_log.txt"), logging.StreamHandler()],
)


def calculate_and_print_statistics(
    per_game_payoffs,
    all_game_round_choices,
    at_least_one_volunteer_per_round,
    agent_names,
    num_rounds,
    save_dir,
):
    """Calculate and print statistics"""
    try:
        # Calculate total payoffs per agent
        total_payoffs = {name: 0 for name in agent_names}
        for payoffs in per_game_payoffs:
            for name in agent_names:
                total_payoffs[name] += payoffs.get(name, 0)

        # Print statistics
        print("\n===== Volunteer's Dilemma Statistics =====")
        print(f"Total games: {len(per_game_payoffs)}")
        print(f"Total rounds per game: {num_rounds}")

        # 1. Average volunteer probability per agent per round
        if all_game_round_choices:
            all_choices = [
                choice
                for round_data in all_game_round_choices.values()
                for choice in round_data
            ]
            if all_choices:
                avg_volunteer_prob = np.mean(all_choices)
                print(
                    f"\nAverage 'Volunteer' probability per agent per round: {avg_volunteer_prob:.2%}"
                )

        # 2. Frequency of at least one volunteer per round
        if at_least_one_volunteer_per_round:
            all_standalone_status = [
                status
                for round_data in at_least_one_volunteer_per_round.values()
                for status in round_data
            ]
            if all_standalone_status:
                freq_at_least_one = np.mean(all_standalone_status)
                print(
                    f"Frequency of at least one 'Volunteer' across all rounds/games: {freq_at_least_one:.2%}"
                )

        # 3. Average number of volunteers per round
        if all_game_round_choices:
            avg_num_volunteers = np.mean(
                [np.mean(round_data) for round_data in all_game_round_choices.values()]
            )
            print(f"Average number of volunteers per round: {avg_num_volunteers:.2f}")

        print("\nTotal payoffs across all games:")
        for name in agent_names:
            print(f"  {name}: {total_payoffs[name]:.2f} coins")
        overall_total = sum(total_payoffs.values())
        print(f"  Overall total: {overall_total:.2f} coins")

        # Create statistics dictionary
        statistics = {
            "total_games": len(per_game_payoffs),
            "total_rounds_per_game": num_rounds,
            "avg_volunteer_probability": (
                float(avg_volunteer_prob) if all_game_round_choices else 0
            ),
            "freq_at_least_one_volunteer": (
                float(freq_at_least_one) if at_least_one_volunteer_per_round else 0
            ),
            "avg_num_volunteers": (
                float(avg_num_volunteers) if all_game_round_choices else 0
            ),
            "total_payoffs": total_payoffs,
            "overall_total_payoff": overall_total,
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
    """Main entry point for Volunteer's Dilemma game using V2 framework"""
    # ------- Create main results directory and current experiment directory -------
    experiment_time = input(
        "Please enter experiment folder name (e.g., 'VD_v2_test1'): "
    ).strip()
    if not experiment_time:
        experiment_time = datetime.now().strftime("%m%d_%H%M%S_VD_v2")
    base_result_dir = "result_volunteer_dilemma"
    experiment_result_dir = os.path.join(base_result_dir, f"result_{experiment_time}")
    os.makedirs(experiment_result_dir, exist_ok=True)
    logging.info(f"Experiment results will be saved to: {experiment_result_dir}")

    # ------- Set game parameters -------
    NUM_GAMES = 5
    NUM_ROUNDS = 10
    NUM_AGENTS = 4
    BENEFIT_B = 100  # Benefit for everyone if someone volunteers
    COST_C = 40  # Cost for a volunteer

    # Record experiment configuration
    experiment_config = {
        "experiment_type": "v2_framework_volunteer_dilemma",
        "experiment_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "num_games": NUM_GAMES,
        "num_rounds_per_game": NUM_ROUNDS,
        "num_agents": NUM_AGENTS,
        "benefit_b": BENEFIT_B,
        "cost_c": COST_C,
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
    all_game_round_choices = defaultdict(
        list
    )  # Stores individual choices (0=Stand by, 1=Volunteer) across all rounds and games
    at_least_one_volunteer_per_round = defaultdict(
        list
    )  # Stores whether at least one agent volunteered in each round
    per_game_payoffs = []  # List of dicts with cumulative payoffs for each game

    # ------- Game loop -------
    for game_num in range(1, NUM_GAMES + 1):
        print(f"\n================ Game {game_num}/{NUM_GAMES} ================")
        logging.info(f"Starting game {game_num}/{NUM_GAMES}")

        # Create environment module
        env_module = VolunteerDilemmaEnv(
            num_agents=NUM_AGENTS, benefit_b=BENEFIT_B, cost_c=COST_C
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
                    "benefit_b": BENEFIT_B,
                    "cost_c": COST_C,
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
                agent_class_name="VolunteerDilemmaAgent",
                env_router=env_router,
                start_t=start_time,
            )
            await society.init()

            log_records = []
            game_cumulative_payoffs = defaultdict(float)

            # ------- Round loop -------
            for round_num in range(1, NUM_ROUNDS + 1):
                print(f"\n--- Round {round_num}/{NUM_ROUNDS} (Game {game_num}) ---")
                logging.info(f"Game {game_num} Round {round_num} started")

                try:
                    # Execute one step - agents will submit choices via step() method
                    # Each agent's step() will query environment and submit choice
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
                        choices = latest_round.get("choices", {})
                        num_volunteers = latest_round.get("num_volunteers", 0)
                        payoffs = latest_round.get("payoffs", {})

                        # Update statistics
                        for agent_name in agent_names:
                            game_cumulative_payoffs[agent_name] += payoffs.get(
                                agent_name, 0
                            )

                        # Record choices for statistics
                        # Map choices to numerical values: 1=Volunteer, 0=Stand by
                        numerical_choices = [
                            1 if choices.get(name) == "Volunteer" else 0
                            for name in agent_names
                        ]
                        all_game_round_choices[round_num].extend(numerical_choices)

                        # Record if at least one volunteer
                        is_someone_volunteering = latest_round.get(
                            "is_someone_volunteering", False
                        )
                        at_least_one_volunteer_per_round[round_num].append(
                            1 if is_someone_volunteering else 0
                        )

                        # Build log records
                        agent_round_data = {}
                        for agent_name in agent_names:
                            agent_round_data[agent_name] = {
                                "choice": choices.get(agent_name, "Stand by"),
                                "payoff": payoffs.get(agent_name, 0),
                                "cumulative_payoff": game_cumulative_payoffs[
                                    agent_name
                                ],
                            }
                            print(
                                f"{agent_name}: Chose '{choices.get(agent_name, 'Stand by')}', "
                                f"Round Payoff {payoffs.get(agent_name, 0):.2f} coins, "
                                f"Cumulative Payoff {game_cumulative_payoffs[agent_name]:.2f} coins"
                            )

                        log_records.append(
                            {
                                "round": round_num,
                                "num_volunteers": num_volunteers,
                                "is_someone_volunteering": is_someone_volunteering,
                                "agents_data": agent_round_data,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )

                        print(
                            f"Total volunteers this round: {num_volunteers}. "
                            f"Someone volunteered: {is_someone_volunteering}"
                        )
                        logging.info(
                            f"Game {game_num} Round {round_num} ended, "
                            f"Volunteers: {num_volunteers}, "
                            f"Choices: {choices}"
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
            per_game_payoffs.append(dict(game_cumulative_payoffs))

        finally:
            # Clean up
            if society:
                await society.close()

    # ------- End of all games -------
    # Save overall results
    overall_results = {
        "experiment_settings": experiment_config,
        "per_game_payoffs": per_game_payoffs,
        "all_game_round_choices": {k: v for k, v in all_game_round_choices.items()},
        "at_least_one_volunteer_per_round": {
            k: v for k, v in at_least_one_volunteer_per_round.items()
        },
        "experiment_time": experiment_time,
    }

    overall_results_path = os.path.join(experiment_result_dir, "overall_results.json")
    try:
        with open(overall_results_path, "w", encoding="utf-8") as f:
            json.dump(overall_results, f, indent=2, ensure_ascii=False, default=str)
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
        per_game_payoffs,
        all_game_round_choices,
        at_least_one_volunteer_per_round,
        agent_names,
        NUM_ROUNDS,
        experiment_result_dir,
    )

    if statistics:
        logging.info("Experiment statistics calculated and saved")

    # Save overall experiment summary
    summary_path = os.path.join(experiment_result_dir, "experiment_summary.json")
    try:
        summary_data = experiment_config.copy()
        summary_data.update(
            {"per_game_payoffs": per_game_payoffs, "statistics": statistics}
        )
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2, default=str)
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
