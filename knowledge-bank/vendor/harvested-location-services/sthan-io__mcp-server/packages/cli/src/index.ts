#!/usr/bin/env node

import { Command } from "commander";
import {
  resolveApiKey,
  saveApiKey,
  maskApiKey,
  CREDENTIALS_FILE,
} from "./credentials.js";
import { getClient } from "./client.js";
import { str, pick, obj, die, printFields } from "./output.js";
import { runBatch } from "./batch.js";
import type { BatchOp, BatchOptions } from "./batch.js";

const VERSION = "0.1.7";

const program = new Command();

program
  .name("sthan")
  .description(
    "sthan.io CLI — verify, parse, and geocode US addresses from your terminal"
  )
  .version(VERSION, "-V, --version", "Show CLI version")
  .option(
    "--api-key <key>",
    "API key to use for this command (overrides STHAN_API_KEY and the stored key)"
  );

program
  .command("login")
  .description("Save your sthan.io API key for future commands")
  .requiredOption(
    "--api-key <key>",
    "Your API key (starts with sthan_). Create one at https://sthan.io/dashboard"
  )
  .action((opts: { apiKey: string }) => {
    const path = saveApiKey(opts.apiKey);
    console.log(`✓ API key saved to ${path}`);
    console.log(`  ${maskApiKey(opts.apiKey)}`);
    console.log(`\nTry: sthan verify "123 Main St, New York, NY 10001"`);
  });

program
  .command("whoami")
  .description("Show the API key this CLI will use (masked) and its source")
  .action((_opts, cmd) => {
    const { apiKey } = cmd.optsWithGlobals();
    const resolved = resolveApiKey(apiKey);
    if (!resolved) {
      console.error("Not logged in. Run: sthan login --api-key sthan_...");
      process.exitCode = 2;
      return;
    }
    const where = {
      flag: "--api-key flag",
      env: "STHAN_API_KEY env var",
      file: CREDENTIALS_FILE,
    }[resolved.source];
    console.log(`${maskApiKey(resolved.apiKey)}  (from ${where})`);
  });

interface CommonBatchOptions extends BatchOptions {
  json?: boolean;
}

interface GeocodeOptions extends CommonBatchOptions {
  reverse?: string;
}

const VERIFY_OP: BatchOp = {
  verb: "Verifying",
  call: (c, a) => c.verifyAddress(a).then((res) => res.Result as Record<string, unknown>),
  resultColumns: ["standardized_address", "dpv", "deliverable_status", "zip4", "confidence"],
  mapResult: (r) => ({
    standardized_address: str(r, "fullAddress"),
    dpv: str(r, "dpvConfirmation"),
    deliverable_status: str(r, "deliverableStatus"),
    zip4: [str(r, "zipCode"), str(r, "zip4")].filter(Boolean).join("-"),
    confidence: str(r, "confidence"),
  }),
};

const PARSE_OP: BatchOp = {
  verb: "Parsing",
  call: (c, a) => c.parseAddress(a).then((res) => res.Result as Record<string, unknown>),
  resultColumns: [
    "standardized_address",
    "address_number",
    "street",
    "unit_type",
    "unit_number",
    "city",
    "state_code",
    "zip_code",
    "zip4",
    "county",
  ],
  mapResult: (r) => ({
    standardized_address: str(r, "fullAddress"),
    address_number: str(r, "addressNumber"),
    street: [
      str(r, "streetPreDir"),
      str(r, "streetName"),
      str(r, "streetPostType"),
      str(r, "streetPostDir"),
    ]
      .filter(Boolean)
      .join(" "),
    unit_type: str(r, "unitType"),
    unit_number: str(r, "unitNumber"),
    city: str(r, "city"),
    state_code: str(r, "stateCode"),
    zip_code: str(r, "zipCode"),
    zip4: str(r, "zip4"),
    county: str(r, "county"),
  }),
};

const GEOCODE_OP: BatchOp = {
  verb: "Geocoding",
  call: (c, a) => c.geocodeAddress(a).then((res) => res.Result as Record<string, unknown>),
  resultColumns: ["latitude", "longitude", "formatted_address", "accuracy", "confidence"],
  mapResult: (r) => {
    const loc = obj(r, "location");
    const acc = obj(r, "accuracy");
    return {
      latitude: loc ? str(loc, "latitude") : "",
      longitude: loc ? str(loc, "longitude") : "",
      formatted_address: str(r, "formattedAddress"),
      accuracy: acc ? str(acc, "type") : "",
      confidence: str(r, "confidence"),
    };
  },
};

program
  .command("verify")
  .description("Verify a US address is real and deliverable (single, or batch with --input)")
  .argument("[address]", 'Address, e.g. "123 Main St, New York, NY 10001"')
  .option("--json", "Output the raw JSON response instead of a summary")
  .option("-i, --input <file>", "Batch: read addresses from a .csv/.tsv/.xlsx/.txt file")
  .option("-o, --output <file>", "Batch: write results to a .csv or .xlsx file")
  .option("-c, --column <name>", "Batch: address column name (auto-detected if omitted)")
  .option("--concurrency <n>", "Batch: parallel requests (default 10)")
  .action(async (address: string | undefined, opts: CommonBatchOptions, cmd) => {
    const client = getClient(cmd.optsWithGlobals().apiKey);
    if (opts.input) {
      await runBatch(client, VERIFY_OP, opts);
      return;
    }
    if (!address) {
      console.error("Provide an address, or use --input <file> for batch.");
      process.exit(4);
    }
    try {
      const res = await client.verifyAddress(address);
      const r = res.Result as Record<string, unknown>;
      if (opts.json) {
        console.log(JSON.stringify(r, null, 2));
        return;
      }
      printVerifySummary(r);
    } catch (e) {
      die(e);
    }
  });

/** Stable USPS DPV codes drive the verdict glyph; everything else is shown as-is. */
function printVerifySummary(r: Record<string, unknown>): void {
  // DPV codes are stable; blank DPV = Unknown (NOT the same as N = NotDeliverable).
  const dpv = str(r, "DpvConfirmation").toUpperCase();
  const verdict =
    dpv === "Y"
      ? "✓ deliverable"
      : dpv === "N"
        ? "✗ not deliverable / not found"
        : dpv === "S"
          ? "⚠ deliverable, but unit number missing"
          : dpv === "D"
            ? "⚠ deliverable, but unit not confirmed"
            : "? deliverability unknown (not confirmed)";

  const full = str(r, "FullAddress") || str(r, "AddressLine1");
  console.log(full || "(no standardized address returned)");
  console.log(verdict);

  const fields: Array<[string, string]> = [
    ["ZIP+4", [str(r, "ZipCode"), str(r, "Zip4")].filter(Boolean).join("-")],
    ["Unit", [str(r, "UnitType"), str(r, "UnitNumber")].filter(Boolean).join(" ")],
    ["DPV", dpv],
    ["Deliverable status", str(r, "DeliverableStatus")],
    ["Confidence", str(r, "Confidence")],
    ["Match tier", str(r, "MatchTier")],
    ["County", str(r, "County")],
  ];
  printFields(fields);
  const footnotes = pick(r, "Footnotes");
  if (Array.isArray(footnotes) && footnotes.length) {
    console.log(`  Notes: ${footnotes.join("; ")}`);
  }
}

program
  .command("parse")
  .description("Parse a freeform US address into components (single, or batch with --input)")
  .argument("[address]", 'Address, e.g. "apt 2b 500 broadway new york ny"')
  .option("--json", "Output the raw JSON response instead of a summary")
  .option("-i, --input <file>", "Batch: read addresses from a .csv/.tsv/.xlsx/.txt file")
  .option("-o, --output <file>", "Batch: write results to a .csv or .xlsx file")
  .option("-c, --column <name>", "Batch: address column name (auto-detected if omitted)")
  .option("--concurrency <n>", "Batch: parallel requests (default 10)")
  .action(async (address: string | undefined, opts: CommonBatchOptions, cmd) => {
    const client = getClient(cmd.optsWithGlobals().apiKey);
    if (opts.input) {
      await runBatch(client, PARSE_OP, opts);
      return;
    }
    if (!address) {
      console.error("Provide an address, or use --input <file> for batch.");
      process.exit(4);
    }
    try {
      const res = await client.parseAddress(address);
      const r = res.Result as Record<string, unknown>;
      if (opts.json) return void console.log(JSON.stringify(r, null, 2));
      printParseSummary(r);
    } catch (e) {
      die(e);
    }
  });

program
  .command("geocode")
  .description("Geocode a US address to coordinates (single/batch), or reverse with --reverse")
  .argument("[address]", "Address to geocode (omit when using --reverse)")
  .option("-r, --reverse <lat,lon>", "Reverse geocode, e.g. 38.8977,-77.0365")
  .option("--json", "Output the raw JSON response instead of a summary")
  .option("-i, --input <file>", "Batch: forward-geocode addresses from a .csv/.tsv/.xlsx/.txt file")
  .option("-o, --output <file>", "Batch: write results to a .csv or .xlsx file")
  .option("-c, --column <name>", "Batch: address column name (auto-detected if omitted)")
  .option("--concurrency <n>", "Batch: parallel requests (default 10)")
  .action(async (address: string | undefined, opts: GeocodeOptions, cmd) => {
    const client = getClient(cmd.optsWithGlobals().apiKey);
    if (opts.input) {
      if (opts.reverse) {
        console.error(
          "Batch mode forward-geocodes addresses; --reverse is not supported with --input."
        );
        process.exit(4);
      }
      await runBatch(client, GEOCODE_OP, opts);
      return;
    }
    try {
      let r: Record<string, unknown>;
      if (opts.reverse) {
        const [lat, lon] = opts.reverse.split(",").map((n) => Number(n.trim()));
        if (Number.isNaN(lat) || Number.isNaN(lon)) {
          console.error("Invalid --reverse coordinates. Use lat,lon e.g. 38.8977,-77.0365");
          process.exit(4);
        }
        r = (await client.reverseGeocode(lat, lon)).Result as Record<string, unknown>;
      } else if (address) {
        r = (await client.geocodeAddress(address)).Result as Record<string, unknown>;
      } else {
        console.error("Provide an address, or --reverse lat,lon");
        process.exit(4);
      }
      if (opts.json) return void console.log(JSON.stringify(r, null, 2));
      printGeocodeSummary(r);
    } catch (e) {
      die(e);
    }
  });

program
  .command("ip")
  .description("Look up the geographic location of an IP address")
  .argument("<ip>", "IPv4 or IPv6 address, e.g. 8.8.8.8")
  .option("--json", "Output the raw JSON response instead of a summary")
  .action(async (ip: string, opts: { json?: boolean }, cmd) => {
    const client = getClient(cmd.optsWithGlobals().apiKey);
    try {
      const res = await client.ipGeolocation(ip);
      const r = res.Result as Record<string, unknown>;
      if (opts.json) return void console.log(JSON.stringify(r, null, 2));
      printIpSummary(r);
    } catch (e) {
      die(e);
    }
  });

function printParseSummary(r: Record<string, unknown>): void {
  console.log(str(r, "fullAddress") || "(no parse result)");
  const street = [
    str(r, "streetPreDir"),
    str(r, "streetName"),
    str(r, "streetPostType"),
    str(r, "streetPostDir"),
  ]
    .filter(Boolean)
    .join(" ");
  printFields([
    ["Number", str(r, "addressNumber")],
    ["Street", street],
    ["Unit", [str(r, "unitType"), str(r, "unitNumber")].filter(Boolean).join(" ")],
    ["City", str(r, "city")],
    ["State", str(r, "stateCode")],
    ["ZIP+4", [str(r, "zipCode"), str(r, "zip4")].filter(Boolean).join("-")],
    ["County", str(r, "county")],
    ["Confidence", str(r, "confidence")],
  ]);
}

function printGeocodeSummary(r: Record<string, unknown>): void {
  console.log(str(r, "formattedAddress") || "(no result)");
  const loc = obj(r, "location");
  if (loc) {
    const coords = [str(loc, "latitude"), str(loc, "longitude")].filter(Boolean).join(", ");
    if (coords) console.log(`  ${coords}`);
  }
  const acc = obj(r, "accuracy");
  printFields([
    ["Accuracy", acc ? str(acc, "type") : ""],
    ["Confidence", str(r, "confidence")],
    ["Distance (m)", str(r, "distance")],
  ]);
}

function printIpSummary(r: Record<string, unknown>): void {
  console.log(str(r, "ipAddress") || "(no result)");
  const place = [str(r, "city"), str(r, "region"), str(r, "country")]
    .filter(Boolean)
    .join(", ");
  if (place) console.log(`  ${place}`);
  const tz = r["timezoneDetail"] as Record<string, unknown> | undefined;
  const flags = [r["isMobile"] ? "mobile" : "", r["isProxy"] ? "proxy/VPN" : "", r["isHosting"] ? "hosting" : ""].filter(Boolean).join(", ");
  const conf = r["confidence"];
  printFields([
    ["Coordinates", [str(r, "latitude"), str(r, "longitude")].filter(Boolean).join(", ")],
    ["Postal code", str(r, "postalCode")],
    ["Timezone", str(r, "timezone") + (tz && tz["currentLocalTime"] ? ` (local time ${String(tz["currentLocalTime"])})` : "")],
    ["Network", [str(r, "asn") ? `AS${str(r, "asn")}` : "", str(r, "asName"), str(r, "isp")].filter(Boolean).join(" ")],
    ["Flags", flags],
    ["Reverse DNS", str(r, "reverseDns")],
    ["Confidence", typeof conf === "number" ? `${Math.round(conf * 100)}% agreement on the city` : ""],
    ["Precision", str(r, "precision")],
  ]);
}

program.parseAsync(process.argv);
