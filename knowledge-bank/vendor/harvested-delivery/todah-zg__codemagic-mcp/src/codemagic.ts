import { z } from "zod";

const BASE_URL_V3 = "https://codemagic.io";
const BASE_URL_V1 = "https://api.codemagic.io";

const FETCH_TIMEOUT_MS = 10_000;

async function buildApiError(response: Response): Promise<Error> {
  const body = await response.text().catch(() => "");
  const detail = body ? ` — ${body.slice(0, 200)}` : "";
  return new Error(`Codemagic API error: ${response.status} ${response.statusText}${detail}`);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function parseOrThrow<T>(schema: z.ZodType<T, z.ZodTypeDef, any>, data: unknown, context: string): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    const issues = result.error.issues
      .map(i => `${i.path.join(".") || "(root)"}: ${i.message}`)
      .join("; ");
    throw new Error(`${context}: unexpected response shape — ${issues}`);
  }
  return result.data;
}

// Used by listBuilds (v3 API). Normalises short_lived_download_url → url so both
// list and detail paths expose the same Artifact shape.
const ArtifactSchema = z.object({
  name: z.string(),
  type: z.string(),
  size_in_bytes: z.number(),
  short_lived_download_url: z.string(),
  version_name: z.string().nullable(),
  version_code: z.string().nullable(),
}).transform(a => ({
  name: a.name,
  type: a.type,
  size_in_bytes: a.size_in_bytes,
  url: a.short_lived_download_url,
  version_name: a.version_name,
  version_code: a.version_code,
}));

// Used by getBuild (v1 API). Field names differ: artefacts (British), size, versionCode.
const V1ArtifactSchema = z.object({
  name: z.string(),
  type: z.string(),
  url: z.string(),
  size: z.number(),
  versionName: z.string().nullable().optional(),
  versionCode: z.string().nullable().optional(),
}).transform(a => ({
  name: a.name,
  type: a.type,
  url: a.url,
  size_in_bytes: a.size,
  version_name: a.versionName ?? null,
  version_code: a.versionCode ?? null,
}));

const V1BuildSchema = z.object({
  _id: z.string(),
  appId: z.string(),
  status: z.string(),
  index: z.number(),
  branch: z.string().nullable().optional(),
  tag: z.string().nullable().optional(),
  createdAt: z.string(),
  startedAt: z.string().nullable().optional(),
  finishedAt: z.string().nullable().optional(),
  artefacts: z.array(V1ArtifactSchema).default([]),
}).transform(b => ({
  id: b._id,
  app_id: b.appId,
  status: b.status,
  index: b.index,
  branch: b.branch ?? null,
  tag: b.tag ?? null,
  created_at: b.createdAt,
  started_at: b.startedAt ?? null,
  finished_at: b.finishedAt ?? null,
  artifacts: b.artefacts,
}));

const BuildSchema = z.object({
  id: z.string(),
  app_id: z.string(),
  status: z.string(),
  index: z.number(),
  branch: z.string().nullable(),
  tag: z.string().nullable(),
  created_at: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
  artifacts: z.array(ArtifactSchema),
});

const ApplicationSchema = z.object({
  id: z.string(),
  name: z.string(),
  icon_url: z.string().nullable(),
  last_build_id: z.string().nullable(),
  archived: z.boolean().nullable(),
});

const TeamSchema = z.object({
  id: z.string(),
  name: z.string(),
});

const VariableGroupSchema = z.object({
  id: z.string(),
  name: z.string(),
});

const VariableSchema = z.object({
  id: z.string(),
  name: z.string(),
  value: z.string().nullable(),
  secure: z.boolean(),
});

const CacheRawSchema = z.object({
  _id: z.string(),
  workflowId: z.string(),
  lastUsed: z.string(),
  size: z.number(),
});

const BuildActionSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: z.string(),
  status: z.string().nullable(),
});

const WebhookSchema = z.object({
  _id: z.string(),
  appId: z.string(),
  url: z.string(),
  events: z.array(z.string()),
  branchPatterns: z.array(z.string()).optional(),
});

/**
 * Fetch all pages of a page-numbered v3 list endpoint.
 * Uses page_size=100 to minimise round trips. Stops when current_page >= total_pages.
 */
async function fetchAllPages<T>(apiToken: string, url: string, itemSchema: z.ZodType<T>, extraParams = new URLSearchParams()): Promise<T[]> {
  const all: T[] = [];
  let page = 1;
  while (true) {
    const params = new URLSearchParams(extraParams);
    params.set("page", String(page));
    params.set("page_size", "100");
    const response = await fetch(`${url}?${params}`, {
      headers: { "x-auth-token": apiToken },
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    if (!response.ok) throw await buildApiError(response);
    const envelope = parseOrThrow(
      z.object({ data: z.array(z.unknown()), current_page: z.number(), total_pages: z.number() }),
      await response.json(),
      `fetchAllPages(${url})`,
    );
    const items = envelope.data.map(item => parseOrThrow(itemSchema, item, url));
    all.push(...items);
    if (envelope.current_page >= envelope.total_pages || items.length === 0) break;
    page++;
  }
  return all;
}

export interface Application {
  id: string;
  name: string;
  icon_url: string | null;
  last_build_id: string | null;
  archived: boolean | null;
}

/**
 * List applications in a Codemagic team or personal account.
 * @param apiToken - Codemagic API token from User settings → Integrations.
 * @param teamId - Optional team ID. If omitted, returns apps for the authenticated user.
 */
export async function listApplications(apiToken: string, teamId?: string): Promise<Application[]> {
  const url = teamId
    ? `${BASE_URL_V3}/api/v3/teams/${teamId}/apps`
    : `${BASE_URL_V3}/api/v3/user/apps`;
  return fetchAllPages(apiToken, url, ApplicationSchema);
}

export interface Team {
  id: string;
  name: string;
}

/**
 * List teams the authenticated user belongs to.
 * Use the returned team IDs with list_applications, list_builds, and other team-scoped tools.
 * @param apiToken - Codemagic API token.
 */
export async function listTeams(apiToken: string): Promise<Team[]> {
  return fetchAllPages(apiToken, `${BASE_URL_V3}/api/v3/user/teams`, TeamSchema);
}

export interface Artifact {
  name: string;
  type: string;
  size_in_bytes: number;
  /** Artifact download URL. From get_build/wait_for_build (v1 API): permanent, requires x-auth-token. From list_builds (v3 API): short-lived JWT, self-authenticating. */
  url: string;
  version_name: string | null;
  version_code: string | null;
}

export interface Build {
  id: string;
  app_id: string;
  status: string;
  index: number;
  branch: string | null;
  tag: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  artifacts: Artifact[];
}

export interface BuildsResult {
  builds: Build[];
  hasMore: boolean;
}

/**
 * List builds for a team, with optional filters and a result cap.
 * Uses cursor-based pagination — fetches pages of up to 100 until maxResults is reached
 * or no more pages exist. hasMore=true means results were truncated.
 * @param apiToken - Codemagic API token.
 * @param teamId - Team ID to list builds for.
 * @param filters - Optional filters for app, status, branch, or workflow.
 * @param maxResults - Maximum builds to return (default 50).
 */
export async function listBuilds(
  apiToken: string,
  teamId: string,
  filters?: { app_id?: string; status?: string; branch?: string; workflow_id?: string },
  maxResults = 50,
): Promise<BuildsResult> {
  const all: Build[] = [];
  let cursor: string | undefined;
  while (all.length < maxResults) {
    const params = new URLSearchParams();
    if (filters?.app_id) params.set("app_id", filters.app_id);
    if (filters?.status) params.set("status", filters.status);
    if (filters?.branch) params.set("branch", filters.branch);
    if (filters?.workflow_id) params.set("workflow_id", filters.workflow_id);
    params.set("page_size", String(Math.min(maxResults - all.length, 100)));
    if (cursor) params.set("cursor", cursor);
    const response = await fetch(`${BASE_URL_V3}/api/v3/teams/${teamId}/builds?${params}`, {
      headers: { "x-auth-token": apiToken },
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    if (!response.ok) throw await buildApiError(response);
    const data = parseOrThrow(
      z.object({ data: z.array(BuildSchema), cursor: z.string().nullish() }),
      await response.json(),
      "listBuilds",
    );
    all.push(...data.data);
    cursor = data.cursor ?? undefined;
    if (!cursor || data.data.length === 0) break;
  }
  return { builds: all, hasMore: !!cursor };
}

/**
 * Get full details for a single build, including its artifacts.
 * @param apiToken - Codemagic API token.
 * @param buildId - The build ID.
 */
export async function getBuild(apiToken: string, buildId: string): Promise<Build> {
  const response = await fetch(`${BASE_URL_V1}/builds/${buildId}`, {
    headers: { "x-auth-token": apiToken },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
  const { build } = parseOrThrow(z.object({ build: V1BuildSchema }), await response.json(), "getBuild");
  return build;
}

export interface TriggerBuildParams {
  appId: string;
  workflowId: string;
  branch?: string;
  tag?: string;
  environment?: {
    variables?: Record<string, string>;
    groups?: string[];
  };
  labels: string[];
  instanceType?: string;
}

/**
 * Trigger a new build on Codemagic.
 * Either `branch` or `tag` must be set in params.
 * @param apiToken - Codemagic API token.
 * @param params - Build parameters including app, workflow, branch/tag, and environment.
 * @param yamlContent - Optional inline codemagic.yaml. When provided, sent as a
 *   multipart form upload and overrides any yaml in the repository.
 * @returns The new build ID.
 */
export async function triggerBuild(
  apiToken: string,
  params: TriggerBuildParams,
  yamlContent?: string
): Promise<string> {
  let body: BodyInit;
  const headers: Record<string, string> = { "x-auth-token": apiToken };

  if (yamlContent) {
    const form = new FormData();
    form.append("data", JSON.stringify(params));
    form.append("config", new Blob([yamlContent], { type: "text/plain" }), "codemagic.yaml");
    body = form;
  } else {
    body = JSON.stringify(params);
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${BASE_URL_V1}/builds`, {
    method: "POST",
    headers,
    body,
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
  const { buildId } = parseOrThrow(z.object({ buildId: z.string() }), await response.json(), "triggerBuild");
  return buildId;
}

export interface Workflow {
  id: string;
  name: string;
}

/**
 * Cancel a running or queued build.
 * Has no effect on builds that have already reached a terminal state.
 * @param apiToken - Codemagic API token.
 * @param buildId - The build ID to cancel.
 */
export async function cancelBuild(apiToken: string, buildId: string): Promise<void> {
  const response = await fetch(`${BASE_URL_V1}/builds/${buildId}/cancel`, {
    method: "POST",
    headers: { "x-auth-token": apiToken },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
}


/**
 * List workflows defined for an application.
 * Note: workflows defined in codemagic.yaml only appear here after their first build has run.
 * @param apiToken - Codemagic API token.
 * @param appId - The application ID.
 */
export async function listWorkflows(apiToken: string, appId: string): Promise<Workflow[]> {
  const response = await fetch(`${BASE_URL_V1}/apps/${appId}`, {
    headers: { "x-auth-token": apiToken },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
  const { application } = parseOrThrow(
    z.object({ application: z.object({ workflows: z.record(z.string(), z.object({ name: z.string() })) }) }),
    await response.json(),
    "listWorkflows",
  );
  return Object.entries(application.workflows).map(([id, workflow]) => ({ id, name: workflow.name }));
}

/**
 * Connect a Git repository to Codemagic as a new application.
 * After adding, the app shows "Set up build" in the UI — this is expected.
 * Builds can still be triggered via API using workflow IDs from codemagic.yaml.
 * @param apiToken - Codemagic API token.
 * @param repositoryUrl - SSH or HTTPS URL of the Git repository.
 * @param teamId - Optional team to add the app to.
 * @param sshKey - Required for private repositories not accessible via HTTPS.
 */
export async function addApplication(
  apiToken: string,
  repositoryUrl: string,
  teamId?: string,
  sshKey?: { data: string; passphrase: string | null }
): Promise<{ id: string; appName: string }> {
  const endpoint = sshKey ? `${BASE_URL_V1}/apps/new` : `${BASE_URL_V1}/apps`;
  const body: Record<string, unknown> = { repositoryUrl };
  if (teamId) body.teamId = teamId;
  if (sshKey) body.sshKey = sshKey;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "x-auth-token": apiToken,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);

  const data = parseOrThrow(
    z.object({
      application: z.object({ _id: z.string(), appName: z.string() }).optional(),
      _id: z.string().optional(),
      appName: z.string().optional(),
    }),
    await response.json(),
    "addApplication",
  );
  const id = data.application?._id ?? data._id;
  const appName = data.application?.appName ?? data.appName;
  if (!id || !appName) {
    throw new Error(`add_application: unexpected response shape — ${JSON.stringify(data)}`);
  }
  return { id, appName };
}

/** Terminal build statuses — a build in one of these states will not progress further. */
export const TERMINAL_STATUSES = new Set(["finished", "failed", "canceled", "timeout", "skipped"]);

/**
 * Alias for getBuild — kept under this name for tool-surface continuity (the wait_for_build
 * tool calls it in a polling loop; the name signals intent at the call site).
 * Returns immediately; no polling loop.
 */
export async function waitForBuild(apiToken: string, buildId: string): Promise<Build> {
  return getBuild(apiToken, buildId);
}

export interface VariableGroup {
  id: string;
  name: string;
}

export interface Variable {
  id: string;
  name: string;
  value: string | null;
  secure: boolean;
}

/**
 * List variable groups for a team or app.
 * Secret variable values are not returned by the API — manage them in the Codemagic UI.
 * @param apiToken - Codemagic API token.
 * @param teamId - Team ID (mutually exclusive with appId).
 * @param appId - App ID for app-scoped groups (mutually exclusive with teamId).
 */
export async function listVariableGroups(apiToken: string, teamId?: string, appId?: string): Promise<VariableGroup[]> {
  const url = teamId
    ? `${BASE_URL_V3}/api/v3/teams/${teamId}/variable-groups`
    : `${BASE_URL_V3}/api/v3/apps/${appId}/variable-groups`;
  return fetchAllPages(apiToken, url, VariableGroupSchema);
}

/**
 * List variables in a variable group.
 * Secret variable values are returned as null — only non-secret values are visible.
 * The returned variable IDs are required for update_variable and delete_variable.
 * @param apiToken - Codemagic API token.
 * @param groupId - The variable group ID.
 */
export async function listVariables(apiToken: string, groupId: string): Promise<Variable[]> {
  return fetchAllPages(apiToken, `${BASE_URL_V3}/api/v3/variable-groups/${groupId}/variables`, VariableSchema);
}

/**
 * Create a new variable group for a team or app.
 * Team-level groups require advanced_security settings — this function defaults to disabled.
 * Personal accounts do not support team-level variable groups.
 * @param apiToken - Codemagic API token.
 * @param name - Name of the new group.
 * @param teamId - Team ID (mutually exclusive with appId).
 * @param appId - App ID for app-scoped groups (mutually exclusive with teamId).
 */
export async function createVariableGroup(
  apiToken: string,
  name: string,
  teamId?: string,
  appId?: string
): Promise<VariableGroup> {
  const path = teamId
    ? `/api/v3/teams/${teamId}/variable-groups`
    : `/api/v3/apps/${appId}/variable-groups`;
  const body: Record<string, unknown> = { name };
  if (teamId) {
    body.advanced_security = { enabled: false, selected_apps: [] };
  }
  const response = await fetch(`${BASE_URL_V3}${path}`, {
    method: "POST",
    headers: {
      "x-auth-token": apiToken,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
  const { data } = parseOrThrow(z.object({ data: VariableGroupSchema }), await response.json(), "createVariableGroup");
  return data;
}

/**
 * Add a non-secret variable to a variable group.
 * Variables are always created with secure: false. For secret values,
 * use the Codemagic UI — secrets should never pass through the agent.
 * @param apiToken - Codemagic API token.
 * @param groupId - The variable group ID.
 * @param name - Variable name, e.g. FLUTTER_VERSION.
 * @param value - Variable value.
 */
export async function addVariable(
  apiToken: string,
  groupId: string,
  name: string,
  value: string
): Promise<void> {
  const response = await fetch(`${BASE_URL_V3}/api/v3/variable-groups/${groupId}/variables`, {
    method: "POST",
    headers: {
      "x-auth-token": apiToken,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      secure: false,
      variables: [{ name, value }],
    }),
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
}

/**
 * Update an existing variable in a variable group.
 * Only non-secure variables should be updated via the agent — manage secret
 * values directly in the Codemagic UI.
 * @param apiToken - Codemagic API token.
 * @param groupId - The variable group ID.
 * @param variableId - The variable ID to update (from list_variable_groups).
 * @param name - New variable name.
 * @param value - New variable value.
 */
export async function updateVariable(
  apiToken: string,
  groupId: string,
  variableId: string,
  name: string,
  value: string
): Promise<void> {
  const response = await fetch(`${BASE_URL_V3}/api/v3/variable-groups/${groupId}/variables/${variableId}`, {
    method: "PATCH",
    headers: { "x-auth-token": apiToken, "Content-Type": "application/json" },
    body: JSON.stringify({ name, value, secure: false }),
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
}

/**
 * Delete a variable from a variable group.
 * @param apiToken - Codemagic API token.
 * @param groupId - The variable group ID.
 * @param variableId - The variable ID to delete (from list_variable_groups).
 */
export async function deleteVariable(
  apiToken: string,
  groupId: string,
  variableId: string
): Promise<void> {
  const response = await fetch(`${BASE_URL_V3}/api/v3/variable-groups/${groupId}/variables/${variableId}`, {
    method: "DELETE",
    headers: { "x-auth-token": apiToken },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
}

export interface Cache {
  id: string;
  workflowId: string;
  lastUsed: string;
  size: number;
}

/**
 * List all build caches for an application.
 * Uses the v1 API — not in the v3 OpenAPI schema.
 * @param apiToken - Codemagic API token.
 * @param appId - The Codemagic app ID.
 */
export async function listCaches(apiToken: string, appId: string): Promise<Cache[]> {
  const response = await fetch(`${BASE_URL_V1}/apps/${appId}/caches`, {
    headers: { "x-auth-token": apiToken },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
  const { caches } = parseOrThrow(z.object({ caches: z.array(CacheRawSchema) }), await response.json(), "listCaches");
  return caches.map(c => ({ id: c._id, workflowId: c.workflowId, lastUsed: c.lastUsed, size: c.size }));
}

/**
 * Delete one or all build caches for an application. Deletion is async — the
 * API returns 202 Accepted and completes in the background.
 * Uses the v1 API — not in the v3 OpenAPI schema.
 * @param apiToken - Codemagic API token.
 * @param appId - The Codemagic app ID.
 * @param cacheId - Specific cache ID to delete. If omitted, all caches are deleted.
 */
export async function deleteCache(apiToken: string, appId: string, cacheId?: string): Promise<string[]> {
  const url = cacheId
    ? `${BASE_URL_V1}/apps/${appId}/caches/${cacheId}`
    : `${BASE_URL_V1}/apps/${appId}/caches`;
  const response = await fetch(url, {
    method: "DELETE",
    headers: { "x-auth-token": apiToken },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
  const { caches } = parseOrThrow(z.object({ caches: z.array(z.string()) }), await response.json(), "deleteCache");
  return caches;
}

/**
 * Create a time-limited public download URL for a build artifact.
 * Expects a v1 artifact URL from getBuild() / waitForBuild() —
 * the form https://api.codemagic.io/artifacts/{uuid}/{uuid}/{filename}.
 * WARNING: public URLs are accessible without authentication — share carefully.
 * @param apiToken - Codemagic API token.
 * @param artifactUrl - The artifact url from a build artifact (returned by get_build or wait_for_build).
 * @param expiresAt - URL expiry as a Unix timestamp in seconds.
 * @returns The public download URL and its expiry datetime string.
 */
export async function createPublicArtifactUrl(
  apiToken: string,
  artifactUrl: string,
  expiresAt: number
): Promise<{ url: string; expiresAt: string }> {
  const prefix = `${BASE_URL_V1}/artifacts/`;
  if (!artifactUrl.startsWith(prefix)) {
    throw new Error(
      `Unexpected artifact URL format: ${artifactUrl}. ` +
      `Expected a URL from get_build or wait_for_build (https://api.codemagic.io/artifacts/…).`
    );
  }
  const artifactPath = artifactUrl.slice(prefix.length);
  const response = await fetch(`${prefix}${artifactPath}/public-url`, {
    method: "POST",
    headers: { "x-auth-token": apiToken, "Content-Type": "application/json" },
    body: JSON.stringify({ expiresAt }),
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
  return parseOrThrow(z.object({ url: z.string(), expiresAt: z.string() }), await response.json(), "createPublicArtifactUrl");
}

// ─── Webhooks ────────────────────────────────────────────────────────────────

export interface Webhook {
  _id: string;
  appId: string;
  url: string;
  events: string[];
  branchPatterns?: string[];
}

/**
 * Get the incoming webhook URL for a Codemagic app.
 * This is the URL you add to your Git provider (GitHub/GitLab/Bitbucket)
 * to trigger builds automatically on push or pull request events.
 * No API call is needed — the URL is derived from the app ID.
 * @param appId - The Codemagic app ID.
 * @returns The webhook URL to configure in the Git provider.
 */
export function getWebhookUrl(appId: string): string {
  return `https://api.codemagic.io/hooks/${appId}`;
}

/**
 * List all webhook subscriptions for a Codemagic app.
 * @param apiToken - Codemagic API token.
 * @param appId - The Codemagic app ID.
 */
export async function listWebhooks(apiToken: string, appId: string): Promise<Webhook[]> {
  const response = await fetch(`${BASE_URL_V1}/apps/${appId}/webhooks`, {
    headers: { "x-auth-token": apiToken },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
  return parseOrThrow(z.array(WebhookSchema), await response.json(), "listWebhooks");
}

/**
 * Delete a webhook subscription from a Codemagic app.
 * @param apiToken - Codemagic API token.
 * @param appId - The Codemagic app ID.
 * @param webhookId - The webhook ID to delete.
 */
export async function deleteWebhook(apiToken: string, appId: string, webhookId: string): Promise<void> {
  const response = await fetch(`${BASE_URL_V1}/apps/${appId}/webhooks/${webhookId}`, {
    method: "DELETE",
    headers: { "x-auth-token": apiToken },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
}

export interface BuildAction {
  id: string;
  name: string;
  type: string;
  status: string | null;
}

/**
 * List all build steps (actions) for a build, including their status and timing.
 * The returned IDs are used with getStepLog to fetch log text for individual steps.
 * Uses the v3 API — no log content is returned here, only metadata.
 * @param apiToken - Codemagic API token.
 * @param buildId - The build ID.
 */
export async function getBuildActions(apiToken: string, buildId: string): Promise<BuildAction[]> {
  return fetchAllPages(apiToken, `${BASE_URL_V3}/api/v3/builds/${buildId}/actions`, BuildActionSchema);
}

/**
 * Fetch the plain-text log for a single build step.
 * Uses the v1 API (api.codemagic.io) — this endpoint is not in the v3 OpenAPI schema
 * but accepts the same x-auth-token authentication.
 * @param apiToken - Codemagic API token.
 * @param buildId - The build ID.
 * @param stepId - The step ID from getBuildActions.
 */
export async function getStepLog(apiToken: string, buildId: string, stepId: string): Promise<string> {
  const response = await fetch(`${BASE_URL_V1}/builds/${buildId}/step/${stepId}`, {
    headers: { "x-auth-token": apiToken },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw await buildApiError(response);
  return response.text();
}