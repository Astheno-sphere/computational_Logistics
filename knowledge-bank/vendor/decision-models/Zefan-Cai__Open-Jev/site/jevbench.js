/* JevBench uses its own aggregate report; existing comparisons are unchanged. */
(() => {
  "use strict";
  const status = document.querySelector("#jevbench-status");
  const content = document.querySelector("#jevbench-content");
  const cell = (tag, text) => {
    const node = document.createElement(tag);
    node.textContent = text;
    return node;
  };
  const percent = (value) => `${(100 * value).toFixed(2)}%`;
  const new27bCheckpoint = "c49994563c3c4f04a99d9130203c4e526f4ae5086c84deec57698d18cb652e71";

  async function loadJevBench() {
    try {
      const response = await fetch("./jevbench.json");
      if (!response.ok) throw new Error("JevBench report unavailable");
      const report = await response.json();
      if (report.publication_ready !== true) {
        status.textContent = "Results are awaiting completion and independent audits for all model streams.";
        return;
      }
      const requiredStreams = report.schema_version === 2
        ? ["2b", "9b", "new27b", "jev", "luna", "astra"]
        : ["2b", "9b", "jev", "luna", "astra"];
      const fullAudit = report.full_internal_audit;
      const fullAuditPassed = report.schema_version === 1 ||
        (fullAudit?.status === "passed_complete_full24_audit" && fullAudit.publishable === true &&
         fullAudit.checkpoint_sha256 === new27bCheckpoint);
      const validTiming = (row) => row.id === "new27b"
        ? row.metrics.latency === null && row.timing_comparable === false &&
          row.execution?.mode === "frozen_base_fsdp2" && row.execution.world_size === 4 &&
          row.checkpoint?.checkpoint_sha256 === new27bCheckpoint
        : Number.isFinite(row.metrics.latency?.p50_ms) && Number.isFinite(row.metrics.latency?.p95_ms);
      const validTiers = (row) => Object.entries({original: 72, easy: 48, hard: 111}).every(([tier, count]) => {
        const metric = row.per_public_tier?.[tier];
        return metric?.n_planned === count && Number.isInteger(metric.n_correct) &&
          metric.n_correct >= 0 && metric.n_correct <= count && metric.accuracy === metric.n_correct / count;
      });
      if (![1, 2].includes(report.schema_version) || !fullAuditPassed || report.benchmark.public_tasks !== 231 ||
          report.required_streams.length !== requiredStreams.length ||
          !requiredStreams.every((id) => report.required_streams.includes(id)) ||
          report.results.length !== requiredStreams.length ||
          new Set(report.results.map((row) => row.id)).size !== requiredStreams.length ||
          !report.results.every((row) => requiredStreams.includes(row.id) &&
            row.status === "complete" && row.audit_status === "passed" &&
            row.metrics.n_planned === 231 && row.metrics.n_attempted === 231 &&
            row.metrics.n_scorable === 231 && Number.isInteger(row.metrics.n_correct) &&
            row.metrics.n_correct >= 0 && row.metrics.n_correct <= 231 &&
            row.metrics.accuracy === row.metrics.n_correct / 231 && validTiming(row) && validTiers(row))) {
        throw new Error("JevBench publication checks incomplete");
      }
      const rows = report.results.map((result) => {
        const row = document.createElement("tr");
        const name = cell("th", {"2b": "Open-Jev-2B", "9b": "Open-Jev-9B", "new27b": "Open-Jev-27B-v1.1"}[result.id] || result.label);
        name.scope = "row";
        name.append(cell("small", result.probability_source === "native" ? "Native probabilities" : "Verbalized probabilities"));
        const metric = result.metrics;
        const hard = result.per_public_tier.hard;
        row.append(name,
          cell("td", `${metric.n_correct} / 231 · ${percent(metric.accuracy)}`),
          cell("td", `${hard.n_correct} / 111 · ${percent(hard.accuracy)}`),
          cell("td", `${metric.n_strict_valid} / 231`),
          cell("td", metric.n_renormalized),
          cell("td", result.timing_comparable === false ? "Not comparable¹" : `${metric.latency.p50_ms.toFixed(1)} ms`),
          cell("td", result.timing_comparable === false ? "Not comparable¹" : `${metric.latency.p95_ms.toFixed(1)} ms`));
        return row;
      });
      const tiers = report.results.map((result) => {
        const row = document.createElement("tr");
        const name = cell("th", {"2b": "Open-Jev-2B", "9b": "Open-Jev-9B", "new27b": "Open-Jev-27B-v1.1"}[result.id] || result.label);
        name.scope = "row";
        row.append(name, ...["original", "easy", "hard"].map((tier) => {
          const metric = result.per_public_tier[tier];
          return cell("td", `${metric.n_correct} / ${metric.n_planned}`);
        }));
        return row;
      });
      document.querySelector("#jevbench-rows").replaceChildren(...rows);
      document.querySelector("#jevbench-tier-rows").replaceChildren(...tiers);
      status.textContent = `All ${requiredStreams.length} model streams complete and independently audited · 231 public tasks per model.`;
      content.hidden = false;
    } catch {
      content.hidden = true;
      status.textContent = "JevBench results are unavailable. See the linked method and aggregate report.";
    }
  }
  loadJevBench();
})();
