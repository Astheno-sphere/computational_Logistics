# SQL business semantics v3

This is an original, executable SQLite decision corpus inspired by the **use-case category** of [dbt-assay](https://github.com/ryan-sunny/dbt-assay/tree/ebf8812c9aeb19747f7168a0e08d3d224e170b12): distinguishing a runnable query from one that computes the intended business metric. No repository examples, test cases, SQL gold, JevBench items, or other benchmark questions were read or copied by the generator. There are no paid API calls or model-generated labels. Original authored data are CC0-1.0.

## Frozen data

| Quantity | Count |
| --- | ---: |
| Decision rows | 12,288 |
| Train | 6,144 |
| Calibration / validation / test / OOD | 1,536 each |
| Complete visible databases | 6,144 |
| Database pairs differing only in requested metric | 6,144 |
| Business-semantic operators | 12 |
| Operator × schema/layout families | 96 |
| Distinct SQL template sets after removing literals | 48 |
| Rows with 3 / 4 SQL candidates | 1,024 / 11,264 |
| Rows with one / two answer-equivalent correct candidates | 10,247 / 2,041 |

The second row in each pair uses the same tables and exactly the same candidate order, but changes the explicit requested metric. The requested answer and the positive candidate set must change. These are request counterfactuals, not cell mutations or independently collected databases. Actual table cardinality, customer repetition, amounts, NULL/zero patterns, quantities, dates, refund status, tag multiplicity, rate denominators, and snapshot ties vary. An independent fingerprint that removes arbitrary IDs, row order and absolute date origin still finds **6,144 distinct databases**, with none crossing splits.

The task is **Choice**. Model input is restricted to `state`, `question`, `kind`, and `options`. State includes complete table schema, all visible rows, business request, parameters, and the result contract. Options are 3–4 finite SQL statements. Reference answers, SQL execution results, provenance and labels occur only in `target` / `metadata`; they are never appended to the input. The largest full input is under 4,300 characters at this configuration; token-length and GPU-memory preflight remain responsibilities of the training runner.

## What the operators test

| Operator | Business distinction |
| --- | --- |
| Extended amounts | Unit price × quantity versus unweighted listed prices |
| Distinct customers | Distinct non-NULL customers versus event rows |
| NULL averages | Ignore missing values versus treat them as zero |
| Time window | Inclusive start / exclusive end versus inclusive endpoints |
| Unit conversion | Mixed dollars and cents converted into a requested unit |
| Refund netting | Gross versus settled-refund net totals; preserve sales cardinality |
| Join multiplicity | Once per qualifying event versus once per matching tag record |
| Anti join with NULL | Customers without / with events; `NOT IN` NULL trap |
| Weighted rates | Global successes / trials versus mean of per-event rates |
| Group thresholds | Aggregate customer total versus individual-event threshold |
| Snapshot selection | Latest / earliest snapshot, with explicit same-day tie breaking |
| Left join and zeros | Include customers with no events versus observed customers only |

Queries include aggregates, `DISTINCT`, `EXISTS`, anti joins, grouped subqueries, `HAVING`, joins, CTEs, `COALESCE`, `NULLIF`, `CASE`, and window functions. Every candidate is executed against the complete visible in-memory database. All candidates must execute; semantic distractors must actually produce a different answer when given zero target mass. SQL NULL and numeric zero remain different. Rounded requests specify halfway cases away from zero, with an explicit halfway regression fixture.

Correctness is **answer equivalence on the visible database**. Two syntactically different SQL queries returning the requested value both receive probability `1 / number_of_correct_candidates`. This deliberately avoids marking a coincidentally equivalent query wrong. It does not assert query equivalence on unseen databases. The all-candidates-correct case is rejected. The task is not free-form text-to-SQL generation.

## Splits and limits

Each complete operator/layout family, parent database, its paired requests, and all source-instance records occupy one split. Eight layouts combine:

- Customer IDs stored on events or normalized through a separate account relation.
- ISO date strings or integer day offsets.
- Derived-table SQL or CTE SQL.

Four combinations train; one each is calibration, validation, test and OOD. OOD is the held-out **normalized customers + integer days + CTE** combination. The component factors and the 12 semantic operators are shared with training. This measures composition within an authored grammar, not transfer to a new SQL dialect or an unrelated business domain. CTE form is a syntactic factor; 96 operator/layout families are not 96 distinct SQL AST families, data sources, or domains.

The fixtures are small, complete, controlled English warehouses. They do not establish performance on naturally collected stakeholder requests, hidden production tables, security audits, large databases, or dbt-assay. Generating this corpus does not establish any model improvement. The frozen v2 datasets are untouched.

## Reproduction and verification

```bash
python -m jev.sql_semantics_v3 --output-dir data/sql-semantics-v3
python -m unittest tests.test_sql_semantics_v3 -v
python reports/sql-semantics-v3/independent_audit.py \
  --data data/sql-semantics-v3 \
  --output reports/sql-semantics-v3/independent-replay-audit.json
```

Choose a new or empty output directory. The default seed is `20260921`, with 64 databases per operator/layout family. Generation is standard-library-only, deterministic, and reads no input files.

The ten tests include hand-calculated fixtures for all twelve operators, a separate SQLite loading path, exact rounding behavior, uniform labels for equivalent candidates, syntax/write/multiple-statement rejection, metadata independence, target/data tampering, split grouping, and reproducibility. The independent audit imports neither the generator nor its oracle: it separately interprets the visible request, reconstructs SQLite, and checks all **48,128 candidate executions**. The frozen run has zero SQL errors and zero label disagreements. Reports retain full denominators and data-file checksums:

- [Manifest](../reports/sql-semantics-v3/manifest.json)
- [Generation audit](../reports/sql-semantics-v3/generation-audit.json)
- [Independent replay audit](../reports/sql-semantics-v3/independent-replay-audit.json)

Train SHA-256: `ec763cfc84c6f80f428fc2a5eed9bd365c8b48a30beb71fa47712d45802cdd4d`.
