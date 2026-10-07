'use strict';

// Write-flow testing — exercises real CRUD chains (create → read → update →
// delete) to catch write-path and logic bugs a read-only smoke probe can't.
//
// SAFETY: this MUTATES data. It is OFF unless `config.writeFlows.enabled === true`,
// every flow is explicitly defined (nothing is auto-discovered or auto-mutated),
// and every created resource is cleaned up (DELETE) at the end of its flow —
// even on failure. Intended for a disposable / test-tenant environment only.

function is2xx(status) {
  return typeof status === 'number' && status >= 200 && status < 300;
}

function extractId(body, field) {
  if (body == null || typeof body !== 'object') return null;
  if (body[field] != null && typeof body[field] !== 'object') return body[field];
  for (const wrapper of ['data', 'result', 'item']) {
    const w = body[wrapper];
    if (w && typeof w === 'object' && w[field] != null && typeof w[field] !== 'object') return w[field];
  }
  return null;
}

function mk(flow, step, detail) {
  return { flow: flow.name || flow.create && flow.create.path || 'flow', step, detail };
}

/**
 * Run a single CRUD flow. Always attempts cleanup (DELETE) for anything it
 * created, even if an earlier step failed. Returns { ok, findings, cleanedUp }.
 */
async function runOneFlow(flow, request) {
  const findings = [];
  let createdId = null;
  const fillId = (p) => String(p).replace(/\{[^}]+\}/g, () => encodeURIComponent(String(createdId)));

  try {
    if (!flow.create || !flow.create.path) {
      findings.push(mk(flow, 'config', 'flow has no create step'));
    } else {
      const c = await request({ method: flow.create.method || 'POST', path: flow.create.path, body: flow.create.body });
      if (!is2xx(c.status)) {
        findings.push(mk(flow, 'create', `expected 2xx, got ${c.status}`));
      } else {
        createdId = extractId(c.body, flow.idField || 'id');
        if (createdId == null) {
          findings.push(mk(flow, 'create', `created resource id (field "${flow.idField || 'id'}") not found in response`));
        } else {
          if (flow.read && flow.read.path) {
            const r = await request({ method: 'GET', path: fillId(flow.read.path) });
            if (!is2xx(r.status)) findings.push(mk(flow, 'read', `created resource not readable (got ${r.status})`));
          }
          if (flow.update && flow.update.path) {
            const u = await request({ method: flow.update.method || 'PATCH', path: fillId(flow.update.path), body: flow.update.body });
            if (!is2xx(u.status)) findings.push(mk(flow, 'update', `update failed (got ${u.status})`));
          }
        }
      }
    }
  } catch (err) {
    findings.push(mk(flow, 'error', err.message));
  }

  // CLEANUP — always, best-effort.
  let cleanedUp = false;
  if (createdId != null && flow.delete && flow.delete.path) {
    try {
      const d = await request({ method: 'DELETE', path: fillId(flow.delete.path) });
      cleanedUp = is2xx(d.status) || d.status === 404;
      if (!cleanedUp) {
        findings.push(mk(flow, 'cleanup', `cleanup DELETE returned ${d.status} — resource may be orphaned`));
      } else if (flow.read && flow.read.path) {
        const g = await request({ method: 'GET', path: fillId(flow.read.path) });
        if (is2xx(g.status)) findings.push(mk(flow, 'delete', 'resource still readable after delete'));
      }
    } catch (err) {
      findings.push(mk(flow, 'cleanup', `cleanup failed: ${err.message}`));
    }
  }

  return { ok: findings.length === 0, findings, createdId, cleanedUp };
}

/**
 * Run all configured write-flows. `request` is ({method,path,body}) => {status,body}.
 */
async function runWriteFlows(config, request) {
  const wf = (config && config.writeFlows) || {};
  const summary = { enabled: !!wf.enabled, ran: 0, passed: 0, failed: 0, cleanedUp: 0, findings: [], flows: [] };
  if (!wf.enabled || !Array.isArray(wf.flows) || wf.flows.length === 0) return summary;

  for (const flow of wf.flows) {
    const res = await runOneFlow(flow, request);
    summary.ran++;
    if (res.ok) summary.passed++; else summary.failed++;
    if (res.cleanedUp) summary.cleanedUp++;
    summary.findings.push(...res.findings);
    summary.flows.push({ name: flow.name || (flow.create && flow.create.path), ok: res.ok, cleanedUp: res.cleanedUp });
  }
  return summary;
}

module.exports = { runWriteFlows, runOneFlow, extractId, is2xx };
