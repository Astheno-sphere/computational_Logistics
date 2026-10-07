### dynamic_lisa

Run dynamic LISA (directional LISA) analysis using giddy.directional.Rose. This function analyzes directional changes in spatial patterns between two time periods.

- Tool: `dynamic_lisa`

Parameters

- shapefile_path (string) - Path to shapefile with panel data
- value_columns (string or list) - Exactly two columns: [start_time, end_time]
- target_crs (string, default "EPSG:4326") - Target coordinate reference system
- weights_method (string, default "queen") - 'queen', 'rook', or 'distance'
- distance_threshold (number, default 100000) - Distance threshold in meters (converted to degrees if EPSG:4326)
- k (integer, default 8) - Number of rose sectors
- permutations (integer, default 99) - Number of permutations for inference (0 to skip)
- alternative (string, default "two.sided") - 'two.sided', 'positive', or 'negative'
- relative (boolean, default True) - Divide each column by its mean
- drop_na (boolean, default True) - Drop features with NA in either column

Returns

- n_regions, k_sectors, weights_method, value_columns
- cuts_radians: Sector edges in radians
- sector_counts: Count per sector
- angles_theta_rad: Angles for each region (one per region)
- vector_lengths_r: Vector lengths for each region (one per region)
- bins_used: Bins used in analysis
- inference: permutations, alternative, p_values_by_sector, expected_counts_perm, larger_or_equal_counts, smaller_or_equal_counts
- data_preview[], status, message

Example

```json
{
  "tool": "dynamic_lisa",
  "params": {
    "shapefile_path": "data/regions.shp",
    "value_columns": ["GDP_2010", "GDP_2020"],
    "target_crs": "EPSG:3857",
    "weights_method": "queen",
    "k": 8,
    "permutations": 99,
    "alternative": "two.sided"
  }
}
```
