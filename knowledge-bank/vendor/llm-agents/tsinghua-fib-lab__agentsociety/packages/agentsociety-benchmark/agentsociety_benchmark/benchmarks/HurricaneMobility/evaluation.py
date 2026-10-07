import json
import numpy as np
from typing import Any, Dict
    

async def evaluation(to_evaluate: Any, datasets_path: str, metadata: Dict):
    if metadata['mode'] == 'test':
        raise NotImplementedError("Test mode is not supported for HurricaneMobility")
    
    # load ground truth
    with open(f"{datasets_path}/groundtruth/hurricane_groundtruth.json", "r") as f:
        groundtruth = json.load(f)

    # Ground truth change rate
    real_mid_pre = groundtruth["relative_changes"]["during_vs_before"]
    real_post_pre = groundtruth["relative_changes"]["after_vs_before"]
    # Ground truth hourly travel
    real_hourly_trips_pre = groundtruth["hourly_trips"]["before"]
    real_hourly_trips_mid = groundtruth["hourly_trips"]["during"]
    real_hourly_trips_post = groundtruth["hourly_trips"]["after"]

    # Generated data
    gen_pre = to_evaluate["total_travel_times"][0]
    gen_mid = to_evaluate["total_travel_times"][1]
    gen_post = to_evaluate["total_travel_times"][2]
    gen_mid_pre = (gen_mid-gen_pre)/gen_pre*100
    gen_post_pre = (gen_post-gen_pre)/gen_pre*100
    gen_hourly_trips_pre = to_evaluate["hourly_travel_times"][0]
    gen_hourly_trips_mid = to_evaluate["hourly_travel_times"][1]
    gen_hourly_trips_post = to_evaluate["hourly_travel_times"][2]

    # Calculate change rate similarity score (0-100)
    """
    Calculates the similarity score for change rates between real and generated data.
    - **Description**:
        - Compares the relative changes in travel times during and after hurricane vs before.
        - Uses mean absolute percentage error (MAPE) to measure accuracy.
        - Converts MAPE to a 0-100 score where 100 is perfect match.

    - **Args**:
        - `real_mid_pre` (float): Real change rate during vs before hurricane.
        - `real_post_pre` (float): Real change rate after vs before hurricane.
        - `gen_mid_pre` (float): Generated change rate during vs before hurricane.
        - `gen_post_pre` (float): Generated change rate after vs before hurricane.

    - **Returns**:
        - `change_rate_score` (float): Score between 0-100 for change rate accuracy.
    """
    def calculate_change_rate_score(real_mid_pre, real_post_pre, gen_mid_pre, gen_post_pre):
        # Calculate mean absolute percentage error
        mape_mid = abs(real_mid_pre - gen_mid_pre) / (abs(real_mid_pre) + 1e-8) * 100
        mape_post = abs(real_post_pre - gen_post_pre) / (abs(real_post_pre) + 1e-8) * 100
        avg_mape = (mape_mid + mape_post) / 2
        
        # Convert MAPE to score (0-100), where 0% error = 100 points
        change_rate_score = max(0, 100 - avg_mape)
        return change_rate_score

    # Calculate hourly distribution similarity score (0-100)
    """
    Calculates the similarity score for hourly travel distribution patterns.
    - **Description**:
        - Compares the hourly travel patterns across three time periods.
        - Uses cosine similarity to measure distribution pattern similarity.
        - Normalizes distributions before comparison to focus on patterns rather than absolute values.

    - **Args**:
        - `real_hourly_trips_pre` (list): Real hourly trips before hurricane.
        - `real_hourly_trips_mid` (list): Real hourly trips during hurricane.
        - `real_hourly_trips_post` (list): Real hourly trips after hurricane.
        - `gen_hourly_trips_pre` (list): Generated hourly trips before hurricane.
        - `gen_hourly_trips_mid` (list): Generated hourly trips during hurricane.
        - `gen_hourly_trips_post` (list): Generated hourly trips after hurricane.

    - **Returns**:
        - `distribution_score` (float): Score between 0-100 for distribution similarity.
    """
    def calculate_distribution_score(real_hourly_trips_pre, real_hourly_trips_mid, real_hourly_trips_post,
                                   gen_hourly_trips_pre, gen_hourly_trips_mid, gen_hourly_trips_post):
        def cosine_similarity(a, b):
            # Normalize vectors to focus on pattern rather than magnitude
            a_norm = np.array(a) / (np.linalg.norm(a) + 1e-8)
            b_norm = np.array(b) / (np.linalg.norm(b) + 1e-8)
            return np.dot(a_norm, b_norm)
        
        # Calculate cosine similarity for each time period
        sim_pre = cosine_similarity(real_hourly_trips_pre, gen_hourly_trips_pre)
        sim_mid = cosine_similarity(real_hourly_trips_mid, gen_hourly_trips_mid)
        sim_post = cosine_similarity(real_hourly_trips_post, gen_hourly_trips_post)
        
        # Average similarity across all periods
        avg_similarity = (sim_pre + sim_mid + sim_post) / 3
        
        # Convert to 0-100 score
        distribution_score = max(0, avg_similarity * 100)
        return distribution_score

    # Calculate individual scores
    change_rate_score = calculate_change_rate_score(real_mid_pre, real_post_pre, gen_mid_pre, gen_post_pre)
    distribution_score = calculate_distribution_score(real_hourly_trips_pre, real_hourly_trips_mid, real_hourly_trips_post,
                                                    gen_hourly_trips_pre, gen_hourly_trips_mid, gen_hourly_trips_post)
    
    # Calculate final weighted score (0-100)
    """
    Calculates the final weighted score combining change rate and distribution accuracy.
    - **Description**:
        - Combines change rate score (60% weight) and distribution score (40% weight).
        - Change rate is weighted higher as it directly measures hurricane impact accuracy.
        - Distribution pattern is important but secondary to overall change magnitude.

    - **Args**:
        - `change_rate_score` (float): Score for change rate accuracy (0-100).
        - `distribution_score` (float): Score for distribution pattern similarity (0-100).

    - **Returns**:
        - `final_score` (float): Final weighted score between 0-100.
    """
    final_score = change_rate_score * 0.6 + distribution_score * 0.4

    return {
        "total_travel_times": to_evaluate["total_travel_times"],
        "hourly_travel_times": to_evaluate["hourly_travel_times"],
        "change_rate_score": change_rate_score,
        "distribution_score": distribution_score,
        "final_score": final_score,
        "detailed_metrics": {
            "real_change_rates": {"during_vs_before": real_mid_pre, "after_vs_before": real_post_pre},
            "generated_change_rates": {"during_vs_before": gen_mid_pre, "after_vs_before": gen_post_pre},
            "change_rate_error": {
                "during_vs_before": abs(real_mid_pre - gen_mid_pre),
                "after_vs_before": abs(real_post_pre - gen_post_pre)
            }
        }
    }