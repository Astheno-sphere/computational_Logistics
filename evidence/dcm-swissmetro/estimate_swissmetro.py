"""
Mixed logit (random-coefficients logit) on the public Swissmetro dataset.

PURPOSE
    Show that a discrete-choice estimation pipeline runs end to end on REAL
    stated-preference choice data. This is the standard textbook specification
    (it follows Bierlaire's Biogeme example "b05normal_mixture"); it is
    deliberately plain, not novel.

HOW TO RUN (from this folder)
    python estimate_swissmetro.py

WHAT THE MODEL SAYS IN ONE LINE
    A traveller chooses between TRAIN, SWISSMETRO (SM, a proposed maglev) and
    CAR. Each alternative has a "utility" that falls with travel time and cost.
    The value people put on travel time is allowed to DIFFER across travellers
    (normal distribution), instead of being forced to one number for everybody.

Prepared with AI assistance; intended to be run and understood by the
applicant. It is not a claim of prior estimation expertise.
"""

import importlib.metadata
import json
from pathlib import Path

import pandas as pd

import biogeme
import biogeme.biogeme as bio
import biogeme.database as db
from biogeme import models
from biogeme.expressions import Beta, Draws, MonteCarlo, Variable, log
from biogeme.parameters import Parameters

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Settings you may want to change.
# ---------------------------------------------------------------------------
NUMBER_OF_DRAWS = 1000   # simulation draws per person-observation (more = less simulation noise)
SEED = 1                 # fixes the random numbers so results are reproducible
MODEL_NAME = "swissmetro_mixed_logit"

# ---------------------------------------------------------------------------
# 1. LOAD THE DATA
#    swissmetro.dat is tab-separated. Each row is ONE stated-preference
#    choice made by a respondent among the alternatives they were shown.
# ---------------------------------------------------------------------------
df = pd.read_csv(HERE / "swissmetro.dat", sep="\t")
n_raw = len(df)
database = db.Database("swissmetro", df)

# Name the columns we use, so we can write formulas with them.
CHOICE = Variable("CHOICE")      # 1 = Train, 2 = Swissmetro, 3 = Car, 0 = unknown
PURPOSE = Variable("PURPOSE")    # trip purpose: 1 = commuter, 3 = business, ...
GA = Variable("GA")              # 1 = holds a season ticket ("GA") for the whole rail network
SP = Variable("SP")              # 1 = stated-preference survey, 0 = revealed preference
TRAIN_AV = Variable("TRAIN_AV")  # availability flags (1 = the mode could be chosen)
SM_AV = Variable("SM_AV")
CAR_AV = Variable("CAR_AV")
TRAIN_TT = Variable("TRAIN_TT")  # travel time, minutes
SM_TT = Variable("SM_TT")
CAR_TT = Variable("CAR_TT")
TRAIN_CO = Variable("TRAIN_CO")  # travel cost, Swiss francs
SM_CO = Variable("SM_CO")
CAR_CO = Variable("CAR_CO")

# ---------------------------------------------------------------------------
# 2. EXCLUDE UNUSABLE / OUT-OF-SCOPE RECORDS (the usual textbook filters)
#    - CHOICE == 0: the respondent's choice is missing, so the record cannot
#      inform a choice model.
#    - Keep only PURPOSE 1 (commuter) and 3 (business): the standard sample
#      used in the Biogeme teaching examples, so the model describes a
#      reasonably homogeneous group and results can be compared with the
#      published ones.
# ---------------------------------------------------------------------------
database.remove(CHOICE == 0)
n_after_choice = database.num_rows()
database.remove(((PURPOSE != 1) * (PURPOSE != 3)) > 0)
n_obs = database.num_rows()
print(f"Rows in file: {n_raw}; after dropping CHOICE==0: {n_after_choice}; "
      f"after keeping commuter+business trips: {n_obs}")

# ---------------------------------------------------------------------------
# 3. PREPARE ATTRIBUTES
#    - A GA season-ticket holder pays nothing extra per trip by train, so their
#      train cost is set to 0 (and likewise the SM cost, as SM is assumed to be
#      covered by the same pass).
#    - Divide time and cost by 100 so the coefficients are of a sensible size
#      (e.g. 1.2 instead of 0.012). This helps the optimiser converge and does
#      not change the model. Units: time in hundreds of minutes, cost in
#      hundreds of CHF.
#    - Train and car are only treated as available in the SP survey (SP != 0),
#      following the standard example.
# ---------------------------------------------------------------------------
TRAIN_COST = TRAIN_CO * (GA == 0)
SM_COST = SM_CO * (GA == 0)

TRAIN_TT_S, SM_TT_S, CAR_TT_S = TRAIN_TT / 100, SM_TT / 100, CAR_TT / 100
TRAIN_COST_S, SM_COST_S, CAR_COST_S = TRAIN_COST / 100, SM_COST / 100, CAR_CO / 100

TRAIN_AV_SP = TRAIN_AV * (SP != 0)
CAR_AV_SP = CAR_AV * (SP != 0)

# ---------------------------------------------------------------------------
# 4. PARAMETERS TO ESTIMATE
#    Beta(name, starting value, lower bound, upper bound, fixed?)
#    fixed = 1 means "do not estimate, hold at the starting value".
# ---------------------------------------------------------------------------
# Alternative-specific constants: the average preference for each mode that is
# NOT explained by time and cost. Only differences matter, so one must be
# fixed. We fix Swissmetro's to 0 (it is the reference alternative).
ASC_TRAIN = Beta("ASC_TRAIN", 0, None, None, 0)
ASC_CAR = Beta("ASC_CAR", 0, None, None, 0)
ASC_SM = Beta("ASC_SM", 0, None, None, 1)

# Time coefficient is RANDOM across people: B_TIME_RND = B_TIME + B_TIME_S * N(0,1)
#   B_TIME   = mean of the time coefficient across the population
#   B_TIME_S = its standard deviation (the "heterogeneity" parameter)
B_TIME = Beta("B_TIME", 0, None, None, 0)
B_TIME_S = Beta("B_TIME_S", 0, None, None, 0)

# Cost coefficient is the SAME for everyone (fixed coefficient).
B_COST = Beta("B_COST", 0, None, None, 0)

# One standard-normal random draw per person-observation. Halton draws are a
# low-discrepancy sequence: they cover the space more evenly than purely
# random numbers, so fewer draws are needed for the same accuracy.
B_TIME_RND = B_TIME + B_TIME_S * Draws("B_TIME_RND", "NORMAL_HALTON2")

# ---------------------------------------------------------------------------
# 5. UTILITY FUNCTIONS (one per alternative)
#    Utility = constant + (time coefficient x time) + (cost coefficient x cost)
#    Both coefficients are expected to be NEGATIVE: more time or money, less
#    attractive. The random draw enters through the time coefficient only.
# ---------------------------------------------------------------------------
V_TRAIN = ASC_TRAIN + B_TIME_RND * TRAIN_TT_S + B_COST * TRAIN_COST_S
V_SM = ASC_SM + B_TIME_RND * SM_TT_S + B_COST * SM_COST_S
V_CAR = ASC_CAR + B_TIME_RND * CAR_TT_S + B_COST * CAR_COST_S

# Map biogeme's alternative numbers (1, 2, 3 as coded in CHOICE) to utilities
# and to availability flags (an unavailable mode gets probability zero).
V = {1: V_TRAIN, 2: V_SM, 3: V_CAR}
AV = {1: TRAIN_AV_SP, 2: SM_AV, 3: CAR_AV_SP}

# ---------------------------------------------------------------------------
# 6. CHOICE PROBABILITY AND LIKELIHOOD
#    models.logit gives the probability of the CHOSEN alternative for ONE
#    fixed value of the random coefficient. Because the coefficient is random,
#    the model probability is the AVERAGE of that logit probability over many
#    draws (Monte-Carlo integration, "MonteCarlo(...)"). The log of this is
#    the quantity we maximise, summed over all observations.
# ---------------------------------------------------------------------------
prob = models.logit(V, AV, CHOICE)
log_likelihood = log(MonteCarlo(prob))

# ---------------------------------------------------------------------------
# 7. ESTIMATE
# ---------------------------------------------------------------------------
parameters = Parameters()
parameters.set_value(name="number_of_draws", value=NUMBER_OF_DRAWS)
parameters.set_value(name="seed", value=SEED)
# With 6768 observations x 1000 draws Biogeme's default "full" analytical
# Hessian needs more memory than its budget; "chunked" computes the same
# numbers in blocks (suggested by Biogeme itself). It changes memory use only.
parameters.set_value(name="analytical_hessian_mode", value="chunked")
parameters.set_value(name="hessian_parameter_block_size", value=4)
parameters.set_value(name="hessian_observation_batch_size", value=1000)

# Run inside the output folder so Biogeme's files land next to this script.
import os
os.chdir(HERE)

model = bio.BIOGEME(
    database,
    log_likelihood,
    parameters=parameters,
    save_iterations=False,
    generate_html=True,
    generate_yaml=True,
    user_notes="Mixed logit, Swissmetro, normal random time coefficient",
)
model.model_name = MODEL_NAME
# Null model: every AVAILABLE alternative equally likely. Biogeme does not
# compute this by itself for a mixture, so we ask for it; it is the reference
# point for rho-squared.
null_ll = model.calculate_null_loglikelihood(AV)
results = model.estimate()

# ---------------------------------------------------------------------------
# 8. REPORT THE RESULTS
#    Biogeme's "robust" standard errors / t-stats use the sandwich estimator
#    and are the ones to quote (valid under mild misspecification).
#    Rho-bar-squared is a goodness-of-fit measure: 1 - (LL_final - K) / LL_0,
#    where LL_0 is the log-likelihood of a model that gives each AVAILABLE
#    alternative equal probability and K is the number of estimated
#    parameters (the "bar" penalises extra parameters). Values around 0.2-0.4
#    are typical for good discrete-choice models; it is NOT like R-squared.
# ---------------------------------------------------------------------------
from biogeme.results_processing import get_pandas_estimated_parameters

pars = get_pandas_estimated_parameters(estimation_results=results)["Estimated parameters"]
print(pars.to_string(index=False))
pars.to_csv(HERE / "estimated_parameters.csv", index=False)

# Implied share of travellers with a POSITIVE time coefficient (behaviourally
# implausible: they would like longer trips). For a normal distribution this is
# P(N(B_TIME, B_TIME_S^2) > 0).
from scipy.stats import norm
b_time = results.get_parameter_value("B_TIME")
b_time_s = results.get_parameter_value("B_TIME_S")
share_positive = float(norm.cdf(b_time / abs(b_time_s)))   # P(coef > 0)

summary = {
    "biogeme_version": importlib.metadata.version("biogeme"),
    "number_of_draws": NUMBER_OF_DRAWS,
    "draw_type": "NORMAL_HALTON2",
    "seed": SEED,
    "rows_in_file": int(n_raw),
    "rows_after_dropping_choice0": int(n_after_choice),
    "number_of_observations": int(n_obs),
    "number_of_free_parameters": int(results.number_of_free_parameters),
    "null_log_likelihood": float(null_ll),
    "final_log_likelihood": float(results.final_log_likelihood),
    "rho_square_null": float(results.rho_square_null),
    "rho_bar_square_null": float(results.rho_bar_square_null),
    "AIC": float(results.akaike_information_criterion),
    "BIC": float(results.bayesian_information_criterion),
    "share_of_population_with_positive_time_coefficient": share_positive,
    "parameters": pars.to_dict(orient="records"),
}
with open(HERE / "results_summary.json", "w") as f:
    json.dump(summary, f, indent=2, default=str)
print(json.dumps({k: v for k, v in summary.items() if k != "parameters"}, indent=2))
