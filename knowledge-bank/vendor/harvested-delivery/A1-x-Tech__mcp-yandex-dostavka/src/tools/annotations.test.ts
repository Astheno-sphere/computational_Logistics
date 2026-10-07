import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { registerExpressTools } from "./express.js";
import { registerPlatformTools } from "./platform.js";
import { registerRawTool } from "./raw.js";
import { DESTRUCTIVE, READ_ONLY, WRITE } from "./util.js";

interface Annotations {
  readOnlyHint?: boolean;
  destructiveHint?: boolean;
  idempotentHint?: boolean;
  openWorldHint?: boolean;
}

/** Registers every tool against a fake server, capturing each tool's annotations. */
function collectAnnotations(): Record<string, Annotations | undefined> {
  const annotations: Record<string, Annotations | undefined> = {};
  const server = {
    registerTool: (name: string, cfg: { annotations?: Annotations }) => {
      annotations[name] = cfg.annotations;
    },
  };
  // Registration reads the client only inside handlers, so a stub is fine here.
  registerExpressTools(server as never, {} as never);
  registerPlatformTools(server as never, {} as never);
  registerRawTool(server as never, {} as never);
  return annotations;
}

const ANN = collectAnnotations();

/**
 * Yandex Delivery is a write API, so this is a per-tool map, not a single
 * invariant: reads are READ_ONLY, state-changing calls are WRITE and
 * cancellations (plus the raw escape hatch) are DESTRUCTIVE. Adding a tool
 * means adding it here consciously.
 */
const EXPECTED: Record<string, Annotations> = {
  express_check_price: READ_ONLY,
  express_create_claim: WRITE,
  express_get_claim: READ_ONLY,
  express_accept_claim: WRITE,
  express_cancel_info: READ_ONLY,
  express_cancel_claim: DESTRUCTIVE,
  express_search_claims: READ_ONLY,
  express_performer_position: READ_ONLY,
  express_tracking_links: READ_ONLY,
  platform_list_pickup_points: READ_ONLY,
  platform_create_offers: WRITE,
  platform_confirm_offer: WRITE,
  platform_get_request: READ_ONLY,
  platform_request_history: READ_ONLY,
  platform_cancel_request: DESTRUCTIVE,
  raw_request: DESTRUCTIVE,
};

test("registers all sixteen tools with annotations", () => {
  assert.deepEqual(Object.keys(ANN).sort(), Object.keys(EXPECTED).sort());
  for (const [name, a] of Object.entries(ANN)) {
    assert.ok(a, `${name} is missing annotations`);
  }
});

test("every tool carries its expected hints, all four set explicitly", () => {
  for (const [name, expected] of Object.entries(EXPECTED)) {
    assert.deepEqual(ANN[name], expected, `${name} annotations drifted`);
  }
});

test("no read-only tool is marked destructive and vice versa", () => {
  for (const [name, a] of Object.entries(ANN)) {
    if (a?.readOnlyHint) {
      assert.equal(a.destructiveHint, false, `${name}: a read cannot be destructive`);
      assert.equal(a.idempotentHint, true, `${name}: re-reading yields the same result`);
    } else {
      assert.equal(a?.idempotentHint, false, `${name}: writes are not idempotent for the client`);
    }
    assert.equal(a?.openWorldHint, true, `${name} should set openWorldHint`);
  }
});

test("every registered tool has a public capability page with the correct impact", () => {
  const docsDir = fileURLToPath(new URL("../../docs/capabilities/", import.meta.url));
  const index = fs.readFileSync(path.join(docsDir, "index.md"), "utf8");
  const categoryLeads = new Set<string>();
  const forbiddenPublicTerms =
    /\b(Core Job|Big Job|Micro Job|Job Graph|Critical Chain of Jobs|AJTBD|NMT)\b/u;
  assert.equal(
    fs.readdirSync(docsDir).filter((name) => name.endsWith(".md")).length,
    Object.keys(EXPECTED).length + 1,
    "capability directory must contain one page per tool plus index.md",
  );

  for (const [name, annotations] of Object.entries(EXPECTED)) {
    const docPath = path.join(docsDir, name + ".md");
    assert.ok(fs.existsSync(docPath), name + ": missing docs/capabilities/" + name + ".md");

    const doc = fs.readFileSync(docPath, "utf8");
    assert.match(doc, /^# A1 · Яндекс Доставка · /u, name + ": invalid public title");
    const categoryLead =
      doc.match(/\*\*MCP-инструмент \(tool\) для Яндекс Доставки:\*\* помогает [^\n]+/u)?.[0] ?? "";
    assert.ok(categoryLead, name + ": missing MCP tool category sentence");
    assert.ok(!categoryLeads.has(categoryLead), name + ": category sentence must be unique");
    categoryLeads.add(categoryLead);
    assert.ok(doc.includes("<code>" + name + "</code>"), name + ": technical name is missing");
    assert.doesNotMatch(doc, forbiddenPublicTerms, name + ": internal methodology leaked into public copy");
    assert.match(doc, /## Какую задачу решает\n\n> Я хочу /u, name + ": user task must use «Я хочу»");

    const impact = annotations.readOnlyHint
      ? "**Воздействие:** только чтение"
      : annotations.destructiveHint
        ? "**Воздействие:** опасная операция"
        : "**Воздействие:** изменяет данные";
    assert.ok(doc.includes(impact), name + ": impact label does not match annotations");

    for (const heading of [
      "Какую задачу решает",
      "Когда использовать",
      "Что нужно передать",
      "Что вернёт",
      "Что изменится в Яндекс Доставке",
      "Пример запроса",
      "Возможные ошибки и ограничения",
      "Связанные MCP-инструменты",
      "Технические сведения",
    ]) {
      assert.ok(doc.includes("## " + heading), name + ": missing section " + heading);
    }

    assert.ok(index.includes("./" + name + ".md"), name + ": missing from capability catalog");
  }
});
