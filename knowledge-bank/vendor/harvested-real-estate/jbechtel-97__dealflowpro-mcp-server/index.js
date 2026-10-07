#!/usr/bin/env node
/**
 * DealFlowPro MCP Server (Spec 137 Phase 2)
 *
 * Exposes DealFlowPro's deal analysis engine as MCP tools for
 * Claude Code, Claude Desktop, and any MCP-compatible AI agent.
 *
 * Tools:
 *   - analyze_deal: Full multifamily deal analysis with DFP Score
 *   - score_deal: Quick deal scoring (lightweight)
 *   - reverse_calc: Back-solve max offer price from target returns
 *   - market_data: Flood zone, neighborhood income, job growth
 *
 * Configuration:
 *   DFP_API_KEY (required) — Your DealFlowPro API key
 *   DFP_API_URL (optional) — API base URL (defaults to https://dealflowpro.io)
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const MCP_VERSION = "1.2.7";
const USER_AGENT = `dealflowpro-mcp/${MCP_VERSION}`;

const API_KEY = process.env.DFP_API_KEY;
const API_BASE = (process.env.DFP_API_URL || "https://dealflowpro.io").replace(/\/$/, "");

if (!API_KEY) {
  console.error("Error: DFP_API_KEY environment variable is required.");
  console.error("Get your API key at https://dealflowpro.io");
  process.exit(1);
}

async function callApi(endpoint, body) {
  const response = await fetch(`${API_BASE}/api/v1/${endpoint}`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
      "User-Agent": USER_AGENT,
    },
    body: JSON.stringify(body),
  });

  const data = await response.json();

  if (!response.ok || !data.success) {
    const errorMsg = data.error?.message || data.error || "API call failed";
    throw new Error(`DFP API error (${response.status}): ${errorMsg}`);
  }

  return data;
}

function formatCurrency(n) {
  if (n == null) return "N/A";
  return "$" + Math.round(n).toLocaleString("en-US");
}

function formatPercent(n) {
  if (n == null) return "N/A";
  return n.toFixed(2) + "%";
}

function formatAnalysisResult(data) {
  const d = data.data;
  const m = d.metrics || {};
  const f = d.financials || {};
  const s = d.dfp_score || {};
  const mo = d.max_offer || {};

  let result = `## Deal Analysis Results\n\n`;
  result += `**DFP Score: ${s.score ?? "N/A"}/100 (${s.band?.label ?? "N/A"})**\n\n`;

  result += `### Key Metrics\n`;
  result += `| Metric | Value |\n|--------|-------|\n`;
  result += `| Cap Rate | ${formatPercent(m.going_in_cap_rate)} |\n`;
  result += `| DSCR | ${m.going_in_dscr ?? "N/A"} |\n`;
  result += `| Cash-on-Cash | ${formatPercent(m.cash_on_cash)} |\n`;
  result += `| Avg Cash-on-Cash | ${formatPercent(m.avg_cash_on_cash)} |\n`;
  result += `| IRR | ${formatPercent(m.irr)} |\n`;
  result += `| Equity Multiple | ${m.equity_multiple ?? "N/A"}x |\n`;
  result += `| OER | ${formatPercent(m.operating_expense_ratio)} |\n\n`;

  result += `### Financials\n`;
  result += `| Item | Value |\n|------|-------|\n`;
  result += `| NOI | ${formatCurrency(f.net_operating_income)} |\n`;
  result += `| Annual Debt Service | ${formatCurrency(f.annual_debt_service)} |\n`;
  result += `| Annual Cash Flow | ${formatCurrency(f.annual_cash_flow)} |\n`;
  result += `| Total Cash Required | ${formatCurrency(f.total_cash_invested)} |\n`;
  result += `| Loan Amount | ${formatCurrency(f.loan_amount)} |\n\n`;

  if (mo.binding_price) {
    result += `### Max Offer Price\n`;
    result += `**${formatCurrency(mo.binding_price)}** (binding constraint: ${mo.binding_key})\n\n`;
    if (mo.metrics) {
      result += `| Constraint | Max Price |\n|------------|----------|\n`;
      for (const [key, val] of Object.entries(mo.metrics)) {
        result += `| ${val.label} (${val.threshold}) | ${formatCurrency(val.maxPrice)} |\n`;
      }
      result += `\n`;
    }
  }

  return result;
}

// Create MCP server
const server = new McpServer({
  name: "DealFlowPro",
  version: "1.2.7",
});

// Tool: analyze_deal
// Annotation values mirror the remote server's mcp_tools.php so the two
// surfaces describe the same tools identically.
server.registerTool(
  "analyze_deal",
  {
    title: "Analyze Multifamily Deal",
    description: "Analyze a multifamily real estate deal. Returns cap rate, cash-on-cash, DSCR, IRR, DFP Score (0-100), max offer price, and full financial projections. Use this when someone asks about analyzing a property, evaluating a deal, or running the numbers on a multifamily investment.",
    annotations: {
      title: "Analyze Multifamily Deal",
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
    purchase_price: z.number().describe("Asking/purchase price in dollars"),
    units: z.number().optional().describe("Number of apartment units"),
    monthly_income: z.number().describe("Total monthly rental income in dollars"),
    monthly_expenses: z.number().optional().describe("Total monthly operating expenses in dollars (if omitted, 50% of income is assumed)"),
    property_address: z.string().optional().describe("Property location (city, state)"),
    year_built: z.number().optional().describe("Year the property was built"),
    assumptions: z.object({
      "down-payment": z.number().optional().describe("Down payment percentage (default 25)"),
      "interest-rate": z.number().optional().describe("Loan interest rate percentage (default 6.5)"),
      "vacancy-rate": z.number().optional().describe("Vacancy rate percentage (default 7)"),
      "holding-period": z.number().optional().describe("Hold period in years (default 5)"),
      "exit-cap-rate": z.number().optional().describe("Exit cap rate percentage (default 6.5)"),
    }).optional().describe("Override default underwriting assumptions"),
    },
  },
  async (params) => {
    const body = {
      deal: {
        purchase_price: params.purchase_price,
        units: params.units || 0,
        monthly_income: params.monthly_income,
        monthly_expenses: params.monthly_expenses || 0,
        property_address: params.property_address || "",
        year_built: params.year_built,
      },
      assumptions: params.assumptions || null,
      scenario: "proforma",
    };

    const result = await callApi("analyze", body);
    return { content: [{ type: "text", text: formatAnalysisResult(result) }] };
  }
);

// Tool: score_deal
server.registerTool(
  "score_deal",
  {
    title: "Score Multifamily Deal (Quick)",
    description: "Quick-score a multifamily deal on the DFP 0-100 scale. Returns the DFP Score and key metrics. Faster than full analysis — use this for quick screening.",
    annotations: {
      title: "Score Multifamily Deal (Quick)",
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      purchase_price: z.number().describe("Asking/purchase price in dollars"),
      units: z.number().optional().describe("Number of apartment units"),
      monthly_income: z.number().describe("Total monthly rental income in dollars"),
      monthly_expenses: z.number().optional().describe("Total monthly operating expenses in dollars"),
      property_address: z.string().optional().describe("Property location"),
    },
  },
  async (params) => {
    const body = {
      deal: {
        purchase_price: params.purchase_price,
        units: params.units || 0,
        monthly_income: params.monthly_income,
        monthly_expenses: params.monthly_expenses || 0,
        property_address: params.property_address || "",
      },
    };

    const result = await callApi("score", body);
    const d = result.data;
    const s = d.dfp_score || {};
    const km = d.key_metrics || {};

    let text = `## DFP Score: ${s.score ?? "N/A"}/100 (${s.band?.label ?? "N/A"})\n\n`;
    text += `| Metric | Value |\n|--------|-------|\n`;
    text += `| Cap Rate | ${formatPercent(km.cap_rate)} |\n`;
    text += `| DSCR | ${km.dscr ?? "N/A"} |\n`;
    text += `| Cash-on-Cash | ${formatPercent(km.cash_on_cash)} |\n`;
    text += `| NOI | ${formatCurrency(km.noi)} |\n`;

    return { content: [{ type: "text", text }] };
  }
);

// Tool: reverse_calc
server.registerTool(
  "reverse_calc",
  {
    title: "Reverse-Calculate Max Offer Price",
    description: "Calculate the maximum offer price for a multifamily deal based on target return metrics. Back-solves from your desired cap rate, cash-on-cash, DSCR, and/or IRR to find what you should pay. Use this when someone asks 'what should I offer?' or 'what's the max price?'",
    annotations: {
      title: "Reverse-Calculate Max Offer Price",
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
    monthly_income: z.number().describe("Total monthly rental income in dollars"),
    monthly_expenses: z.number().optional().describe("Total monthly operating expenses in dollars"),
    units: z.number().optional().describe("Number of apartment units"),
    targets: z.object({
      cap_rate: z.number().optional().describe("Target cap rate (e.g., 7 for 7%)"),
      cash_on_cash: z.number().optional().describe("Target cash-on-cash return (e.g., 8 for 8%)"),
      dscr: z.number().optional().describe("Target DSCR (e.g., 1.25)"),
      irr: z.number().optional().describe("Target IRR (e.g., 15 for 15%)"),
    }).describe("Target return metrics — provide at least one"),
    assumptions: z.object({
      "down-payment": z.number().optional(),
      "interest-rate": z.number().optional(),
      "vacancy-rate": z.number().optional(),
      "holding-period": z.number().optional(),
      "exit-cap-rate": z.number().optional(),
    }).optional().describe("Override default underwriting assumptions"),
    },
  },
  async (params) => {
    const body = {
      deal: {
        monthly_income: params.monthly_income,
        monthly_expenses: params.monthly_expenses || 0,
        units: params.units || 0,
      },
      targets: params.targets,
      assumptions: params.assumptions || null,
      scenario: "proforma",
    };

    const result = await callApi("reverse-calc", body);
    const d = result.data;

    let text = `## Max Offer Price: ${formatCurrency(d.max_offer_price)}\n\n`;
    text += `**Binding constraint: ${d.binding_constraint}**\n`;
    if (d.price_per_unit) text += `Price per unit: ${formatCurrency(d.price_per_unit)}\n`;
    text += `\n`;

    text += `| Target Metric | Max Price |\n|---------------|----------|\n`;
    for (const [key, val] of Object.entries(d.max_prices || {})) {
      text += `| ${key.replace("by_", "")} | ${val ? formatCurrency(val) : "Unsolvable"} |\n`;
    }

    return { content: [{ type: "text", text }] };
  }
);

// Tool: market_data
server.registerTool(
  "market_data",
  {
    title: "Lookup Property Market Data",
    description: "Look up market intelligence for a property address. Returns flood zone, neighborhood income relative to state median, and job growth rate. Use this when someone asks about a market, neighborhood, or location.",
    annotations: {
      title: "Lookup Property Market Data",
      readOnlyHint: true,
      destructiveHint: false,
      // External sources (FEMA flood zones, Census ACS, BLS job growth)
      // can revise between calls, so results are not idempotent.
      idempotentHint: false,
      openWorldHint: true,
    },
    inputSchema: {
      address: z.string().describe("Full property address including city and state (e.g., '2909 Burgess Dr, Charlotte, NC 28208')"),
      zip: z.string().optional().describe("ZIP code (extracted from address if not provided)"),
    },
  },
  async (params) => {
    const result = await callApi("market", { address: params.address, zip: params.zip || "" });
    const d = result.data;

    let text = `## Market Data: ${d.address}\n\n`;
    text += `| Factor | Value |\n|--------|-------|\n`;
    text += `| Flood Zone | ${d.flood_zone.zone_code || "Unknown"} (${d.flood_zone.in_flood_zone === true ? "In flood zone" : d.flood_zone.in_flood_zone === false ? "Not in flood zone" : "Unknown"}) |\n`;
    text += `| Neighborhood Income vs State Median | ${d.neighborhood_income.vs_state_median != null ? d.neighborhood_income.vs_state_median + "%" : "Unknown"} |\n`;
    text += `| Job Growth Rate | ${d.job_growth.rate != null ? d.job_growth.rate + "%" : "Unknown"} |\n`;

    return { content: [{ type: "text", text }] };
  }
);

// Start server
const transport = new StdioServerTransport();
await server.connect(transport);
