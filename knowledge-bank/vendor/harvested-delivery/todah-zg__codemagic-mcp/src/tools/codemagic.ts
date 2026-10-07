import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { listApplications, listTeams, listBuilds, getBuild, triggerBuild, cancelBuild, listWorkflows, addApplication, waitForBuild, listVariableGroups, listVariables, createVariableGroup, addVariable, updateVariable, deleteVariable, getWebhookUrl, listWebhooks, deleteWebhook, getBuildActions, getStepLog, TERMINAL_STATUSES, listCaches, deleteCache, createPublicArtifactUrl, type BuildsResult } from "../codemagic.js";
import { generateSSHKeyPair, parseGitHubRepo, addGitHubDeployKey, manualGenericInstructions } from "../ssh.js";
export function registerCodemagicTools(server: McpServer, apiToken: string, version: string): void {

  server.registerTool("ping", {
    description: "Check that the server is alive and return its version",
  }, async () => {
    return {
      content: [{ type: "text", text: `Codemagic MCP server is running. Version: ${version}` }],
    };
  });

  server.registerTool("list_applications", {
    description: "List all applications in your Codemagic account. Call this first to get the app IDs needed by all other Codemagic tools.",
    inputSchema: {
      team_id: z.string().optional().describe("Team ID to list apps for. If omitted, lists apps for the authenticated user."),
    },
  }, async ({ team_id }) => {
    const apps = await listApplications(apiToken, team_id);
    const text = apps.map(app => `${app.name} (${app.id})`).join("\n");
    return {
      content: [{ type: "text", text }],
    };
  });

  server.registerTool("list_teams", {
    description: "List teams the authenticated Codemagic account belongs to. Use the team IDs returned here with list_applications, list_builds, and other tools that accept an optional team_id.",
    inputSchema: {},
  }, async () => {
    const teams = await listTeams(apiToken);
    if (!teams.length) return {
      content: [{ type: "text", text: "No teams found. The token belongs to a personal account only." }],
    };
    const text = teams.map(t => `${t.name} — ID: ${t.id}`).join("\n");
    return { content: [{ type: "text", text }] };
  });

  server.registerTool("list_workflows", {
    description: "List workflows for an application. Returns workflow names and IDs — use the ID in trigger_build to run a specific workflow. Note: yaml-defined workflows only appear after their first build has run.",
    inputSchema: {
      app_id: z.string().describe("The application ID"),
    },
  }, async ({ app_id }) => {
    const workflows = await listWorkflows(apiToken, app_id);
    const text = workflows.map(w => `${w.name} (${w.id})`).join("\n");
    return {
      content: [{ type: "text", text: text || "No workflows found." }],
    };
  });

  server.registerTool("list_builds", {
    description: "List builds for a team with optional filters. Returns build IDs and status. Use get_build with a build ID to retrieve full details and artifact download URLs.",
    inputSchema: {
      team_id: z.string().describe("The team ID to list builds for"),
      app_id: z.string().optional().describe("Filter by Application ID"),
      status: z.enum(["queued", "building", "finished", "failed", "canceled", "timeout", "skipped"]).optional().describe("Filter by build status"),
      branch: z.string().optional().describe("Filter by git branch"),
      workflow_id: z.string().optional().describe("Filter by workflow ID"),
      limit: z.number().int().min(1).max(500).default(50).optional().describe("Maximum number of builds to return (default 50, max 500). Use filters to narrow results instead of raising this."),
    },
  }, async ({ team_id, app_id, status, branch, workflow_id, limit = 50 }) => {
    const { builds, hasMore } = await listBuilds(apiToken, team_id, { app_id, status, branch, workflow_id }, limit);
    const lines = builds.map(b => `#${b.index} ${b.status} - ${b.branch ?? b.tag ?? "no branch"} (${b.id})`);
    if (hasMore) {
      lines.push(`\n(showing first ${builds.length} builds — use filters or increase limit to narrow results)`);
    }
    return {
      content: [{ type: "text", text: lines.join("\n") || "No builds found." }],
    };
  });

  server.registerTool("get_build", {
    description: "Get full details for a single build including artifact download URLs. The build ID comes from trigger_build or list_builds. Artifact URLs require x-auth-token — use them with upload_to_testflight, upload_to_google_play, or create_public_artifact_url.",
    inputSchema: {
      build_id: z.string().describe("The build ID"),
    },
  }, async ({ build_id }) => {
    const build = await getBuild(apiToken, build_id);
    const artifactLines = build.artifacts.map(a =>
      ` - ${a.name} (${a.type}, ${a.size_in_bytes} bytes)\n   ${a.url}`
    ).join("\n");
    const text = [
      `Build #${build.index} - ${build.status}`,
      `Branch: ${build.branch ?? build.tag ?? "none"}`,
      `Created: ${build.created_at}`,
      `Started: ${build.started_at ?? "not started"}`,
      `Finished: ${build.finished_at ?? "not finished"}`,
      `Artifacts:\n${artifactLines || "  none"}`,
    ].join("\n");
    return {
      content: [{ type: "text", text }],
    };
  });

  server.registerTool("trigger_build", {
    description: "Trigger a new build on Codemagic. For release builds: determine BUILD_NUMBER first using list_asc_builds (iOS) or list_google_play_tracks (Android), then pass it in the variables parameter. Use yaml_content to supply an inline codemagic.yaml — get a starter template from get_yaml_template and validate it with validate_codemagic_yaml before triggering. Call wait_for_build with the returned build ID to wait for completion and retrieve artifact URLs.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      app_id: z.string().describe("The application ID"),
      workflow_id: z.string().describe("The workflow ID to run"),
      branch: z.string().optional().describe("Git branch to build"),
      tag: z.string().optional().describe("Git tag to build"),
      variables: z.record(z.string(), z.string()).optional().describe("Environment variables to inject into the build"),
      groups: z.array(z.string()).optional().describe("Environment variable groups to include"),
      labels: z.array(z.string()).optional().describe("Labels to attach to the build"),
      yaml_content: z.string().optional().describe("A codemagic.yaml file content to use for this build. When provided, the yaml is passed inline and does not need to exist in the repository."),
      instance_type: z.string().optional().describe(
        "Override the instance type for this build. Common values: mac_mini_m2, mac_mini_m4, linux_x2, linux_x4, windows_x2. Must be available on your billing plan. If omitted, the instance type from codemagic.yaml is used. IMPORTANT: Personal accounts (no team) can only use mac_mini_m2 — linux_x2, linux_x4, and mac_mini_m4 are not available on personal accounts."
      ),
    },
  }, async ({ app_id, workflow_id, branch, tag, variables, groups, labels, yaml_content, instance_type }) => {
    if (!branch && !tag) {
      return {
        content: [{ type: "text", text: "Error: either branch or tag must be provided." }],
        isError: true,
      };
    }
    const buildId = await triggerBuild(apiToken, {
      appId: app_id,
      workflowId: workflow_id,
      branch,
      tag,
      environment: { variables, groups },
      labels: labels ?? [],
      instanceType: instance_type,
    }, yaml_content);
    const buildUrl = `https://codemagic.io/app/${app_id}/build/${buildId}`;
    return {
      content: [{ type: "text", text: `Build triggered. Build ID: ${buildId}\n${buildUrl}` }],
    };
  });

  server.registerTool("wait_for_build", {
    description:
      "Check the current status of a Codemagic build. Returns immediately — no polling loop. " +
      "If the build has not finished, call this tool again with the same build_id. " +
      "A Codemagic build takes 10–40 minutes; calling this 20+ times is normal and expected. " +
      "Returns full build details and artifact download URLs once a terminal state is reached.",
    inputSchema: {
      build_id: z.string().describe("The Codemagic build ID to check"),
    },
  }, async ({ build_id }) => {
    const build = await waitForBuild(apiToken, build_id);

    if (!TERMINAL_STATUSES.has(build.status)) {
      return {
        content: [{ type: "text", text: `Build #${build.index} is still "${build.status}". Call wait_for_build again with the same build_id to continue polling.` }],
      };
    }

    const artifactLines = build.artifacts.map(a =>
      `  - ${a.name} (${a.type})\n    ${a.url}`
    ).join("\n");
    const text = [
      `Build #${build.index} — ${build.status}`,
      `Branch: ${build.branch ?? build.tag ?? "none"}`,
      `Finished: ${build.finished_at ?? "unknown"}`,
      `Artifacts:\n${artifactLines || "  none"}`,
    ].join("\n");
    return {
      content: [{ type: "text", text }],
      // Non-finished terminal states (failed, canceled, timeout, skipped) are surfaced as
      // tool errors so the agent's call chain fails fast rather than proceeding with a bad build.
      isError: build.status !== "finished",
    };
  });

  server.registerTool("cancel_build", {
    description: "Cancel a running or queued Codemagic build. Use when a triggered build is no longer needed — for example if the wrong branch was used or an error was found after triggering. Has no effect on builds that have already finished.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: true,
    },
    inputSchema: {
      build_id: z.string().describe("The Codemagic build ID to cancel (from trigger_build or list_builds)"),
    },
  }, async ({ build_id }) => {
    await cancelBuild(apiToken, build_id);
    return {
      content: [{ type: "text", text: `Build ${build_id} cancelled.` }],
    };
  });

  server.registerTool("add_application", {
    description:
      "Add a new application to Codemagic by connecting a Git repository. " +
      "For HTTPS URLs: if you have connected your GitHub, GitLab, or Bitbucket account via Codemagic Settings → Integrations, private repositories are accessible with just the URL — no credentials needed. " +
      "For SSH URLs (git@... or ssh://git@...): a fresh Ed25519 deploy key is generated automatically. The private key is stored directly in Codemagic and the public key is added to GitHub automatically if the gh CLI is installed and authenticated, or shown for manual setup otherwise. " +
      "Note: after adding, the app shows 'Set up build' in the Codemagic UI — this is expected.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      repository_url: z.string().describe("SSH or HTTPS URL of the Git repository"),
      team_id: z.string().optional().describe("Team ID to add the app to"),
    },
  }, async ({ repository_url, team_id }) => {
    const isSSH = repository_url.startsWith("git@") || repository_url.startsWith("ssh://git@");

    if (!isSSH) {
      const app = await addApplication(apiToken, repository_url, team_id);
      return {
        content: [{ type: "text", text: `Application added: ${app.appName} (${app.id})` }],
      };
    }

    // SSH URL — generate a deploy key, send the private key to Codemagic, expose the public key
    const keyPair = await generateSSHKeyPair();
    const sshKeyData = Buffer.from(keyPair.privateKey).toString("base64");
    const app = await addApplication(apiToken, repository_url, team_id, {
      data: sshKeyData,
      passphrase: null,
    });

    const lines: string[] = [`Application added: ${app.appName} (${app.id})`, ""];

    const githubRepo = parseGitHubRepo(repository_url);
    if (githubRepo) {
      const result = await addGitHubDeployKey(githubRepo.owner, githubRepo.repo, keyPair.publicKey);
      lines.push(result.message);
      if (!result.added) {
        lines.push("", "Once the deploy key is in place, Codemagic can clone the repository during builds.");
      }
    } else {
      lines.push(manualGenericInstructions(keyPair.publicKey));
      lines.push("", "Once the deploy key is in place, Codemagic can clone the repository during builds.");
    }

    return {
      content: [{ type: "text", text: lines.join("\n") }],
    };
  });

  server.registerTool("list_variable_groups", {
    description: "List variable groups for a team or app in Codemagic. Use group names to reference them in trigger_build. Secret values are never returned — manage secrets directly in the Codemagic UI.",
    inputSchema: {
      team_id: z.string().optional().describe("Team ID to list groups for"),
      app_id: z.string().optional().describe("App ID to list groups for"),
    },
  }, async ({ team_id, app_id }) => {
    if (!team_id && !app_id) {
      return {
        content: [{ type: "text", text: "Error: either team_id or app_id must be provided." }],
        isError: true,
      };
    }
    const groups = await listVariableGroups(apiToken, team_id, app_id);
    const text = groups.map(g => `${g.name} (${g.id})`).join("\n");
    return {
      content: [{ type: "text", text: text || "No variable groups found." }],
    };
  });

  server.registerTool("list_variables", {
    description: "List variables in a Codemagic variable group. Returns variable IDs, names, and values. Secret variable values are returned as null — only non-secret values are visible. Use the variable IDs with update_variable and delete_variable.",
    annotations: { readOnlyHint: true },
    inputSchema: {
      group_id: z.string().describe("The variable group ID (from list_variable_groups)"),
    },
  }, async ({ group_id }) => {
    const variables = await listVariables(apiToken, group_id);
    if (!variables.length) return {
      content: [{ type: "text", text: "No variables found in this group." }],
    };
    const text = variables.map(v =>
      `${v.name} = ${v.secure ? "(secret)" : v.value ?? "(empty)"}  [id: ${v.id}]`
    ).join("\n");
    return { content: [{ type: "text", text }] };
  });

  server.registerTool("create_variable_group", {
    description: "Create a new variable group in Codemagic. Requires a team_id (personal accounts do not support global variable groups) or an app_id for app-level groups. After creating, add non-secret variables via add_variable, or add secret values directly in the Codemagic UI.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      name: z.string().describe("Name of the variable group"),
      team_id: z.string().optional().describe("Team ID to create the group under"),
      app_id: z.string().optional().describe("App ID to create the group under"),
    },
  }, async ({ name, team_id, app_id }) => {
    if (!team_id && !app_id) {
      return {
        content: [{ type: "text", text: "Error: either team_id or app_id must be provided." }],
        isError: true,
      };
    }
    const group = await createVariableGroup(apiToken, name, team_id, app_id);
    return {
      content: [{ type: "text", text: `Variable group created: ${group.name} (${group.id})` }],
    };
  });

  server.registerTool("add_variable", {
    description: "Add a non-secret variable to a Codemagic variable group. For secret values (API keys, certificates, tokens) use the Codemagic UI instead — secrets should never pass through the agent.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      group_id: z.string().describe("The variable group ID to add the variable to"),
      name: z.string().describe("Variable name, e.g. FLUTTER_VERSION"),
      value: z.string().describe("Variable value"),
    },
  }, async ({ group_id, name, value }) => {
    await addVariable(apiToken, group_id, name, value);
    return {
      content: [{ type: "text", text: `Variable ${name} added to group ${group_id}.` }],
    };
  });

  server.registerTool("update_variable", {
    description: "Update the name or value of an existing non-secret variable in a Codemagic variable group. The variable_id comes from list_variable_groups. For secret values use the Codemagic UI — secrets should never pass through the agent.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      group_id: z.string().describe("The variable group ID"),
      variable_id: z.string().describe("The variable ID to update (from list_variable_groups)"),
      name: z.string().describe("New variable name"),
      value: z.string().describe("New variable value"),
    },
  }, async ({ group_id, variable_id, name, value }) => {
    await updateVariable(apiToken, group_id, variable_id, name, value);
    return {
      content: [{ type: "text", text: `Variable ${variable_id} updated.` }],
    };
  });

  server.registerTool("delete_variable", {
    description: "Delete a variable from a Codemagic variable group. The variable_id comes from list_variable_groups. This cannot be undone.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: true,
    },
    inputSchema: {
      group_id: z.string().describe("The variable group ID"),
      variable_id: z.string().describe("The variable ID to delete (from list_variable_groups)"),
    },
  }, async ({ group_id, variable_id }) => {
    await deleteVariable(apiToken, group_id, variable_id);
    return {
      content: [{ type: "text", text: `Variable ${variable_id} deleted.` }],
    };
  });

  server.registerTool("get_webhook_url", {
    description: "Get the incoming webhook URL for a Codemagic app. Paste this URL into your Git provider (GitHub, GitLab, or Bitbucket) repository settings to trigger builds automatically on push or pull request events.",
    annotations: { readOnlyHint: true },
    inputSchema: {
      app_id: z.string().describe("The Codemagic app ID"),
    },
  }, async ({ app_id }) => {
    const url = getWebhookUrl(app_id);
    return {
      content: [{ type: "text", text: `Webhook URL for app ${app_id}:\n${url}\n\nAdd this URL to your Git provider's repository webhook settings. Set the content type to application/json and select the push and pull request events you want to trigger builds.` }],
    };
  });

  server.registerTool("list_webhooks", {
    description: "List webhook subscriptions configured for a Codemagic app",
    annotations: { readOnlyHint: true },
    inputSchema: {
      app_id: z.string().describe("The Codemagic app ID"),
    },
  }, async ({ app_id }) => {
    const webhooks = await listWebhooks(apiToken, app_id);
    if (webhooks.length === 0) {
      return { content: [{ type: "text", text: "No webhooks configured for this app." }] };
    }
    return { content: [{ type: "text", text: JSON.stringify(webhooks, null, 2) }] };
  });

  server.registerTool("delete_webhook", {
    description: "Delete a webhook subscription from a Codemagic app",
    annotations: { destructiveHint: true },
    inputSchema: {
      app_id: z.string().describe("The Codemagic app ID"),
      webhook_id: z.string().describe("The webhook ID to delete (from list_webhooks)"),
    },
  }, async ({ app_id, webhook_id }) => {
    await deleteWebhook(apiToken, app_id, webhook_id);
    return { content: [{ type: "text", text: `Webhook ${webhook_id} deleted.` }] };
  });

  server.registerTool("list_caches", {
    description: "List build caches for a Codemagic app. Each cache is scoped to a workflow. Use the cache IDs with delete_cache to free up storage or force a clean build.",
    annotations: { readOnlyHint: true },
    inputSchema: {
      app_id: z.string().describe("The Codemagic app ID"),
    },
  }, async ({ app_id }) => {
    const caches = await listCaches(apiToken, app_id);
    if (!caches.length) return {
      content: [{ type: "text", text: "No caches found for this app." }],
    };
    const text = caches.map(c =>
      `${c.workflowId} — ${(c.size / 1024 / 1024).toFixed(1)} MB, last used ${c.lastUsed}  [id: ${c.id}]`
    ).join("\n");
    return { content: [{ type: "text", text }] };
  });
  
  server.registerTool("delete_cache", {
    description: "Delete a build cache for a Codemagic app. If cache_id is provided, deletes that specific workflow cache. If omitted, deletes all caches for the app. Deletion is asynchronous — the API returns immediately and completes in the background.",
    annotations: { readOnlyHint: false, destructiveHint: true },
    inputSchema: {
      app_id: z.string().describe("The Codemagic app ID"),
      cache_id: z.string().optional().describe("Specific cache ID to delete (from list_caches). If omitted, all caches are deleted."),
    },
  }, async ({ app_id, cache_id }) => {
    const deleted = await deleteCache(apiToken, app_id, cache_id);
    const target = cache_id ? `cache ${cache_id}` : `all caches`;
    return {
      content: [{ type: "text", text: `Deletion started for ${target}. IDs queued: ${deleted.join(", ")}` }],
    };
  });

  server.registerTool("create_public_artifact_url", {
    description:
      "Create a time-limited public download URL for a build artifact. " +
      "Pass the artifact URL from get_build or wait_for_build. " +
      "The returned URL is accessible without authentication — anyone with the link can download the artifact. " +
      "Use for sharing IPAs or AABs with testers who don't have Codemagic access.",
    annotations: { readOnlyHint: false, destructiveHint: false },
    inputSchema: {
      artifact_url: z.string().describe("The artifact url from a build artifact (returned by get_build or wait_for_build)"),
      expires_in_hours: z.number().min(1).optional().describe("How many hours until the public URL expires (default: 24, max: practical limit is a few days)"),
    },
  }, async ({ artifact_url, expires_in_hours = 24 }) => {
    const expiresAt = Math.floor(Date.now() / 1000) + expires_in_hours * 3600;
    const result = await createPublicArtifactUrl(apiToken, artifact_url, expiresAt);
    return {
      content: [{ type: "text", text: `Public URL (expires ${result.expiresAt}):\n${result.url}` }],
    };
  });

  server.registerTool("get_build_logs", {
    description: "Fetch logs for a Codemagic build. By default returns logs for failed steps only — the primary use case is diagnosing why a build failed. Pass step_name to fetch logs for a specific step regardless of status (e.g. 'building_ios', 'testing', 'publishing'). Always returns the step list with statuses first.",
    annotations: { readOnlyHint: true },
    inputSchema: {
      build_id: z.string().describe("The Codemagic build ID"),
      step_name: z.string().optional().describe("Fetch logs for this specific step name only. If omitted, logs are fetched for failed steps (or none if the build succeeded)."),
    },
  }, async ({ build_id, step_name }) => {
    const actions = await getBuildActions(apiToken, build_id);
  
    const stepList = actions.map(a =>
      `  [${a.status ?? "pending"}] ${a.name} (${a.type})`
    ).join("\n");
  
    const toFetch = step_name
      ? actions.filter(a => a.name === step_name || a.type === step_name)
      : actions.filter(a => a.status === "failed");
  
    if (toFetch.length === 0) {
      return {
        content: [{ type: "text", text: `Steps:\n${stepList}\n\nNo logs to fetch.` }],
      };
    }
  
    const MAX_LOG_CHARS = 20_000;
    const logSections = await Promise.all(
      toFetch.map(async (a) => {
        const raw = await getStepLog(apiToken, build_id, a.id);
        const truncated = raw.length > MAX_LOG_CHARS
          ? raw.slice(-MAX_LOG_CHARS) + `\n[truncated — showing last ${MAX_LOG_CHARS} chars of ${raw.length}]`
          : raw;
        return `=== ${a.name} (${a.status ?? "pending"}) ===\n${truncated}`;
      })
    );
  
    return {
      content: [{ type: "text", text: `Steps:\n${stepList}\n\n${logSections.join("\n\n")}` }],
    };
  });



}