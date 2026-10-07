import { z } from 'zod/v4';

import { carrierScheduleSearchInputSchema } from '../tools/carrier-schedule-search.js';
import { agentFetchInputSchema, agentSearchInputSchema } from '../tools/agent-search.js';
import { documentVesselLookupInputSchema } from '../tools/document-vessel-lookup.js';
import { portCallsInputSchema } from '../tools/port-calls.js';
import { providerOnboardingInputSchema } from '../tools/provider-onboarding.js';
import { scheduleDelayPredictInputSchema } from '../tools/schedule-delay-predict.js';
import { vesselAreaInputSchema } from '../tools/vessel-area.js';
import { vesselNameResolveInputSchema } from '../tools/vessel-name-resolve.js';
import { vesselPositionInputSchema } from '../tools/vessel-position.js';
import { vesselScheduleInputSchema } from '../tools/vessel-schedule.js';
import { vesselSearchInputSchema } from '../tools/vessel-search.js';
import { vesselTrackInputSchema } from '../tools/vessel-track.js';

export const serverVersion = '0.1.0';

const readOnlyAnnotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: false,
} as const;

interface ToolCardDefinition {
  name: string;
  title: string;
  description: string;
  inputSchema?: z.ZodType;
}

export const vesselMcpToolCards: readonly ToolCardDefinition[] = [
  {
    name: 'search',
    title: 'Search Vessel Traffic MCP',
    description:
      'Search this MCP server for vessel or ship-tracking results by natural-language vessel name, MMSI, or IMO. Returns result ids for fetch plus source, freshness, confidence, and navigation caveats.',
    inputSchema: agentSearchInputSchema,
  },
  {
    name: 'fetch',
    title: 'Fetch Vessel Traffic MCP Result',
    description:
      'Fetch an agent-readable vessel result returned by search. Use for ChatGPT/OpenAI, Claude, Codex, Gemini, and other search-style MCP clients that expect search/fetch tools.',
    inputSchema: agentFetchInputSchema,
  },
  {
    name: 'provider_status',
    title: 'Provider Status',
    description: 'List configured vessel data providers, auth state, feature support, quota hints, and caveats.',
  },
  {
    name: 'data_sources',
    title: 'Data Sources',
    description: 'List available vessel data source adapters, coverage notes, auth mode, and caveats.',
  },
  {
    name: 'credential_profiles',
    title: 'Credential Profiles',
    description:
      'List BYOK credential profile labels, provider hints, declared field names, and status. Raw keys are never returned.',
  },
  {
    name: 'provider_onboarding',
    title: 'Provider Onboarding',
    description:
      'Show safe manual signup, API docs, credential env vars, configured status, and validation steps for provider access. Does not create accounts or issue credentials.',
    inputSchema: providerOnboardingInputSchema,
  },
  {
    name: 'vessel_search',
    title: 'Vessel Search',
    description:
      'Search vessels by MMSI, IMO, name, or callsign. Requires at least one identifier; returns normalized identities with provider source metadata.',
    inputSchema: vesselSearchInputSchema,
  },
  {
    name: 'vessel_name_resolve',
    title: 'Vessel Name Resolve',
    description:
      'Resolve a messy vessel name, for example from B/L text, to ranked MMSI/IMO candidates with matched/missing signals and confidence.',
    inputSchema: vesselNameResolveInputSchema,
  },
  {
    name: 'document_vessel_lookup',
    title: 'Document Vessel Lookup',
    description:
      'Extract vessel signals from B/L-style text and return ranked candidates for names, IMO/MMSI, callsigns, voyages, ports, containers, and dates.',
    inputSchema: documentVesselLookupInputSchema,
  },
  {
    name: 'vessel_position',
    title: 'Vessel Position',
    description:
      'Return the latest known position for a vessel by MMSI or IMO with source, retrievedAt, observedAt, and freshness metadata.',
    inputSchema: vesselPositionInputSchema,
  },
  {
    name: 'vessel_area',
    title: 'Vessel Area',
    description:
      'Return latest known positions for vessels inside a bounding box with provider source metadata.',
    inputSchema: vesselAreaInputSchema,
  },
  {
    name: 'vessel_track',
    title: 'Vessel Track',
    description:
      'Return recent track points for a vessel by MMSI or IMO, optionally bounded by ISO-8601 windowStart/windowEnd.',
    inputSchema: vesselTrackInputSchema,
  },
  {
    name: 'port_calls',
    title: 'Port Calls',
    description:
      'Return recent port-call events for a vessel by MMSI/IMO or for a UN/LOCODE port. Requires at least one filter.',
    inputSchema: portCallsInputSchema,
  },
  {
    name: 'carrier_schedule_search',
    title: 'Carrier Schedule Search',
    description:
      'Search carrier sailing schedules by origin/destination, carrier SCAC/name, cargo type, direct-only flag, and departure/arrival windows. Returns normalized schedules with upstream source metadata.',
    inputSchema: carrierScheduleSearchInputSchema,
  },
  {
    name: 'vessel_schedule',
    title: 'Vessel Schedule',
    description:
      'Return scheduled carrier port calls for a vessel by MMSI, IMO, vessel name, voyage number, or carrier SCAC with source metadata.',
    inputSchema: vesselScheduleInputSchema,
  },
  {
    name: 'schedule_delay_predict',
    title: 'Schedule Delay Predict',
    description:
      'Compare planned carrier schedule timestamps with estimated/actual timestamps and return an on-time, at-risk, delayed, or unknown heuristic.',
    inputSchema: scheduleDelayPredictInputSchema,
  },
] as const;

export interface ServerCardOptions {
  mcpPath: string;
  authRequired: boolean;
}

export function createServerCard(options: ServerCardOptions): Record<string, unknown> {
  return {
    schemaVersion: '1.0',
    serverInfo: {
      name: 'vessel-traffic-mcp',
      version: serverVersion,
    },
    name: 'vessel-traffic-mcp',
    mcpName: 'io.github.tools-mcp/vessel-traffic-mcp',
    title: 'Vessel Traffic MCP',
    version: serverVersion,
    description:
      'Read-only MCP server for vessel identity, AIS-style positions, tracks, port calls, carrier schedules, vessel schedules, and delay heuristics.',
    repository: 'https://github.com/tools-mcp/vessel-traffic-mcp',
    website: 'https://tools-mcp.github.io/vessel-traffic-mcp/',
    license: 'MIT',
    transport: {
      type: 'streamable-http',
      endpoint: options.mcpPath,
      authentication: {
        required: options.authRequired,
        type: options.authRequired ? 'bearer' : 'none',
      },
    },
    authentication: {
      required: options.authRequired,
      schemes: options.authRequired ? ['bearer'] : [],
    },
    packages: [
      {
        registryType: 'npm',
        identifier: '@tools-mcp/vessel-traffic-mcp',
        version: serverVersion,
        transport: { type: 'stdio' },
      },
    ],
    capabilities: {
      tools: true,
      resources: false,
      prompts: false,
    },
    tools: vesselMcpToolCards.map((tool) => ({
      name: tool.name,
      title: tool.title,
      description: tool.description,
      inputSchema: tool.inputSchema ? z.toJSONSchema(tool.inputSchema) : emptyObjectJsonSchema(),
      annotations: readOnlyAnnotations,
    })),
    resources: [],
    prompts: [],
    provenance: {
      requiresSourceAttribution: true,
      sourceFields: ['source.provider', 'source.landingUrl'],
      note:
        'Live and public-provider responses are designed to expose upstream source metadata so users can verify and visit the original service.',
    },
    tags: [
      'mcp',
      'model-context-protocol',
      'vessel-ais',
      'ship-tracking',
      'maritime',
      'ais',
      'byok',
      'claude',
      'chatgpt',
      'codex',
      'gemini',
      'vessel-ais-mcp',
      'chatgpt-mcp',
      'claude-mcp',
      'gemini-mcp',
    ],
  };
}

function emptyObjectJsonSchema(): Record<string, unknown> {
  return {
    $schema: 'https://json-schema.org/draft/2020-12/schema',
    type: 'object',
    properties: {},
    additionalProperties: false,
  };
}
