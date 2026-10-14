# Mixed logit on the public Swissmetro dataset

**What this is.** A reproducible mixed-logit (random-coefficients logit) estimation on the public
Swissmetro stated-preference dataset. It shows that a discrete-choice estimation pipeline runs end to end
on **real** choice data, not synthetic data.

**What this is not.** It is not a claim of prior estimation expertise and not new research. The
specification is the standard textbook one (it follows Bierlaire's Biogeme example `b05normal_mixture`).
It was prepared with AI assistance as part of PhD proposal preparation, and it is intended to be run and
understood by the applicant, Arshad Akhtar Abbasia.

## Reproduce

```bash
cd evidence/dcm-swissmetro
pip install -r requirements.txt        # biogeme==3.3.5 (Python 3.13.16 used)
python estimate_swissmetro.py          # ~1 min on a laptop; writes the result files below
python plot_results.py                 # writes time_coefficient_distribution.png
```

Halton draws are deterministic, so the seed has no effect and reruns give the same numbers.
Tested with Biogeme **3.3.5**, numpy 2.5.3, pandas 2.3.3, scipy 1.18.1, matplotlib 3.11.2.

## Data source and licence

`swissmetro.dat` is copied unmodified from the Biogeme repository
(github.com/michelbierlaire/biogeme, file `src/biogeme/data/data/swissmetro.dat`, commit
`8d1063b5c371f09f5dd44f430b3be66455f2b785`, identical to `tests/swissmetro/swissmetro.dat`).
The repository is MIT licensed (copy in `LICENSE_biogeme_MIT.txt`, (c) 2026 Michel Bierlaire). The survey
is described in Bierlaire, Axhausen and Abay (2001), "The acceptance of modal innovation: the case of
Swissmetro", Swiss Transport Research Conference. 10,728 rows; the repository's licence file does not
single out the data file separately, so cite the survey paper when using it.

## Specification (all explained line by line in the script)

- Alternatives: Train, Swissmetro (SM), Car. Availability flags respected (train and car treated as
  available only in the stated-preference rows, as in the standard example).
- Sample: drop `CHOICE == 0` (10,728 to 10,719 rows), keep trip purposes commuter and business
  (to **6,768** observations; the usual teaching sample).
- Utility = alternative-specific constant + B_TIME x time/100 + B_COST x cost/100. Season-ticket (GA)
  holders have train and SM cost set to 0.
- B_TIME is **random**: Normal(B_TIME, B_TIME_S^2) across travellers. B_COST is fixed.
  ASC_SM is the fixed reference (0).
- Simulation: 1,000 Halton draws per observation. Robust (sandwich) standard errors.

## Headline results (Biogeme 3.3.5, N = 6,768, 1,000 Halton draws)

| Statistic | Value |
|---|---|
| Final log-likelihood | -5214.88 |
| Null log-likelihood (equal shares over available modes) | -6964.66 |
| Rho-squared / **rho-bar-squared** (vs null) | 0.2512 / **0.2505** |
| Free parameters / AIC / BIC | 5 / 10439.75 / 10473.85 |

| Parameter | Estimate | Robust s.e. | Robust t |
|---|---|---|---|
| ASC_TRAIN | -0.4015 | 0.0658 | -6.10 |
| ASC_CAR | 0.1371 | 0.0517 | 2.65 |
| B_TIME (mean) | -2.2593 | 0.1169 | -19.33 |
| B_TIME_S (std. dev.) | -1.6570 | 0.1313 | -12.62 |
| B_COST | -1.2852 | 0.0863 | -14.89 |

(The sign of B_TIME_S is arbitrary for a normal draw; only its magnitude, 1.66, matters.)

As a reproduction check, Biogeme's own saved reference run for this specification
(`docs/source/examples/swissmetro/saved_results/b05normal_mixture_*.yaml`, 10,000 pseudo-random draws)
gives final LL -5215.69, B_TIME -2.257, B_TIME_S 1.654, B_COST -1.285, ASC_TRAIN -0.403, ASC_CAR 0.136,
which agrees with the table above to within simulation noise. Stability: rerunning with 3,000
draws moved every estimate by less than 0.001 and the log-likelihood by 0.009 (checked once, not saved
here). Biogeme prints a generic warning that 1,000 draws is "low"; the check above shows it is adequate
for this model.

Figure: `time_coefficient_distribution.png` (estimated distribution of the time coefficient).

## Plain-language reading

Travellers dislike longer trips and higher costs, and both effects are very precisely estimated (|t| above
14). The valuation of travel time varies a lot between people: the standard deviation (1.66) is about
three quarters of the mean (2.26), so some travellers are far more time-sensitive than others. Because a
normal distribution is assumed, about 8.6% of travellers are implied to have a positive time coefficient
(they would like longer trips), which is behaviourally implausible and is a known weakness of a normal
shape; a lognormal or bounded distribution is the usual remedy and was deliberately not done here.
Controlling for time and cost, travellers lean slightly towards car and away from train relative to
Swissmetro. A rho-bar-squared of 0.25 means the model explains a moderate share of choice behaviour,
typical for stated-preference mode choice with few attributes.

## Limitations and caveats

- Each respondent answered several choice scenarios, but this standard specification treats rows as
  independent (no panel structure). Standard errors may therefore be somewhat too small. Biogeme's panel
  mixture example (`b26`-style, one draw per respondent) is the next step.
- Only one random coefficient and no socio-economic covariates. The ratio B_TIME/B_COST implies a mean
  value of time near 105 CHF/hour, which is high; I did not investigate why, and it should not be quoted
  as a value-of-time estimate.
- Re-estimation on a different Biogeme version may differ in the later decimals.

## Files

`estimate_swissmetro.py` (model), `plot_results.py` (figure), `swissmetro.dat` (data),
`requirements.txt`, `run_log.txt` (console output), `estimated_parameters.csv`, `results_summary.json`,
`swissmetro_mixed_logit.html` and `.yaml` (Biogeme's own output), `time_coefficient_distribution.png`,
`LICENSE_biogeme_MIT.txt`.
