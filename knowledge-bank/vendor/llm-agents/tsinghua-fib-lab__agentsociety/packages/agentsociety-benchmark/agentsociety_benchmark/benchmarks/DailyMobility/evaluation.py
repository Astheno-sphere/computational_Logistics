import numpy as np
from typing import Any, Dict
from scipy.spatial.distance import jensenshannon

def calculate_jsd_1d(data1, data2, bins=50):
    """
    Calculate JSD between two 1D arrays (e.g., gyration radius, location numbers)
    
    Args:
        data1 (np.array): First 1D array
        data2 (np.array): Second 1D array  
        bins (int): Number of bins for histogram calculation
        
    Returns:
        float: JSD value between the two distributions
    """
    # Create histograms
    hist1, bin_edges = np.histogram(data1, bins=bins, density=True)
    hist2, _ = np.histogram(data2, bins=bins, density=True)
    
    # Add small epsilon to avoid zero probabilities
    epsilon = 1e-10
    hist1 = hist1 + epsilon
    hist2 = hist2 + epsilon
    
    # Normalize to sum to 1
    hist1 = hist1 / np.sum(hist1)
    hist2 = hist2 / np.sum(hist2)
    
    # Calculate JSD using scipy
    jsd = jensenshannon(hist1, hist2)
    
    return jsd

def calculate_jsd_2d(data1, data2):
    """
    Calculate JSD between two 2D arrays (e.g., intention sequences, intention proportions)
    Each row represents an agent's data
    
    Args:
        data1 (np.array): First 2D array, shape (n_agents, n_features)
        data2 (np.array): Second 2D array, shape (n_agents, n_features)
        
    Returns:
        float: JSD value between the two distributions
    """
    # Flatten the 2D arrays to 1D for distribution comparison
    flat_data1 = data1.flatten()
    flat_data2 = data2.flatten()
    
    # Calculate JSD using the 1D function
    jsd = calculate_jsd_1d(flat_data1, flat_data2)
    
    return jsd

async def evaluation(to_evaluate: Any, datasets_path: str, metadata: Dict):
    if metadata['mode'] == 'test':
        raise NotImplementedError("Test mode is not supported for DailyMobility")
    
    # read ground truth
    real_gyration_radius = np.load(f"{datasets_path}/groundtruth/gyration_radius.npy")
    real_daily_location_numbers = np.load(f"{datasets_path}/groundtruth/daily_location_numbers.npy")
    real_intention_sequences = np.load(f"{datasets_path}/groundtruth/daily_intentions_2d.npy")
    real_intention_proportions = np.load(f"{datasets_path}/groundtruth/intention_proportions_2d.npy")

    # generated results
    gen_gyration_radius = np.array(to_evaluate["gyration_radius"])
    gen_daily_location_numbers = np.array(to_evaluate["daily_location_numbers"])
    gen_intention_sequences = np.array(to_evaluate["intention_sequences"])
    gen_intention_proportions = np.array(to_evaluate["intention_proportions"])

    # calculate metrics - JSD divergence
    jsd_gyration = calculate_jsd_1d(real_gyration_radius, gen_gyration_radius)
    jsd_locations = calculate_jsd_1d(real_daily_location_numbers, gen_daily_location_numbers)
    jsd_sequences = calculate_jsd_2d(real_intention_sequences, gen_intention_sequences)
    jsd_proportions = calculate_jsd_2d(real_intention_proportions, gen_intention_proportions)

    # calculate final score
    final_score = ((1-jsd_gyration + 1-jsd_locations + 1-jsd_sequences + 1-jsd_proportions) / 4) * 100
    
    # Return evaluation results
    results = {
        "jsd_gyration_radius": jsd_gyration,
        "jsd_daily_location_numbers": jsd_locations,
        "jsd_intention_sequences": jsd_sequences,
        "jsd_intention_proportions": jsd_proportions,
        "final_score": final_score
    }
    
    return results
    
    