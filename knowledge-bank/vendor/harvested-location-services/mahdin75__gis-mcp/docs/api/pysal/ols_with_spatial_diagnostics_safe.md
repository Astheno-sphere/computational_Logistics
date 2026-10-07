### ols_with_spatial_diagnostics_safe

Run OLS regression with spatial diagnostics, ensuring data safety checks.

- Tool: `ols_with_spatial_diagnostics_safe`

Parameters

- data_path (string): Path to shapefile or GeoPackage.
- y_field (string): Dependent variable column name.
- x_fields (list of strings): Independent variable column names.
- weights_path (string, optional): Path to weights file (.gal or .gwt).
- weights_method (string, default "queen"): 'queen', 'rook', 'distance_band', or 'knn'.
- id_field (string, optional): Attribute name for IDs.
- threshold (float, required if method="distance_band"): Distance threshold.
- k (integer, required if method="knn"): Number of neighbors.
- binary (bool, default True): Binary option (DistanceBand only).

Returns

- n_obs (integer): Number of observations.
- r2 (float): R-squared value.
- std_error (list): Standard errors for coefficients.
- betas (dict): Estimated coefficients.
- moran_residual (float): Moran’s I of residuals (if available).
- moran_pvalue (float): P-value of Moran’s I test (if available).
- status, message
