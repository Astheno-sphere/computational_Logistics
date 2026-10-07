#!/usr/bin/env python
"""
Prisoner's Dilemma Game - V2 Framework Implementation
Main entry point for running Prisoner's Dilemma game using V2 framework
"""

import asyncio
import json
import logging
import os
from collections import defaultdict
from datetime import datetime

# Disable telemetry before any imports
os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

# V2 framework imports
from agentsociety2.contrib.env.prisoners_dilemma import PrisonersDilemmaEnv
from agentsociety2.env import CodeGenRouter
from agentsociety2.society import AgentSociety

# Ensure results directory exists
os.makedirs("result_prisoners_dilemma", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("llm_api_log.txt"), logging.StreamHandler()],
)


def calculate_and_print_statistics(
    per_game_payoffs,
    total_actions,
    round_action_counts,
    agent_names,
    num_rounds,
    save_dir,
):
    """Calculate and print statistics"""
    try:
        # Calculate total payoffs
        total_payoffs = {name: 0 for name in agent_names}
        for payoffs in per_game_payoffs:
            for name in agent_names:
                total_payoffs[name] += payoffs.get(name, 0)

        # Calculate cooperation rates
        cooperation_counts = {name: 0 for name in agent_names}
        total_action_counts = {name: 0 for name in agent_names}

        for name in agent_names:
            for action in total_actions.get(name, []):
                total_action_counts[name] += 1
                if action == "Yes":
                    cooperation_counts[name] += 1

        cooperation_rates = {
            name: (
                (cooperation_counts[name] / total_action_counts[name] * 100)
                if total_action_counts[name] > 0
                else 0
            )
            for name in agent_names
        }

        # Calculate cooperation rate per round
        round_cooperation_rates = {}
        for round_num in range(1, num_rounds + 1):
            round_cooperation_rates[round_num] = {}
            for name in agent_names:
                round_actions = round_action_counts.get(name, {}).get(round_num, [])
                if round_actions:
                    round_coop_count = sum(1 for a in round_actions if a == "Yes")
                    round_cooperation_rates[round_num][name] = (
                        round_coop_count / len(round_actions) * 100
                    )
                else:
                    round_cooperation_rates[round_num][name] = 0

        # Print statistics
        print("\n===== Cooperation Statistics =====")
        print(f"Total games: {len(per_game_payoffs)}")
        print(f"Total rounds per game: {num_rounds}")

        print("\nOverall cooperation rates:")
        for name in agent_names:
            print(f"  {name}: {cooperation_rates[name]:.2f}%")

        print("\nRound-by-round cooperation rates:")
        for round_num in sorted(round_cooperation_rates.keys()):
            print(f"  Round {round_num}:")
            for name in agent_names:
                rate = round_cooperation_rates[round_num].get(name, 0)
                print(f"    {name}: {rate:.2f}%")

        print("\nTotal payoffs across all games:")
        for name in agent_names:
            print(f"  {name}: {total_payoffs[name]} points")
        overall_total = sum(total_payoffs.values())
        print(f"  Overall total: {overall_total} points")

        # Determine cooperation level
        avg_cooperation_rate = (
            sum(cooperation_rates.values()) / len(cooperation_rates)
            if cooperation_rates
            else 0
        )
        if avg_cooperation_rate <= 20:
            cooperation_level = "Low cooperation (mostly defection)"
        elif avg_cooperation_rate >= 80:
            cooperation_level = "High cooperation (mostly cooperation)"
        else:
            cooperation_level = "Moderate cooperation"
        print(f"\nCooperation Level: {cooperation_level}")

        # Create statistics dictionary
        statistics = {
            "total_games": len(per_game_payoffs),
            "total_rounds_per_game": num_rounds,
            "cooperation_rates": cooperation_rates,
            "round_cooperation_rates": round_cooperation_rates,
            "total_payoffs": total_payoffs,
            "overall_total_payoff": overall_total,
            "cooperation_level": cooperation_level,
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
    """Main entry point for Prisoner's Dilemma game using V2 framework"""
    # ------- Create main results directory and current experiment directory -------
    experiment_time = input(
        "Please enter experiment folder name (e.g., 'PD_v2_test1'): "
    ).strip()
    if not experiment_time:
        experiment_time = datetime.now().strftime("%m%d_%H%M%S_PD_v2")
    base_result_dir = "result_prisoners_dilemma"
    experiment_result_dir = os.path.join(base_result_dir, f"result_{experiment_time}")
    os.makedirs(experiment_result_dir, exist_ok=True)
    logging.info(f"Experiment results will be saved to: {experiment_result_dir}")

    # ------- Set game parameters -------
    NUM_GAMES = 5
    NUM_ROUNDS = 10
    NUM_AGENTS = 2  # Prisoner's Dilemma is a 2-player game
    PAYOFF_CC = 3
    PAYOFF_CD = 0
    PAYOFF_DC = 5
    PAYOFF_DD = 1

    # Record experiment configuration
    experiment_config = {
        "experiment_type": "v2_framework_prisoners_dilemma",
        "experiment_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "num_games": NUM_GAMES,
        "num_rounds_per_game": NUM_ROUNDS,
        "num_agents": NUM_AGENTS,
        "payoff_cc": PAYOFF_CC,
        "payoff_cd": PAYOFF_CD,
        "payoff_dc": PAYOFF_DC,
        "payoff_dd": PAYOFF_DD,
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
    total_actions = {"Agent A": [], "Agent B": []}
    round_action_counts = {"Agent A": defaultdict(list), "Agent B": defaultdict(list)}
    per_game_payoffs = []  # List of dicts, e.g., [{"Agent A": X, "Agent B": Y}, ...]

    # ------- Game loop -------
    for game_num in range(1, NUM_GAMES + 1):
        print(f"\n================ Game {game_num}/{NUM_GAMES} ================")
        logging.info(f"Starting game {game_num}/{NUM_GAMES}")

        # Create environment module
        env_module = PrisonersDilemmaEnv(
            payoff_cc=PAYOFF_CC,
            payoff_cd=PAYOFF_CD,
            payoff_dc=PAYOFF_DC,
            payoff_dd=PAYOFF_DD,
        )

        # Create environment router
        env_router = CodeGenRouter(env_modules=[env_module])
        # Create agent specs (workspace-bound; no direct Agent(...))
        agent_names = ["Agent A", "Agent B"]
        agent_specs = [
            {"id": i + 1, "profile": {"id": i + 1, "name": name}, "config": {}}
            for i, name in enumerate(agent_names)
        ]

        # Create AgentSociety
        start_time = datetime.now()
        society = None
        try:
            society = AgentSociety(
                agent_specs=agent_specs,
                agent_class_name="PrisonersDilemmaAgent",
                env_router=env_router,
                start_t=start_time,
            )
            await society.init()

            log_records = []
            game_payoffs = {"Agent A": 0, "Agent B": 0}

            # ------- Round loop -------
            for round_num in range(1, NUM_ROUNDS + 1):
                print(f"\n--- Round {round_num}/{NUM_ROUNDS} (Game {game_num}) ---")
                logging.info(f"Game {game_num} Round {round_num} started")

                try:
                    # Execute one step - agents will submit actions via step() method
                    # Each agent's step() will query environment and submit action
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
                        agent_a_action = latest_round.get("agent_a_action", "")
                        agent_b_action = latest_round.get("agent_b_action", "")
                        agent_a_payoff = latest_round.get("agent_a_payoff", 0)
                        agent_b_payoff = latest_round.get("agent_b_payoff", 0)

                        # Update statistics
                        game_payoffs["Agent A"] += agent_a_payoff
                        game_payoffs["Agent B"] += agent_b_payoff

                        # Record actions
                        if agent_a_action in ["Yes", "No"]:
                            total_actions["Agent A"].append(agent_a_action)
                            round_action_counts["Agent A"][round_num].append(
                                agent_a_action
                            )
                        if agent_b_action in ["Yes", "No"]:
                            total_actions["Agent B"].append(agent_b_action)
                            round_action_counts["Agent B"][round_num].append(
                                agent_b_action
                            )

                        # Build log records
                        log_records.append(
                            {
                                "round": round_num,
                                "Agent A": {
                                    "action": agent_a_action,
                                    "payoff": agent_a_payoff,
                                    "cumulative_payoff": game_payoffs["Agent A"],
                                },
                                "Agent B": {
                                    "action": agent_b_action,
                                    "payoff": agent_b_payoff,
                                    "cumulative_payoff": game_payoffs["Agent B"],
                                },
                                "timestamp": datetime.now().isoformat(),
                            }
                        )

                        print(
                            f"Agent A: {agent_a_action} ({agent_a_payoff} pts, cumulative: {game_payoffs['Agent A']} pts)"
                        )
                        print(
                            f"Agent B: {agent_b_action} ({agent_b_payoff} pts, cumulative: {game_payoffs['Agent B']} pts)"
                        )
                        logging.info(
                            f"Game {game_num} Round {round_num} ended, Agent A: {agent_a_action} ({agent_a_payoff} pts), Agent B: {agent_b_action} ({agent_b_payoff} pts)"
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
                print(f"  {agent_name}: {game_payoffs[agent_name]} points")
            total_game_payoff = sum(game_payoffs.values())
            print(f"Total payoff for all agents: {total_game_payoff} points")

            # Save this game's payoffs
            per_game_payoffs.append(game_payoffs.copy())

        finally:
            # Clean up
            if society:
                await society.close()

    # ------- End of all games -------
    # Save overall results
    overall_results = {
        "experiment_settings": experiment_config,
        "per_game_payoffs": per_game_payoffs,
        "total_actions": total_actions,
        "round_action_counts": {k: dict(v) for k, v in round_action_counts.items()},
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
        total_actions,
        round_action_counts,
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
