#!/usr/bin/env python
"""
Trust Game - V2 Framework Implementation
Main entry point for running Trust Game using V2 framework
"""

import asyncio
import json
import logging
import os
from datetime import datetime

# Disable telemetry before any imports
os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

# V2 framework imports
from agentsociety2.contrib.env.trust_game import TrustGameEnv
from agentsociety2.env import CodeGenRouter
from agentsociety2.society import AgentSociety

# Ensure results directory exists
os.makedirs("result_trust_game", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("llm_api_log.txt"), logging.StreamHandler()],
)


def calculate_and_print_statistics(
    per_game_payoffs,
    all_game_investments,
    all_game_returns,
    all_game_return_rates,
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

        # Calculate average investment and return rates
        trustor_names = [name for name in agent_names if "Trustor" in name]
        trustee_names = [name for name in agent_names if "Trustee" in name]

        # Calculate average investment per trustor
        # Each game has per-game total investments, calculate average across games
        avg_investments = {}
        for name in trustor_names:
            total_investment = 0
            count = 0
            for investments in all_game_investments:
                # Find matching agent in this game (same base name)
                base_name = name.rsplit("_G", 1)[0] if "_G" in name else name
                for inv_name, inv_value in investments.items():
                    inv_base = (
                        inv_name.rsplit("_G", 1)[0] if "_G" in inv_name else inv_name
                    )
                    if inv_base == base_name:
                        total_investment += inv_value
                        count += 1
                        break
            if count > 0:
                avg_investments[name] = total_investment / count
            else:
                avg_investments[name] = 0

        # Calculate average return rate per trustee
        avg_return_rates = {name: 0 for name in trustee_names}
        return_rate_counts = {name: 0 for name in trustee_names}
        for return_rates in all_game_return_rates:
            for name in trustee_names:
                if name in return_rates:
                    avg_return_rates[name] += return_rates[name]
                    return_rate_counts[name] += 1

        for name in trustee_names:
            if return_rate_counts[name] > 0:
                avg_return_rates[name] /= return_rate_counts[name]

        # Print statistics
        print("\n===== Trust Game Statistics =====")
        print(f"Total games: {len(per_game_payoffs)}")
        print(f"Total rounds per game: {num_rounds}")

        print("\nAverage investments per trustor:")
        for name in trustor_names:
            print(f"  {name}: {avg_investments[name]:.2f} coins")

        print("\nAverage return rates per trustee:")
        for name in trustee_names:
            print(f"  {name}: {avg_return_rates[name]:.1%}")

        print("\nTotal payoffs across all games:")
        for name in agent_names:
            print(f"  {name}: {total_payoffs[name]:.2f} coins")
        overall_total = sum(total_payoffs.values())
        print(f"  Overall total: {overall_total:.2f} coins")

        # Create statistics dictionary
        statistics = {
            "total_games": len(per_game_payoffs),
            "total_rounds_per_game": num_rounds,
            "avg_investments": avg_investments,
            "avg_return_rates": avg_return_rates,
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
    """Main entry point for Trust Game using V2 framework"""
    # ------- Create main results directory and current experiment directory -------
    experiment_time = input(
        "Please enter experiment folder name (e.g., 'TG_v2_test1'): "
    ).strip()
    if not experiment_time:
        experiment_time = datetime.now().strftime("%m%d_%H%M%S_TG_v2")
    base_result_dir = "result_trust_game"
    experiment_result_dir = os.path.join(base_result_dir, f"result_{experiment_time}")
    os.makedirs(experiment_result_dir, exist_ok=True)
    logging.info(f"Experiment results will be saved to: {experiment_result_dir}")

    # ------- Set game parameters -------
    NUM_GAMES = 5
    NUM_ROUNDS = 10
    NUM_PAIRS = 4  # Number of Trustor-Trustee pairs
    INITIAL_FUNDS = 10
    MULTIPLICATION_FACTOR = 3

    # Record experiment configuration
    experiment_config = {
        "experiment_type": "v2_framework_trust_game",
        "experiment_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "num_games": NUM_GAMES,
        "num_rounds_per_game": NUM_ROUNDS,
        "num_pairs": NUM_PAIRS,
        "initial_funds": INITIAL_FUNDS,
        "multiplication_factor": MULTIPLICATION_FACTOR,
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
    all_game_investments = []  # List of dicts per game: [{"Trustor_1": X, ...}, ...]
    all_game_returns = []  # List of dicts per game: [{"Trustee_1": Y, ...}, ...]
    all_game_return_rates = []  # List of dicts per game: [{"Trustee_1": rate, ...}, ...]
    per_game_payoffs = []  # List of dicts, e.g., [{"Trustor_1": X, "Trustee_1": Y, ...}, ...]

    # ------- Game loop -------
    for game_num in range(1, NUM_GAMES + 1):
        print(f"\n================ Game {game_num}/{NUM_GAMES} ================")
        logging.info(f"Starting game {game_num}/{NUM_GAMES}")

        # Create environment module
        env_module = TrustGameEnv(
            num_pairs=NUM_PAIRS,
            initial_funds=INITIAL_FUNDS,
            multiplication_factor=MULTIPLICATION_FACTOR,
        )

        # Create environment router
        env_router = CodeGenRouter(env_modules=[env_module])

        # Create agent specs (workspace-bound; role/partner live in config)
        agent_names = []
        partner_mapping = {}
        agent_specs = []

        for i in range(NUM_PAIRS):
            trustor_name = f"Trustor_{i + 1}_G{game_num}"
            trustee_name = f"Trustee_{i + 1}_G{game_num}"
            trustor_id = i * 2 + 1
            trustee_id = i * 2 + 2

            agent_specs.append(
                {
                    "id": trustor_id,
                    "profile": {"id": trustor_id, "name": trustor_name},
                    "config": {
                        "role": "Trustor",
                        "num_rounds": NUM_ROUNDS,
                        "initial_funds": INITIAL_FUNDS,
                        "multiplication_factor": MULTIPLICATION_FACTOR,
                        "partner_name": trustee_name,
                    },
                }
            )
            agent_names.append(trustor_name)

            agent_specs.append(
                {
                    "id": trustee_id,
                    "profile": {"id": trustee_id, "name": trustee_name},
                    "config": {
                        "role": "Trustee",
                        "num_rounds": NUM_ROUNDS,
                        "initial_funds": INITIAL_FUNDS,
                        "multiplication_factor": MULTIPLICATION_FACTOR,
                        "partner_name": trustor_name,
                    },
                }
            )
            agent_names.append(trustee_name)

            partner_mapping[trustor_name] = trustee_name
            partner_mapping[trustee_name] = trustor_name

        # Set partner mapping in environment
        env_module.set_partner_mapping(partner_mapping)

        # Create AgentSociety
        start_time = datetime.now()
        society = None
        try:
            society = AgentSociety(
                agent_specs=agent_specs,
                agent_class_name="TrustGameAgent",
                env_router=env_router,
                start_t=start_time,
            )
            await society.init()

            log_records = []
            game_payoffs = {name: 0 for name in agent_names}

            # Initialize investment/return/return_rate dicts for all agents
            trustor_names = [name for name in agent_names if "Trustor" in name]
            trustee_names = [name for name in agent_names if "Trustee" in name]

            game_investments = {name: 0 for name in trustor_names}
            game_returns = {name: 0 for name in trustee_names}
            game_return_rates = {
                name: (0, 0) for name in trustee_names
            }  # (total_rate, count)

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
                        trustor_investments = latest_round.get(
                            "trustor_investments", {}
                        )
                        trustee_returns = latest_round.get("trustee_returns", {})
                        payoffs = latest_round.get("payoffs", {})

                        # Update statistics
                        for name in agent_names:
                            if name in payoffs:
                                game_payoffs[name] += payoffs[name]

                        # Record investments and returns for this round
                        for trustor_name in trustor_names:
                            if trustor_name in trustor_investments:
                                game_investments[trustor_name] += trustor_investments[
                                    trustor_name
                                ]

                        for trustee_name in trustee_names:
                            if trustee_name in trustee_returns:
                                trustee_return = trustee_returns[trustee_name]
                                game_returns[trustee_name] += trustee_return

                                # Calculate return rate
                                trustor_name = partner_mapping.get(trustee_name)
                                if trustor_name and trustor_name in trustor_investments:
                                    investment = trustor_investments[trustor_name]
                                    received = investment * MULTIPLICATION_FACTOR
                                    if received > 0:
                                        return_rate = trustee_return / received
                                    else:
                                        return_rate = 0

                                    # Store as a tuple of (total_rate, count) for averaging
                                    if trustee_name not in game_return_rates:
                                        game_return_rates[trustee_name] = (0, 0)
                                    total_rate, count = game_return_rates[trustee_name]
                                    game_return_rates[trustee_name] = (
                                        total_rate + return_rate,
                                        count + 1,
                                    )

                        # Build log records
                        round_log = {
                            "round": round_num,
                            "trustor_investments": trustor_investments,
                            "trustee_returns": trustee_returns,
                            "payoffs": payoffs,
                            "timestamp": datetime.now().isoformat(),
                        }
                        log_records.append(round_log)

                        # Print round summary
                        print(f"Round {round_num} Summary:")
                        for trustor_name in trustor_names:
                            investment = trustor_investments.get(trustor_name, 0)
                            payoff = payoffs.get(trustor_name, 0)
                            print(
                                f"  {trustor_name}: Invested {investment}, Payoff {payoff:.2f}"
                            )

                        for trustee_name in trustee_names:
                            return_amount = trustee_returns.get(trustee_name, 0)
                            payoff = payoffs.get(trustee_name, 0)
                            # Get current round's return rate (tuple format)
                            rate_tuple = game_return_rates.get(trustee_name, (0, 0))
                            if isinstance(rate_tuple, tuple) and rate_tuple[1] > 0:
                                return_rate = rate_tuple[0] / rate_tuple[1]
                            else:
                                return_rate = 0
                            print(
                                f"  {trustee_name}: Returned {return_amount}, Payoff {payoff:.2f}, Return Rate {return_rate:.1%}"
                            )

                        logging.info(f"Game {game_num} Round {round_num} ended")
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
                print(f"  {agent_name}: {game_payoffs[agent_name]:.2f} coins")
            total_game_payoff = sum(game_payoffs.values())
            print(f"Total payoff for all agents: {total_game_payoff:.2f} coins")

            # Convert game_return_rates from tuples back to average rates
            final_return_rates = {}
            for trustee_name, (total_rate, count) in game_return_rates.items():
                if count > 0:
                    final_return_rates[trustee_name] = total_rate / count
                else:
                    final_return_rates[trustee_name] = 0

            # Save this game's data
            per_game_payoffs.append(game_payoffs.copy())
            all_game_investments.append(game_investments.copy())
            all_game_returns.append(game_returns.copy())
            all_game_return_rates.append(final_return_rates)

        finally:
            # Clean up
            if society:
                await society.close()

    # ------- End of all games -------
    # Save overall results
    overall_results = {
        "experiment_settings": experiment_config,
        "per_game_payoffs": per_game_payoffs,
        "all_game_investments": all_game_investments,
        "all_game_returns": all_game_returns,
        "all_game_return_rates": all_game_return_rates,
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
    print(f"Number of pairs: {NUM_PAIRS}")

    # Calculate and print statistics
    statistics = calculate_and_print_statistics(
        per_game_payoffs,
        all_game_investments,
        all_game_returns,
        all_game_return_rates,
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
