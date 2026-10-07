---
name: dcm-estimate
description: Discrete choice modelling for travel behaviour. Simulate a stated-choice experiment, estimate a multinomial logit with Biogeme cross-checked by an independent maximum-likelihood estimator, report value of time, and draw parameters from the estimated covariance for uncertainty analysis. Use for mode choice, EV adoption, willingness to pay, or to feed behaviour into agent-based models.
---

# dcm-estimate

`scripts/dcm.py`: the behavioural core. Utilities per mode (car, EV, bus, bike):
`V = ASC + b_time*time + b_cost*cost (+ b_wait*wait for bus)`; value of time = 60*b_time/b_cost NOK/h.

## Use
```
python scripts/dcm.py --simulate 800 --tasks 8 --out sp.csv    # synthetic stated-choice data
python scripts/dcm.py --estimate sp.csv                        # Biogeme and independent MLE side by side
```
In Python: `estimate_biogeme(df)`, `estimate_mle(df)`, `draw_parameters(est, n)`, `utilities`, `probabilities`, `logsum`.

## Rules
- Report both estimators; they must agree (tests: to 1e-4). Disagreement means a specification or data error.
- Biogeme 3.3 API: options go in the `BIOGEME(...)` constructor; covariance is
  `get_variance_covariance_matrix(get_default_variance_covariance_matrix())` (robust when the Hessian exists).
  Biogeme writes a `biogeme.toml` into the working directory, so estimation runs in a temporary folder.
- Synthetic data recover known parameters: use them to test a specification before touching survey data.
  Real data (for Norway: the national travel survey, RVU, or a stated-choice survey) replace `simulate`.
- MNL only for now. Nested and mixed logit (taste heterogeneity) are the next step; Biogeme supports both.

## Tested (`tests/test_dcm.py`)
Parameter recovery within 3 standard errors, Biogeme vs independent MLE, value of time within 10%,
probability and logsum consistency, parameter draws matching the estimated covariance.
