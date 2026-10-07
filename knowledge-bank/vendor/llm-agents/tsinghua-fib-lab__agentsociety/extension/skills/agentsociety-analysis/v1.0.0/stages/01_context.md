# Stage 1: Load Context

Goal: understand the hypothesis, experiment design, and run status before touching the data.

## Steps

1. Run `$PYTHON_PATH .agentsociety/bin/ags.py analysis load-context --workspace $WORKSPACE --hypothesis-id $HYP_ID --experiment-id $EXP_ID`.
2. Summarize the hypothesis, experiment design, runtime status, duration, and notable errors in natural language.
3. Ask the user whether to focus on specific tables, outcomes, exclusions, or analysis depth.
4. If the user gives no extra direction, state the default analysis direction implied by the experiment objective and success criteria.
5. Record the working paths for later stages:
   `REPLAY_DIR=.../run/replay`,
   `RUN_DIR=.../run`,
   `OUTPUT_DIR=.../presentation/hypothesis_{id}`,
   `CHARTS_DIR=$OUTPUT_DIR/charts`.

## Exit Conditions

- The analysis direction is confirmed by the user, or no extra constraints were provided and the default direction is stated.
- The working path variables are explicit before moving to Stage 2.
