### spatial_markov

Run Spatial Markov analysis on panel data (n regions x t periods) from a shapefile. This function uses giddy.Spatial_Markov to analyze spatial-temporal dynamics and transition probabilities.

- Tool: `spatial_markov`

Parameters

- shapefile_path (string) - Path to shapefile with panel data
- value_columns (string or list) - Time-ordered column names (oldest to newest), at least 2 required
- target_crs (string, default "EPSG:4326") - Target coordinate reference system
- weights_method (string, default "queen") - 'queen', 'rook', or 'distance'
- distance_threshold (number, default 100000) - Distance threshold in meters (converted to degrees if EPSG:4326)
- k (integer, default 5) - Number of classes for y (quantile bins if continuous)
- m (integer, default 5) - Number of classes for spatial lags
- fixed (boolean, default True) - Use pooled quantiles across all periods
- permutations (integer, default 0) - Number of permutations for randomization p-values (>0 to enable)
- relative (boolean, default True) - Divide each period by its mean
- drop_na (boolean, default True) - Drop features with any NA across time columns
- fill_empty_classes (boolean, default True) - Handle empty bins by making them self-absorbing

Returns

- n_regions, n_periods, k_classes_y, m_classes_lag, weights_method, value_columns
- discretization: cutoffs_y, cutoffs_lag, fixed
- global_transition_prob_p: (k x k) transition probability matrix
- conditional_transition_prob_P: (m x k x k) conditional transition probabilities
- global_steady_state_s: (k,) steady state distribution
- conditional_steady_states_S: (m x k) conditional steady states
- tests: chi2_total_x2, chi2_df, chi2_pvalue, Q, Q_p_value, LR, LR_p_value
- data_preview[], status, message

Example

```json
{
  "tool": "spatial_markov",
  "params": {
    "shapefile_path": "data/regions_panel.shp",
    "value_columns": ["GDP_2010", "GDP_2015", "GDP_2020"],
    "target_crs": "EPSG:3857",
    "weights_method": "queen",
    "k": 5,
    "m": 5,
    "permutations": 99
  }
}
```
