import { wrapFetchWithPayment } from "@x402/fetch";
import { x402Client, x402HTTPClient } from "@x402/core/client";
import { registerExactEvmScheme } from "@x402/evm/exact/client";
import { privateKeyToAccount } from "viem/accounts";
import { createPublicClient, formatEther, formatUnits, http } from "viem";
import { base, baseSepolia } from "viem/chains";

const argv = process.argv.slice(2);
const args = new Set(argv);
const challengeOnly = args.has("--challenge-only");
const scenarioIndex = argv.indexOf("--scenario");
const scenario = String(
  scenarioIndex >= 0 && argv[scenarioIndex + 1] ? argv[scenarioIndex + 1] : "earthquakes",
).trim().toLowerCase();
const limitIndex = argv.indexOf("--limit");
const limitOverrideRaw = limitIndex >= 0 && argv[limitIndex + 1] ? argv[limitIndex + 1] : "";
const limitOverride = limitOverrideRaw ? Number.parseInt(String(limitOverrideRaw), 10) : null;
const expectNetworkIndex = argv.indexOf("--expect-network");
const expectedNetwork = String(
  expectNetworkIndex >= 0 && argv[expectNetworkIndex + 1] ? argv[expectNetworkIndex + 1] : "",
).trim();
const requireSettlementSuccess = args.has("--require-settlement-success");
const baseUrl = (process.env.DAEDALMAP_API_BASE_URL || "https://app.daedalmap.com").replace(/\/$/, "");
const endpoint = `${baseUrl}/api/v1/query/dataset`;

if (limitOverrideRaw && (!Number.isFinite(limitOverride) || limitOverride <= 0)) {
  throw new Error(`Invalid --limit value '${limitOverrideRaw}'. Use a positive integer.`);
}

function buildPayload(name) {
  const requestId = `buyer-test-${name}-${Date.now()}`;
  if (name === "currency") {
    const payload = {
      request_id: requestId,
      pack_id: "currency",
      metrics: ["local_per_usd"],
      filters: {
        region_ids: ["CAN", "USA", "MEX"],
        time: {
          start: "2015-01-01",
          end: "2024-12-31",
          granularity: "monthly",
        },
      },
      sort: {
        field: "date",
        direction: "asc",
      },
      limit: 3,
      output: {
        format: "rows",
      },
    };
    if (limitOverride !== null) {
      payload.limit = limitOverride;
    }
    return payload;
  }
  if (name === "earthquakes") {
    const payload = {
      request_id: requestId,
      source_id: "earthquakes_events",
      metrics: ["event_count"],
      filters: {
        region_ids: ["JPN", "CHL", "IDN"],
        time: {
          start: "2011-01-01",
          end: "2011-12-31",
        },
      },
      sort: {
        field: "value",
        direction: "desc",
      },
      limit: 3,
      output: {
        format: "rows",
      },
    };
    if (limitOverride !== null) {
      payload.limit = limitOverride;
    }
    return payload;
  }
  if (name === "volcanoes") {
    const payload = {
      request_id: requestId,
      source_id: "volcanoes_events",
      metrics: ["event_count"],
      filters: {
        region_ids: ["IDN", "JPN", "PHL"],
        time: {
          start: 2015,
          end: 2024,
        },
      },
      sort: {
        field: "value",
        direction: "desc",
      },
      limit: 3,
      output: {
        format: "rows",
      },
    };
    if (limitOverride !== null) {
      payload.limit = limitOverride;
    }
    return payload;
  }
  if (name === "tsunamis") {
    const payload = {
      request_id: requestId,
      source_id: "tsunamis_events",
      metrics: ["event_count"],
      filters: {
        region_ids: ["JPN", "IDN", "XOO"],
        time: {
          start: 2000,
          end: 2024,
        },
      },
      sort: {
        field: "value",
        direction: "desc",
      },
      limit: 3,
      output: {
        format: "rows",
      },
    };
    if (limitOverride !== null) {
      payload.limit = limitOverride;
    }
    return payload;
  }
  throw new Error(
    `Unknown scenario '${name}'. Use --scenario currency, --scenario earthquakes, --scenario volcanoes, or --scenario tsunamis.`,
  );
}

const payload = buildPayload(scenario);

function decodePaymentRequired(headerValue) {
  if (!headerValue) {
    return null;
  }
  try {
    const decoded = Buffer.from(headerValue, "base64").toString("utf8");
    return JSON.parse(decoded);
  } catch (error) {
    return {
      decode_error: String(error),
      raw: headerValue,
    };
  }
}

function collectNetworks(value, acc = new Set()) {
  if (!value) {
    return acc;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed.startsWith("eip155:")) {
      acc.add(trimmed);
    }
    return acc;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      collectNetworks(item, acc);
    }
    return acc;
  }
  if (typeof value === "object") {
    for (const [key, nested] of Object.entries(value)) {
      if (key.toLowerCase().includes("network") || key.toLowerCase().includes("chain")) {
        collectNetworks(nested, acc);
      } else {
        collectNetworks(nested, acc);
      }
    }
  }
  return acc;
}

function extractChallengeNetworks(decodedRequirements) {
  return Array.from(collectNetworks(decodedRequirements));
}

function extractChallengeAmount(decodedRequirements) {
  const requirement =
    decodedRequirements && Array.isArray(decodedRequirements.accepts)
      ? decodedRequirements.accepts[0]
      : decodedRequirements;
  const rawAmount =
    requirement?.maxAmountRequired ??
    requirement?.max_amount_required ??
    requirement?.amount ??
    null;
  if (rawAmount === null || rawAmount === undefined) {
    return null;
  }
  const amount = String(rawAmount).trim();
  return amount || null;
}

function settlementTransactionSummary(settleResponse) {
  if (!settleResponse || typeof settleResponse !== "object") {
    return null;
  }
  const transaction =
    settleResponse.transactionHash ||
    settleResponse.transaction_hash ||
    settleResponse.txHash ||
    settleResponse.tx_hash ||
    settleResponse.transaction ||
    settleResponse.tx ||
    null;
  const success =
    typeof settleResponse.success === "boolean"
      ? settleResponse.success
      : typeof settleResponse.settled === "boolean"
        ? settleResponse.settled
        : null;
  return {
    success,
    transaction,
  };
}

function getChainConfig(network) {
  if (network === "eip155:8453") {
    return {
      chain: base,
      rpcUrl: "https://mainnet.base.org",
      label: "Base mainnet",
    };
  }
  if (network === "eip155:84532") {
    return {
      chain: baseSepolia,
      rpcUrl: "https://sepolia.base.org",
      label: "Base Sepolia",
    };
  }
  return null;
}

async function inspectBuyerBalances(paymentRequirements, payerAddress) {
  const accepted =
    paymentRequirements && Array.isArray(paymentRequirements.accepts)
      ? paymentRequirements.accepts[0]
      : paymentRequirements;
  if (!accepted || !accepted.network || !accepted.asset || !accepted.amount) {
    return null;
  }

  const chainConfig = getChainConfig(String(accepted.network));
  if (!chainConfig) {
    return {
      skipped: true,
      reason: `Unsupported network for preflight balance check: ${accepted.network}`,
    };
  }

  const client = createPublicClient({
    chain: chainConfig.chain,
    transport: http(chainConfig.rpcUrl),
  });
  const erc20Abi = [
    {
      type: "function",
      name: "balanceOf",
      stateMutability: "view",
      inputs: [{ name: "account", type: "address" }],
      outputs: [{ type: "uint256" }],
    },
  ];

  const [nativeBalance, assetBalance] = await Promise.all([
    client.getBalance({ address: payerAddress }),
    client.readContract({
      address: accepted.asset,
      abi: erc20Abi,
      functionName: "balanceOf",
      args: [payerAddress],
    }),
  ]);

  return {
    skipped: false,
    network: accepted.network,
    network_label: chainConfig.label,
    payer: payerAddress,
    asset: accepted.asset,
    required_amount_base_units: accepted.amount,
    asset_balance_base_units: assetBalance.toString(),
    asset_balance_display: formatUnits(assetBalance, 6),
    native_balance_wei: nativeBalance.toString(),
    native_balance_display: formatEther(nativeBalance),
    sufficient_asset_balance: assetBalance >= BigInt(accepted.amount),
  };
}

async function readBody(response) {
  const text = await response.text();
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function runChallengeProbe() {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const paymentRequired = response.headers.get("payment-required");
  const decodedRequirements = decodePaymentRequired(paymentRequired);
  const challengeNetworks = extractChallengeNetworks(decodedRequirements);
  const challengeAmount = extractChallengeAmount(decodedRequirements);
  const body = await readBody(response);

  if (expectedNetwork && !challengeNetworks.includes(expectedNetwork)) {
    throw new Error(
      `Challenge network mismatch. Expected '${expectedNetwork}', got ${JSON.stringify(challengeNetworks) || "[]"}.`,
    );
  }

  console.log("Challenge probe:");
  console.log(JSON.stringify({
    request_id: payload.request_id,
    limit: payload.limit,
    challenged_amount_usdc_base_units: challengeAmount,
    expected_network: expectedNetwork || null,
    status: response.status,
    payment_required_present: Boolean(paymentRequired),
    challenge_networks: challengeNetworks,
    payment_requirements: decodedRequirements,
    body,
  }, null, 2));

  return response;
}

async function runPaidRequest(paymentRequirements) {
  const rawPrivateKey = (process.env.EVM_PRIVATE_KEY || "").trim();
  const privateKey = rawPrivateKey.startsWith("0x") ? rawPrivateKey : `0x${rawPrivateKey}`;
  if (!privateKey) {
    throw new Error("EVM_PRIVATE_KEY is required for paid x402 retries.");
  }

  const signer = privateKeyToAccount(privateKey);
  const buyerPreflight = await inspectBuyerBalances(paymentRequirements, signer.address);
  console.log("Buyer preflight:");
  console.log(JSON.stringify(buyerPreflight, null, 2));
  if (buyerPreflight && buyerPreflight.skipped !== true && buyerPreflight.sufficient_asset_balance !== true) {
    throw new Error(
      `Buyer wallet ${signer.address} has insufficient token balance for the challenged payment. ` +
        `Required ${buyerPreflight.required_amount_base_units} base units, found ${buyerPreflight.asset_balance_base_units}.`,
    );
  }

  const client = new x402Client();
  registerExactEvmScheme(client, { signer });
  const fetchWithPayment = wrapFetchWithPayment(fetch, client);

  const response = await fetchWithPayment(endpoint, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const body = await readBody(response);
  const httpClient = new x402HTTPClient(client);
  let settleResponse = null;
  let settleResponseError = null;
  try {
    settleResponse = httpClient.getPaymentSettleResponse(
      (name) => response.headers.get(name),
    );
  } catch (error) {
    settleResponseError = String(error);
  }
  const settlementSummary = settlementTransactionSummary(settleResponse);

  if (requireSettlementSuccess) {
    if (!settlementSummary || settlementSummary.success !== true) {
      throw new Error(
        `Expected settlement success, got ${JSON.stringify(settlementSummary)} with error ${settleResponseError || "none"}.`,
      );
    }
  }

  console.log("Paid request:");
  console.log(JSON.stringify({
    request_id: payload.request_id,
    limit: payload.limit,
    challenged_amount_usdc_base_units: extractChallengeAmount(paymentRequirements),
    require_settlement_success: requireSettlementSuccess,
    status: response.status,
    settle_response_error: settleResponseError,
    settlement_summary: settlementSummary,
    settle_response: settleResponse,
    body,
  }, null, 2));
}

async function main() {
  console.log(`Testing x402 endpoint: ${endpoint}`);
  console.log(`Scenario: ${scenario}`);
  console.log(`Mode: ${challengeOnly ? "challenge-only" : "challenge + paid retry"}`);
  if (expectedNetwork) {
    console.log(`Expected network: ${expectedNetwork}`);
  }
  console.log(JSON.stringify({ request_preview: payload }, null, 2));
  const challengeResponse = await runChallengeProbe();

  if (challengeOnly) {
    return;
  }

  const challengeRequirements = decodePaymentRequired(challengeResponse.headers.get("payment-required"));
  await runPaidRequest(challengeRequirements);
}

main().catch((error) => {
  console.error("x402 dataset test failed:");
  console.error(error);
  process.exitCode = 1;
});
