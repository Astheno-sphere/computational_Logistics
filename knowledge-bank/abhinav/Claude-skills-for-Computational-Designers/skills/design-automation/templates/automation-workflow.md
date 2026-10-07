# Design Automation Workflow Documentation Template

Use this template to document any design automation workflow in AEC. Complete all sections before deploying the workflow in production. This template ensures consistent, auditable, and maintainable automation documentation across all projects and teams.

---

## Workflow Identification

| Field | Value |
|-------|-------|
| **Workflow Name** | [Descriptive name, e.g., "Automated Egress Compliance Check"] |
| **Workflow ID** | [Unique identifier, e.g., DA-EGR-001] |
| **Version** | [Semantic version, e.g., 1.2.0] |
| **Author** | [Name and role] |
| **Date Created** | [YYYY-MM-DD] |
| **Date Last Modified** | [YYYY-MM-DD] |
| **Status** | [Draft / In Review / Approved / Deployed / Deprecated] |
| **Classification** | [Design / Analysis / Documentation / Compliance / Fabrication / Coordination] |
| **Automation Level** | [Parametric / Rule-Based / Constraint-Based / Generative / AI-Assisted] |

---

## Purpose and Scope

### Objective
[Describe what this workflow accomplishes in 2-3 sentences. What design task does it automate? What manual process does it replace or augment?]

### Scope Boundaries
- **In scope**: [List what the workflow handles]
- **Out of scope**: [List what it explicitly does not handle, to prevent misuse]
- **Building types**: [Which building types does this apply to?]
- **Project phases**: [Which project phases? Concept / Schematic / DD / CD / CA]
- **Jurisdictions**: [Which code jurisdictions are supported?]

### Business Justification
| Metric | Manual Process | Automated Workflow | Improvement |
|--------|---------------|-------------------|-------------|
| Time | [e.g., 8 hours] | [e.g., 15 minutes] | [e.g., 32x faster] |
| Error rate | [e.g., 5-10% checking errors] | [e.g., <0.1%] | [e.g., 50-100x fewer errors] |
| Consistency | [e.g., Varies by person] | [e.g., 100% consistent] | [Standardized] |
| Cost | [e.g., $X per occurrence] | [e.g., $Y per occurrence] | [e.g., Z% savings] |

---

## Input Data Requirements

### Required Inputs

| # | Input Name | Format | Source | Description | Validation Rules |
|---|-----------|--------|--------|-------------|-----------------|
| 1 | [e.g., Building Model] | [e.g., Revit .rvt, IFC] | [e.g., Design team BIM model] | [Description] | [e.g., Must contain rooms with areas, must have levels defined] |
| 2 | [e.g., Room Program] | [e.g., Excel .xlsx] | [e.g., Client brief] | [Description] | [e.g., Columns: Room Name, Area Min, Area Max, Occupancy Type] |
| 3 | [e.g., Site Boundary] | [e.g., DWG, shapefile] | [e.g., Survey] | [Description] | [e.g., Closed polyline, georeferenced] |

### Optional Inputs

| # | Input Name | Format | Default Value | Description |
|---|-----------|--------|---------------|-------------|
| 1 | [e.g., Custom rule overrides] | [e.g., JSON] | [e.g., Standard IBC rules] | [Description] |
| 2 | [e.g., Material library] | [e.g., CSV] | [e.g., Built-in defaults] | [Description] |

### Input Validation Checklist

- [ ] All required inputs are present and accessible
- [ ] File formats are correct and files open without errors
- [ ] Model contains required elements (rooms, walls, levels, etc.)
- [ ] Data ranges are within expected bounds
- [ ] Coordinate systems are consistent across inputs
- [ ] Units are verified (metric/imperial) and consistent
- [ ] Model is up-to-date (check last modified date)
- [ ] Input data has been reviewed by a qualified team member

---

## Processing Steps

### Step 1: [Step Name, e.g., "Data Extraction"]

| Field | Value |
|-------|-------|
| **Tool/Script** | [e.g., Python script: `extract_rooms.py`] |
| **Environment** | [e.g., Python 3.11, Revit 2024 API, Grasshopper] |
| **Duration** | [e.g., ~30 seconds for typical project] |
| **Dependencies** | [e.g., Requires Revit to be open with model loaded] |

**Description**: [2-3 sentences describing what this step does]

**Input**: [What this step receives from previous step or from initial inputs]

**Process**:
1. [Sub-step 1: detailed action]
2. [Sub-step 2: detailed action]
3. [Sub-step 3: detailed action]

**Output**: [What this step produces]

**Error Handling**: [What happens if this step fails? How to recover?]

---

### Step 2: [Step Name, e.g., "Rule Application"]

| Field | Value |
|-------|-------|
| **Tool/Script** | [e.g., Rule engine: `compliance_checker.py`] |
| **Environment** | [e.g., Python 3.11, custom rule engine] |
| **Duration** | [e.g., ~2 minutes] |
| **Dependencies** | [e.g., Rule library v2.1, Step 1 output] |

**Description**: [2-3 sentences]

**Input**: [From Step 1]

**Process**:
1. [Sub-step 1]
2. [Sub-step 2]
3. [Sub-step 3]

**Output**: [Data/files produced]

**Error Handling**: [Failure modes and recovery]

---

### Step 3: [Step Name, e.g., "Result Generation"]

[Repeat the same structure for each step. Typical workflows have 4-8 steps.]

---

### Step N: [Final Step Name]

[Continue as needed]

---

## Decision Points and Branching Logic

### Decision Point 1: [Name, e.g., "Building Height Classification"]

```
IF building_height > 23m:
    → Execute high-rise pathway (Steps X, Y, Z)
    → Apply high-rise rule set
ELSE IF building_height > 12m:
    → Execute mid-rise pathway (Steps X, Y)
    → Apply mid-rise rule set
ELSE:
    → Execute low-rise pathway (Step X)
    → Apply low-rise rule set
```

**Rationale**: [Why this decision point exists. Reference to code section or design logic.]

### Decision Point 2: [Name, e.g., "Compliance Result Action"]

```
IF all_checks_pass:
    → Generate compliance certificate
    → Proceed to next design phase
ELSE IF critical_failures > 0:
    → HALT workflow
    → Generate failure report with specific violations
    → Notify designer for manual intervention
ELSE IF warnings_only:
    → Generate advisory report
    → Allow designer to proceed with acknowledgment
```

### Decision Point 3: [Name]

[Add as many decision points as needed. Document every conditional branch in the workflow.]

---

## Output Deliverables

### Primary Outputs

| # | Output Name | Format | Description | Recipient |
|---|-----------|--------|-------------|-----------|
| 1 | [e.g., Compliance Report] | [e.g., PDF] | [e.g., Detailed pass/fail report for all code checks] | [e.g., Project architect, code consultant] |
| 2 | [e.g., Updated Model] | [e.g., Revit .rvt] | [e.g., Model with compliance parameters populated] | [e.g., BIM coordinator] |
| 3 | [e.g., Data Export] | [e.g., CSV, JSON] | [e.g., Structured compliance data for dashboards] | [e.g., Project manager] |

### Secondary Outputs

| # | Output Name | Format | Description |
|---|-----------|--------|-------------|
| 1 | [e.g., Process Log] | [e.g., .log file] | [e.g., Detailed execution log for debugging] |
| 2 | [e.g., Visualization] | [e.g., PNG/SVG] | [e.g., Color-coded floor plan showing compliance status] |

### Output Validation Checklist

- [ ] All expected output files are generated
- [ ] Output files open correctly and are not corrupted
- [ ] Numerical results are within expected ranges
- [ ] Visualizations are legible and correctly scaled
- [ ] Report content matches the model data
- [ ] No placeholder or default values remain in output
- [ ] Output file naming follows project conventions
- [ ] Output files are saved to the correct project directory

---

## Validation and QA Steps

### Automated Validation

| # | Validation Check | Method | Pass Criteria | Action on Fail |
|---|-----------------|--------|---------------|----------------|
| 1 | [e.g., Input completeness] | [e.g., Script checks all required fields present] | [e.g., All required fields non-null] | [e.g., Abort with error listing missing fields] |
| 2 | [e.g., Result range check] | [e.g., Assert values within bounds] | [e.g., 0 < occupant_load < 10000] | [e.g., Flag anomalous values for review] |
| 3 | [e.g., Cross-check totals] | [e.g., Sum of parts equals total] | [e.g., Sum of room areas = gross floor area ± 2%] | [e.g., Warning with discrepancy amount] |

### Manual QA Steps

| # | QA Step | Responsible | Frequency | Documentation |
|---|--------|-------------|-----------|---------------|
| 1 | [e.g., Spot-check 5 rooms against manual calculation] | [e.g., Senior architect] | [e.g., Every first run on new project] | [e.g., QA checklist form] |
| 2 | [e.g., Review report for completeness and clarity] | [e.g., Project manager] | [e.g., Every run] | [e.g., Approval signature] |
| 3 | [e.g., Compare results with previous version] | [e.g., BIM coordinator] | [e.g., When model changes significantly] | [e.g., Comparison log] |

### Regression Testing

When the workflow is updated, run these regression tests:

| # | Test Case | Input | Expected Output | Last Validated |
|---|----------|-------|-----------------|----------------|
| 1 | [e.g., Standard office building] | [e.g., test_office.rvt] | [e.g., All 47 checks pass] | [YYYY-MM-DD] |
| 2 | [e.g., Building with known violations] | [e.g., test_violations.rvt] | [e.g., 3 specific violations detected] | [YYYY-MM-DD] |
| 3 | [e.g., Edge case: single-story] | [e.g., test_single.rvt] | [e.g., Elevator check skipped, 32 checks pass] | [YYYY-MM-DD] |
| 4 | [e.g., Edge case: mixed occupancy] | [e.g., test_mixed.rvt] | [e.g., Separation checks triggered] | [YYYY-MM-DD] |
| 5 | [e.g., Empty/minimal model] | [e.g., test_empty.rvt] | [e.g., Graceful failure with clear error message] | [YYYY-MM-DD] |

---

## Error Handling Procedures

### Error Classification

| Severity | Definition | User Impact | Response |
|----------|-----------|-------------|----------|
| **Critical** | Workflow cannot continue; data integrity at risk | Results may be invalid | Abort immediately; alert user; log error |
| **Major** | Step failed but workflow can continue with reduced output | Partial results only | Skip failed step; warn user; continue |
| **Minor** | Unexpected condition but result is still valid | No impact on results | Log warning; continue normally |
| **Info** | Informational message about processing | None | Log for debugging |

### Common Error Scenarios

| # | Error | Cause | Detection | Recovery |
|---|-------|-------|-----------|----------|
| 1 | [e.g., Model file locked] | [e.g., Another user has model open] | [e.g., File access exception] | [e.g., Retry after 30s; notify user to close model] |
| 2 | [e.g., Missing room data] | [e.g., Rooms not properly bounded in model] | [e.g., Room area = 0 or null] | [e.g., Skip room; list in error report; warn user] |
| 3 | [e.g., Rule conflict] | [e.g., Contradictory local amendments] | [e.g., Two rules fire with contradictory actions] | [e.g., Apply higher-priority rule; log conflict] |
| 4 | [e.g., Memory exceeded] | [e.g., Very large model] | [e.g., MemoryError exception] | [e.g., Process in batches by level] |
| 5 | [e.g., Network timeout] | [e.g., Cloud service unavailable] | [e.g., HTTP timeout] | [e.g., Retry 3x with exponential backoff; use cached data] |

### Error Logging

All errors are logged with the following information:
```
[TIMESTAMP] [SEVERITY] [STEP] [ERROR_CODE]
  Message: [Human-readable description]
  Context: [Input values and state at time of error]
  Stack: [Call stack for debugging]
  Recovery: [Action taken]
```

Log file location: `[project_dir]/logs/[workflow_id]_[timestamp].log`

---

## Performance Benchmarks

### Execution Time Benchmarks

| Scenario | Model Size | Steps | Execution Time | Hardware |
|----------|-----------|-------|----------------|----------|
| Small project | [e.g., 50 rooms, 2 floors] | [e.g., All 6 steps] | [e.g., 45 seconds] | [e.g., i7-12700, 32GB RAM] |
| Medium project | [e.g., 200 rooms, 10 floors] | [e.g., All 6 steps] | [e.g., 3 minutes] | [e.g., same] |
| Large project | [e.g., 1000 rooms, 40 floors] | [e.g., All 6 steps] | [e.g., 12 minutes] | [e.g., same] |
| Very large project | [e.g., 5000+ rooms, campus] | [e.g., All 6 steps] | [e.g., 45 minutes] | [e.g., same] |

### Performance Optimization Notes

- [e.g., Step 3 (spatial analysis) is the bottleneck; accounts for 70% of total time]
- [e.g., Parallel processing available for Step 4 (reduces time by 60% on 8-core CPU)]
- [e.g., Caching enabled for Step 2 (rule compilation); saves 15 seconds on subsequent runs]
- [e.g., Memory usage peaks at Step 5; ensure 16GB+ RAM for large projects]

### Scalability Limits

| Resource | Limit | Consequence | Mitigation |
|----------|-------|-------------|------------|
| [e.g., Max rooms] | [e.g., 10,000] | [e.g., Memory exceeded] | [e.g., Process by floor] |
| [e.g., Max floors] | [e.g., 100] | [e.g., Stacking time exponential] | [e.g., Group into zones] |
| [e.g., Max rules] | [e.g., 5,000] | [e.g., Slow pattern matching] | [e.g., Rule indexing] |

---

## Maintenance Notes

### Dependency Management

| Dependency | Version | Update Frequency | Impact of Update |
|-----------|---------|-----------------|------------------|
| [e.g., Python] | [e.g., 3.11.x] | [e.g., Annual] | [e.g., Test all scripts] |
| [e.g., Revit API] | [e.g., 2024] | [e.g., Annual] | [e.g., API changes may break extraction] |
| [e.g., IBC rule set] | [e.g., 2021] | [e.g., Every 3 years] | [e.g., Update all egress rules] |
| [e.g., numpy] | [e.g., 1.25.x] | [e.g., Quarterly] | [e.g., Minor; pin major version] |

### Update Triggers

This workflow must be reviewed and potentially updated when:

- [ ] Building code edition changes (IBC cycle: every 3 years)
- [ ] Local code amendments are adopted
- [ ] BIM software version is upgraded (Revit annual release)
- [ ] Python or library dependencies have breaking changes
- [ ] A bug is discovered in production
- [ ] Performance degrades beyond acceptable benchmarks
- [ ] New building types are added to scope
- [ ] Client or project requirements change

### Change Log

| Version | Date | Author | Changes | Reviewed By |
|---------|------|--------|---------|-------------|
| 1.0.0 | [YYYY-MM-DD] | [Name] | Initial release | [Name] |
| 1.1.0 | [YYYY-MM-DD] | [Name] | [e.g., Added hospital rule set] | [Name] |
| 1.1.1 | [YYYY-MM-DD] | [Name] | [e.g., Fixed exit width calculation for sprinklered buildings] | [Name] |
| 1.2.0 | [YYYY-MM-DD] | [Name] | [e.g., Added parallel processing for large models] | [Name] |

### Knowledge Transfer

For onboarding new team members to this workflow:

1. **Prerequisites**: [List required knowledge/skills]
2. **Training materials**: [Link to training documents, videos, or tutorials]
3. **Sandbox environment**: [Where to practice without affecting production]
4. **Key contacts**: [Who to ask for help]
5. **Common pitfalls**: [What new users typically get wrong]

---

## Appendices

### Appendix A: Workflow Diagram

[Insert or link to a visual flowchart of the workflow. Tools: draw.io, Miro, Lucidchart, or even ASCII art for version control.]

```
START
  │
  ▼
[1. Data Extraction] ──── Inputs: Model, Program
  │
  ▼
[2. Validation] ──── Pass? ──── No ──→ ERROR REPORT → END
  │ Yes
  ▼
[3. Processing] ──── Decision Point: Building Type
  │                    │              │
  │                    ▼              ▼
  │               [3a. Office]  [3b. Residential]
  │                    │              │
  │                    └──────┬───────┘
  ▼                           │
[4. Analysis]                 │
  │◄──────────────────────────┘
  ▼
[5. Report Generation]
  │
  ▼
[6. Output & Archive]
  │
  ▼
END
```

### Appendix B: Configuration Parameters

[List all configurable parameters with default values and acceptable ranges]

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| [e.g., grid_module_mm] | [e.g., 300] | [e.g., 100-1200] | [e.g., Planning grid module in millimeters] |
| [e.g., max_travel_distance_m] | [e.g., 60] | [e.g., 23-90] | [e.g., Maximum travel distance, code-dependent] |
| [e.g., output_format] | [e.g., "pdf"] | [e.g., "pdf", "html", "json"] | [e.g., Report output format] |

### Appendix C: Related Workflows

| Workflow ID | Name | Relationship |
|-------------|------|-------------|
| [e.g., DA-STR-001] | [e.g., Structural Grid Automation] | [e.g., Upstream: provides structural grid for this workflow] |
| [e.g., DA-MEP-001] | [e.g., MEP Routing Automation] | [e.g., Downstream: uses layout from this workflow] |
| [e.g., DA-FAB-001] | [e.g., Fabrication Data Export] | [e.g., Downstream: consumes panel schedule from this workflow] |

### Appendix D: Glossary

| Term | Definition |
|------|-----------|
| [e.g., FAR] | [e.g., Floor Area Ratio: gross floor area divided by lot area] |
| [e.g., CSP] | [e.g., Constraint Satisfaction Problem] |
| [e.g., BSP] | [e.g., Binary Space Partitioning] |
| [e.g., EUI] | [e.g., Energy Use Intensity (kBtu/ft2/yr or kWh/m2/yr)] |

---

*Template version: 1.0.0 | Last updated: 2026-03-23*
*For questions about this template, contact the computational design team.*
