### gm_lag

Run GM_Lag (spatial 2SLS / GMM-IV spatial lag model) on a cross-section. This function estimates spatial lag models using instrumental variables and generalized method of moments.

- Tool: `gm_lag`

Parameters

- shapefile_path (string) - Path to shapefile with cross-sectional data
- y_col (string) - Dependent variable column name
- x_cols (string or list) - Exogenous regressor column names (no constant)
- target_crs (string, default "EPSG:4326") - Target coordinate reference system
- weights_method (string, default "queen") - 'queen', 'rook', or 'distance'
- distance_threshold (number, default 100000) - Distance threshold in meters (auto-converted to degrees for EPSG:4326)
- w_lags (integer, default 1) - Number of spatial lags for instruments (WX, WWX, ...)
- lag_q (boolean, default True) - Also lag external instruments q
- yend_cols (string or list, optional) - Other endogenous regressors
- q_cols (string or list, optional) - External instruments for yend_cols
- robust (string, optional) - None, 'white', or 'hac' for robust standard errors
- hac_bandwidth (number, optional) - Bandwidth for HAC (only used if robust='hac')
- spat_diag (boolean, default True) - Include AK test for spatial diagnostics
- sig2n_k (boolean, default False) - Use n-k for variance if True
- drop_na (boolean, default True) - Drop rows with NA in y/x/yend/q

Returns

- n_obs, k_vars, dependent, exog, endog, instruments, weights_method
- spec: w_lags, lag_q, robust, sig2n_k
- betas: Coefficient estimates
- beta_names: Names of coefficients (const, x_cols, yend_cols, W_y)
- std_err: Standard errors
- z_stats: Z-statistics with p-values
- pseudo_r2: Pseudo R-squared
- pseudo_r2_reduced: Reduced form pseudo R-squared
- sig2: Error variance
- ssr: Sum of squared residuals
- ak_test: AK test statistic and p-value (if spat_diag=True)
- pred_y_head: First 5 predicted values
- data_preview[], status, message

Example

```json
{
  "tool": "gm_lag",
  "params": {
    "shapefile_path": "data/regions.shp",
    "y_col": "GDP_GROWTH",
    "x_cols": ["EDUCATION", "INVESTMENT"],
    "target_crs": "EPSG:3857",
    "weights_method": "queen",
    "w_lags": 1,
    "robust": "white",
    "spat_diag": true
  }
}
```
