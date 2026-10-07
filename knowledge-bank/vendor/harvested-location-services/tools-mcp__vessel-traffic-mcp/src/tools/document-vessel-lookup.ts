import { z } from 'zod/v4';

import type { CredentialStore } from '../config/credentials.js';
import type { ProviderRegistry } from '../providers/registry.js';
import { vesselNameResolve } from './vessel-name-resolve.js';
import { nowIso, routingInputShape, type RoutingInput } from './vessel-routing.js';

export const documentVesselLookupInputSchema = z
  .object({
    text: z.string().min(1).optional(),
    hint: z
      .object({
        expectedPorts: z.array(z.string().min(1)).max(20).optional(),
        voyageNumber: z.string().min(1).optional(),
        carrier: z.string().min(1).optional(),
      })
      .strict()
      .optional(),
    limit: z.number().int().positive().max(50).optional(),
    ...routingInputShape,
  })
  .superRefine((data, ctx) => {
    if (!data.text || data.text.trim().length === 0) {
      ctx.addIssue({
        code: 'custom',
        path: ['text'],
        message: 'document_vessel_lookup requires non-empty text.',
      });
    }
  });

export type DocumentVesselLookupInput = z.infer<typeof documentVesselLookupInputSchema>;

interface Deps {
  registry: ProviderRegistry;
  credentialStore: CredentialStore;
}

export interface DocumentVesselSignals {
  vesselName?: string;
  voyageNumber?: string;
  carrier?: string;
  imo?: string;
  mmsi?: string;
  callsign?: string;
  ports: string[];
  containerNumbers: string[];
  dates: string[];
}

const STOP_BOUNDARY = '(?=\\s{2,}|\\s+(?:VOY|VOYAGE|IMO|MMSI|CALL|POL|POD|CONTAINER|ETD|ETA)\\b|\\n|$)';
const VESSEL_NAME_PATTERN = new RegExp(
  `\\b(?:VESSEL|VSL|MV|M\\/V)\\s*[:\\-]\\s*([A-Z][A-Z0-9.\\-\\/ ]*?)${STOP_BOUNDARY}`,
  'i',
);
const IMO_PATTERN = /\bIMO\s*[:#]?\s*(\d{7})\b/i;
const MMSI_PATTERN = /\bMMSI\s*[:#]?\s*(\d{9})\b/i;
const CALLSIGN_PATTERN = /\bCALL\s*SIGN\s*[:#]?\s*([A-Z0-9]{3,10})\b/i;
const VOYAGE_PATTERN = /\b(?:VOYAGE|VOY|V\/N)\b\.?\s*[:#]?\s*([A-Z0-9\-/]{1,16})\b/i;
const CARRIER_PATTERN = new RegExp(
  `\\bCARRIER\\s*[:#]?\\s*([A-Z][A-Z0-9 .,&\\-\\/]*?)${STOP_BOUNDARY}`,
  'i',
);
const PORT_PATTERN = /\b(?:POL|POD|PORT\s+OF\s+(?:LOADING|DISCHARGE)|FROM|TO)\s*[:#]?\s*([A-Z][A-Z0-9]{4})\b/gi;
const UNLOCODE_PATTERN = /\b([A-Z]{2}[A-Z0-9]{3})\b/g;
const CONTAINER_PATTERN = /\b([A-Z]{4}\d{7})\b/g;
const ISO_DATE_PATTERN = /\b(\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+\-]\d{2}:?\d{2})?)?)\b/g;

function dedupe(values: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    if (!seen.has(value)) {
      seen.add(value);
      out.push(value);
    }
  }
  return out;
}

export function extractDocumentSignals(rawText: string): DocumentVesselSignals {
  const text = rawText.trim();
  const upper = text.toUpperCase();
  const vesselMatch = upper.match(VESSEL_NAME_PATTERN);
  const imoMatch = upper.match(IMO_PATTERN);
  const mmsiMatch = upper.match(MMSI_PATTERN);
  const callsignMatch = upper.match(CALLSIGN_PATTERN);
  const voyageMatch = upper.match(VOYAGE_PATTERN);
  const carrierMatch = upper.match(CARRIER_PATTERN);

  const ports: string[] = [];
  let portMatch: RegExpExecArray | null;
  const portRegex = new RegExp(PORT_PATTERN.source, 'gi');
  while ((portMatch = portRegex.exec(upper)) !== null) {
    if (portMatch[1]) ports.push(portMatch[1].trim());
  }
  const unlocodeRegex = new RegExp(UNLOCODE_PATTERN.source, 'g');
  let unlocodeMatch: RegExpExecArray | null;
  while ((unlocodeMatch = unlocodeRegex.exec(upper)) !== null) {
    ports.push(unlocodeMatch[1]);
  }
  const containerRegex = new RegExp(CONTAINER_PATTERN.source, 'g');
  const containerNumbers: string[] = [];
  let containerMatch: RegExpExecArray | null;
  while ((containerMatch = containerRegex.exec(upper)) !== null) {
    containerNumbers.push(containerMatch[1]);
  }
  const dateRegex = new RegExp(ISO_DATE_PATTERN.source, 'g');
  const dates: string[] = [];
  let dateMatch: RegExpExecArray | null;
  while ((dateMatch = dateRegex.exec(text)) !== null) {
    dates.push(dateMatch[1]);
  }

  return {
    vesselName: vesselMatch?.[1]?.trim().replace(/\s+/g, ' '),
    voyageNumber: voyageMatch?.[1]?.trim(),
    carrier: carrierMatch?.[1]?.trim(),
    imo: imoMatch?.[1],
    mmsi: mmsiMatch?.[1],
    callsign: callsignMatch?.[1],
    ports: dedupe(ports),
    containerNumbers: dedupe(containerNumbers),
    dates: dedupe(dates),
  };
}

export async function documentVesselLookup(
  deps: Deps,
  input: DocumentVesselLookupInput,
): Promise<Record<string, unknown>> {
  const retrievedAt = nowIso();
  const text = (input.text ?? '').trim();
  const signals = extractDocumentSignals(text);
  const routing: RoutingInput = {
    provider: input.provider,
    credentialProfile: input.credentialProfile,
    oneTimeCredential: input.oneTimeCredential,
    fallbackPolicy: input.fallbackPolicy,
    coverageHint: input.coverageHint,
  };

  if (!signals.vesselName && !signals.mmsi && !signals.imo && !signals.callsign) {
    return {
      ok: false,
      reason: 'identifier_not_found',
      message:
        'No vessel name, IMO, MMSI, or call sign detected in the supplied document text.',
      retrievedAt,
      signals,
      candidates: [],
      caveats: ['Document parser found no vessel signals; supply a name, IMO, MMSI, or call sign.'],
      dataState: 'no_candidates',
    };
  }

  const resolution = await vesselNameResolve(deps, {
    name: signals.vesselName || undefined,
    mmsi: signals.mmsi,
    imo: signals.imo,
    callsign: signals.callsign,
    ports: input.hint?.expectedPorts ?? signals.ports,
    voyageNumber: input.hint?.voyageNumber ?? signals.voyageNumber,
    carrier: input.hint?.carrier ?? signals.carrier,
    dates: signals.dates,
    limit: input.limit,
    ...routing,
  });
  return {
    ...resolution,
    signals,
  };
}
