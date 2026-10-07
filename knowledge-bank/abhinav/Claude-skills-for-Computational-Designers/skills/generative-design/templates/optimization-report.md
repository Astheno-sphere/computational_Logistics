# Generative Design Optimization Report

## Template for Documenting AEC Generative Design Results

---

## 1. Project Information

| Field | Value |
|---|---|
| **Project Name** | [Project name] |
| **Project Phase** | [Concept / Schematic / Design Development] |
| **Building Type** | [Office / Residential / Educational / Healthcare / Mixed-Use / Infrastructure] |
| **Location** | [City, Country — Climate Zone] |
| **Gross Floor Area** | [m2] |
| **Report Date** | [YYYY-MM-DD] |
| **Prepared By** | [Name, Role] |
| **Optimization Tool** | [Galapagos / Wallacei / Octopus / Opossum / Refinery / Custom] |
| **Platform** | [Grasshopper + Rhino / Dynamo + Revit / Custom Python] |
| **Computation Time** | [Total hours / days] |
| **Hardware** | [CPU model, cores, RAM] |

---

## 2. Problem Definition

### 2.1 Design Context

[Describe the design problem in 2-4 paragraphs. Include:
- What is being optimized (floor plan, facade, structure, massing, etc.)
- Why generative design was chosen over manual exploration
- What design stage this optimization informs
- Key constraints from the brief, site, regulations, or client requirements]

### 2.2 Baseline Design

[Describe the reference design against which optimized solutions will be compared. Include key performance values of the baseline.]

| Metric | Baseline Value | Unit |
|---|---|---|
| [Metric 1] | [Value] | [Unit] |
| [Metric 2] | [Value] | [Unit] |
| [Metric 3] | [Value] | [Unit] |

### 2.3 Optimization Goals

[State what success looks like. What improvements over baseline are expected? What trade-offs are acceptable?]

---

## 3. Variable Summary

### 3.1 Design Variables

| # | Variable Name | Description | Type | Min | Max | Step | Unit |
|---|---|---|---|---|---|---|---|
| V1 | [name] | [description] | Continuous / Discrete / Categorical | [min] | [max] | [step or N/A] | [unit] |
| V2 | [name] | [description] | | | | | |
| V3 | [name] | [description] | | | | | |
| V4 | [name] | [description] | | | | | |
| V5 | [name] | [description] | | | | | |
| ... | ... | ... | | | | | |

**Total variables**: [N]
**Design space size**: [Estimated number of possible solutions or volume of continuous space]

### 3.2 Fixed Parameters

[List parameters that were considered for optimization but fixed to reduce dimensionality, with justification.]

| Parameter | Fixed Value | Justification |
|---|---|---|
| [Parameter 1] | [Value] | [Why fixed — e.g., client requirement, code mandate, sensitivity analysis showed low impact] |
| [Parameter 2] | [Value] | [Justification] |

### 3.3 Variable Interaction Notes

[Document known or expected interactions between variables. Which variables are likely coupled? Which are independent? This information affects encoding and crossover operator selection.]

---

## 4. Objective Summary

### 4.1 Optimization Objectives

| # | Objective Name | Description | Direction | Evaluation Method | Simulation Tool | Time per Eval | Weight (if weighted sum) |
|---|---|---|---|---|---|---|---|
| O1 | [name] | [description] | MIN / MAX | [method] | [tool] | [seconds] | [weight or N/A] |
| O2 | [name] | [description] | | | | | |
| O3 | [name] | [description] | | | | | |
| ... | ... | ... | | | | | |

**Total objectives**: [N]
**Optimization type**: [Single-objective / Bi-objective / Multi-objective / Many-objective]

### 4.2 Fitness Function Formulations

[For each objective, provide the exact formula or computation method used. Include normalization approach.]

**Objective 1: [Name]**
```
[Exact formula or pseudocode for computing this fitness value]
Normalization: [Method — min-max / z-score / target-based / none]
Bounds: [min_expected, max_expected]
```

**Objective 2: [Name]**
```
[Exact formula or pseudocode]
Normalization: [Method]
Bounds: [min_expected, max_expected]
```

[Repeat for all objectives]

### 4.3 Constraints

| # | Constraint | Type | Limit | Handling Method | Penalty Coefficient (if applicable) |
|---|---|---|---|---|---|
| C1 | [description] | Inequality / Equality | [limit value] | Penalty / Repair / Decoder / Deb's rules | [value or N/A] |
| C2 | [description] | | | | |
| C3 | [description] | | | | |

---

## 5. Solver Configuration

### 5.1 Algorithm Settings

| Parameter | Value | Justification |
|---|---|---|
| **Algorithm** | [GA / NSGA-II / SPEA2 / HypE / MOEA/D / RBFOpt / SA / CMA-ES] | [Why this algorithm] |
| **Population size** | [N] | [Based on variable count, evaluation cost, desired diversity] |
| **Number of generations** | [N] | [Based on convergence tests or computational budget] |
| **Total evaluations** | [pop_size * generations] | |
| **Crossover type** | [SBX / Uniform / BLX-alpha / other] | |
| **Crossover rate** | [0.0-1.0] | |
| **Crossover distribution index (eta_c)** | [value, if applicable] | |
| **Mutation type** | [Polynomial / Gaussian / Uniform / other] | |
| **Mutation rate** | [value — e.g., 1/n_vars] | |
| **Mutation distribution index (eta_m)** | [value, if applicable] | |
| **Selection method** | [Tournament / Roulette / Rank / other] | |
| **Tournament size** | [k, if tournament] | |
| **Elitism** | [Yes/No — number of elite individuals] | |
| **Random seed** | [seed value or "multiple runs"] | |
| **Number of independent runs** | [N] | [For robustness assessment] |

### 5.2 Computational Setup

| Parameter | Value |
|---|---|
| **Parallelization** | [None / N cores / GPU / Cloud] |
| **Evaluation per individual** | [time in seconds] |
| **Estimated total runtime** | [hours] |
| **Actual total runtime** | [hours] |
| **Surrogate model used** | [Yes — type / No] |
| **Multi-fidelity scheme** | [Yes — describe / No] |

### 5.3 Stopping Criteria

[Which criteria were used and what values triggered termination.]

| Criterion | Threshold | Triggered? |
|---|---|---|
| Generation limit | [N] | [Yes/No] |
| Fitness plateau (epsilon over N gens) | [epsilon, N] | [Yes/No] |
| Hypervolume plateau | [threshold] | [Yes/No] |
| Diversity threshold | [value] | [Yes/No] |
| Computational budget | [max evaluations] | [Yes/No] |

---

## 6. Convergence Analysis

### 6.1 Convergence Plots Description

[Describe the convergence behavior observed. Reference plots if attached.]

**Best fitness curve**: [Describe trend — rapid initial improvement? Plateau? Oscillation? At which generation did improvement slow significantly?]

**Average fitness curve**: [Describe trend — how does the gap between best and average evolve? Does average fitness track best fitness closely (good) or lag (selection pressure may be insufficient)?]

**Hypervolume curve** (multi-objective): [Describe trend — is the Pareto front improving? At which generation did hypervolume stabilize?]

**Diversity metrics**: [Describe population diversity over generations — gradual decrease (healthy) or rapid collapse (premature convergence)?]

### 6.2 Convergence Assessment

| Question | Answer |
|---|---|
| Did the optimization converge? | [Yes / Partially / No] |
| Estimated generation of convergence | [N] |
| Were sufficient generations run? | [Yes / No — should have run more] |
| Was premature convergence observed? | [Yes — at gen N / No] |
| Were multiple runs consistent? | [Yes — similar Pareto fronts / No — significant variation] |

### 6.3 Issues Encountered

[Document any issues during optimization: model crashes, infeasible populations, unexpected behavior, parameter adjustments made mid-run.]

---

## 7. Pareto Front Analysis

*[This section applies to multi-objective optimization. For single-objective, skip to Section 8.]*

### 7.1 Pareto Front Overview

| Metric | Value |
|---|---|
| **Total non-dominated solutions** | [N] |
| **Pareto front hypervolume** | [value] (reference point: [ref]) |
| **Objective ranges on Pareto front** | O1: [min-max], O2: [min-max], ... |
| **Number of clusters identified** | [N] |
| **Clustering method** | [K-means / Agglomerative / DBSCAN] |

### 7.2 Pareto Front Characterization

[Describe the shape and distribution of the Pareto front:]
- Is it convex, concave, or mixed?
- Is it continuous or disconnected?
- Are solutions evenly distributed or clustered?
- Where are the "knee" points (maximum curvature)?

### 7.3 Trade-Off Analysis

[For each pair of conflicting objectives, describe the trade-off relationship:]

**O1 vs. O2**: [Describe — e.g., "Increasing daylight autonomy from 45% to 65% requires accepting a 15% increase in cooling energy. Beyond 65% DA, the cooling penalty accelerates sharply, suggesting 60-65% DA is the optimal trade-off range."]

**O1 vs. O3**: [Describe trade-off]

**O2 vs. O3**: [Describe trade-off]

### 7.4 Cluster Descriptions

| Cluster | N Solutions | Characteristic | O1 Range | O2 Range | O3 Range | Design Strategy |
|---|---|---|---|---|---|---|
| A | [N] | [brief label] | [range] | [range] | [range] | [What design strategy defines this cluster] |
| B | [N] | [brief label] | [range] | [range] | [range] | [Design strategy] |
| C | [N] | [brief label] | [range] | [range] | [range] | [Design strategy] |

---

## 8. Selected Solutions

### 8.1 Solution Selection Criteria

[Describe how solutions were selected from the Pareto front. What method was used — knee point, aspiration-based, TOPSIS, designer preference, client input?]

### 8.2 Selected Solution 1: [Name/Label]

**Selection rationale**: [Why this solution was chosen — e.g., "Best balance between daylight and cost at the knee point of the Pareto front."]

| Metric | Value | vs. Baseline | Improvement |
|---|---|---|---|
| O1: [name] | [value] | [baseline value] | [+/- %] |
| O2: [name] | [value] | [baseline value] | [+/- %] |
| O3: [name] | [value] | [baseline value] | [+/- %] |

**Key variable values**:

| Variable | Value | Unit |
|---|---|---|
| V1 | [value] | [unit] |
| V2 | [value] | [unit] |
| ... | ... | ... |

**Constraint satisfaction**: [All constraints satisfied? Any near-boundary values?]

**Design description**: [2-3 sentences describing the physical design this solution represents. What does it look like? What is its defining characteristic?]

**Strengths**: [What this solution does well]

**Weaknesses**: [What this solution sacrifices or where it is merely adequate]

### 8.3 Selected Solution 2: [Name/Label]

[Same structure as Solution 1]

### 8.4 Selected Solution 3: [Name/Label]

[Same structure as Solution 1]

### 8.5 Solution Comparison Matrix

| Metric | Baseline | Solution 1 | Solution 2 | Solution 3 | Best Possible |
|---|---|---|---|---|---|
| O1: [name] | [val] | [val] | [val] | [val] | [val on Pareto front] |
| O2: [name] | [val] | [val] | [val] | [val] | [val on Pareto front] |
| O3: [name] | [val] | [val] | [val] | [val] | [val on Pareto front] |
| [qualitative] | [assessment] | [assessment] | [assessment] | [assessment] | N/A |

---

## 9. Sensitivity Analysis Summary

### 9.1 Variable Sensitivity Rankings

[Results from Morris method, Sobol indices, or other sensitivity analysis performed before or during optimization.]

| Rank | Variable | First-Order Sensitivity (S1) | Total Sensitivity (ST) | Most Affected Objective |
|---|---|---|---|---|
| 1 | [most influential variable] | [value] | [value] | [objective] |
| 2 | [second most influential] | [value] | [value] | [objective] |
| 3 | [third] | [value] | [value] | [objective] |
| ... | ... | ... | ... | ... |
| N | [least influential] | [value] | [value] | [objective] |

### 9.2 Key Variable Interactions

[Document significant variable interactions identified through sensitivity analysis or optimization results.]

| Interaction | Effect | Implication |
|---|---|---|
| V1 x V2 | [description of interaction effect] | [What this means for design decisions] |
| V3 x V5 | [description] | [Implication] |

### 9.3 Insensitive Variables

[List variables that showed negligible influence on all objectives. These could be fixed in future optimizations to reduce dimensionality.]

| Variable | Max Sensitivity | Recommendation |
|---|---|---|
| [variable] | [S_T value] | Fix at [value] — negligible impact |
| [variable] | [S_T value] | Fix at [value] — negligible impact |

---

## 10. Recommendations

### 10.1 Recommended Design Direction

[Based on the optimization results, recommend which solution or design strategy to pursue. Justify with evidence from the Pareto front, trade-off analysis, and constraint satisfaction.]

### 10.2 Refinement Opportunities

[Identify aspects of the recommended solution that could be improved through:]
- Local optimization around the selected solution
- Manual design refinement (aesthetics, detailing, user experience)
- Additional analysis not captured by the fitness function
- Stakeholder review and feedback integration

### 10.3 Limitations and Caveats

[Acknowledge limitations of this optimization:]

| Limitation | Impact | Mitigation |
|---|---|---|
| [e.g., Simplified energy model used] | [Fitness values may differ from detailed simulation by +/- X%] | [Validate selected solutions with full EnergyPlus model] |
| [e.g., Aesthetic quality not captured] | [Optimized solutions may require aesthetic refinement] | [Human review and selection applied post-optimization] |
| [e.g., Construction phasing not considered] | [Optimal layout may not align with phased construction] | [Review with construction manager before finalizing] |

### 10.4 Next Steps

[Concrete actions to take following this optimization:]

1. [Action 1 — e.g., "Present top 3 solutions to client for preference selection"]
2. [Action 2 — e.g., "Validate selected solution with detailed energy simulation"]
3. [Action 3 — e.g., "Develop selected solution to schematic design level"]
4. [Action 4 — e.g., "Re-run optimization with updated constraints from structural engineer"]
5. [Action 5 — e.g., "Document optimization parameters for future reference and reuse"]

---

## 11. Appendices

### Appendix A: Parametric Model Description

[Describe the parametric model architecture:]
- Software and plugins used (Grasshopper components, Python libraries, simulation engines)
- Model complexity (component count, computation graph depth)
- Known model limitations or instabilities
- Model file location and version

### Appendix B: Raw Data Summary

| Dataset | Location | Format | Records |
|---|---|---|---|
| All evaluated solutions | [file path] | [CSV / JSON / SQLite] | [N records] |
| Pareto front solutions | [file path] | [format] | [N records] |
| Convergence history | [file path] | [format] | [N generations] |
| Variable sensitivity data | [file path] | [format] | [N variables] |

### Appendix C: Convergence Plots

[Reference or embed convergence plots:]
- Best / average / worst fitness per generation (per objective)
- Hypervolume per generation
- Population diversity per generation
- Pareto front evolution (overlay of fronts at generations 10, 25, 50, final)

### Appendix D: Pareto Front Visualizations

[Reference or embed:]
- 2D Pareto front scatter plots (one per objective pair)
- Parallel coordinate plot of Pareto front solutions
- Cluster visualization with color-coded solutions
- Phenotype (geometry) renderings of selected solutions

### Appendix E: Validation Results

[If selected solutions were validated with independent tools or higher-fidelity models:]

| Solution | Fitness Function Value | Validation Value | Difference | Within Tolerance? |
|---|---|---|---|---|
| Solution 1 — O1 | [value] | [value] | [%] | [Yes/No] |
| Solution 1 — O2 | [value] | [value] | [%] | [Yes/No] |
| Solution 2 — O1 | [value] | [value] | [%] | [Yes/No] |
| ... | ... | ... | ... | ... |

---

*Report generated using the Generative Design Optimization Report Template v1.0*
*Computational Design Skills Plugin for AEC*
