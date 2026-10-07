import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { validateCodemagicYaml, getYamlTemplate, listYamlTemplateTypes } from "../yaml.js";
import { detectProjectType } from "../detection.js";


export function registerYamlTools(server: McpServer): void {

  server.registerTool("validate_codemagic_yaml", {
    description: "Validate a codemagic.yaml file against the official Codemagic JSON schema",
    inputSchema: {
      yaml_content: z.string().describe("The full contents of a codemagic.yaml file"),
    },
  }, async ({ yaml_content }) => {
    const result = await validateCodemagicYaml(yaml_content);
    if (result.valid) {
      return {
        content: [{ type: "text", text: "Valid codemagic.yaml — no errors found." }],
      };
    }
    const text = `Invalid codemagic.yaml — ${result.errors.length} error(s):\n${result.errors.map(e => `  - ${e}`).join("\n")}`;
    return {
      content: [{ type: "text", text }],
      isError: true,
    };
  });

  server.registerTool("get_yaml_template", {
    description: "Get a starter codemagic.yaml template for a given project type. Templates cover build and signing only — publishing is handled separately via App Store Connect tools. Call list_yaml_template_types to see all valid project_type values. IMPORTANT: Android templates use linux_x2 by default (cheaper, no Mac needed). Personal accounts (no team) cannot use linux_x2 — replace it with mac_mini_m2 for personal accounts.",
    inputSchema: {
      project_type: z.string()
        .refine(
          v => listYamlTemplateTypes().includes(v),
          v => ({ message: `Unknown project_type "${v}". Valid types: ${listYamlTemplateTypes().join(", ")}` }),
        )
        .describe("The project type to get a template for. Call list_yaml_template_types for all valid values."),
    },
  }, async ({ project_type }) => {
    const template = getYamlTemplate(project_type);
    if (!template) {
      return {
        content: [{ type: "text", text: `No template found for project type: ${project_type}` }],
        isError: true,
      };
    }
    return {
      content: [{ type: "text", text: template }],
    };
  });

  server.registerTool("list_yaml_template_types", {
    description: "List all available codemagic.yaml template types",
  }, async () => {
    const types = listYamlTemplateTypes();
    return {
      content: [{ type: "text", text: types.join("\n") }],
    };
  });

  server.registerTool("detect_project_type", {
    description: "Detect the Codemagic project type from a repository file listing. Returns the recommended template type, confidence level, and the suggested debug template to use for initial onboarding. For JavaScript/TypeScript projects, providing package.json content significantly improves accuracy.",
    annotations: { readOnlyHint: true },
    inputSchema: {
      file_paths: z.array(z.string()).describe("File paths in the repository relative to the root. Include at least two directory levels for best results."),
      package_json_content: z.string().optional().describe("Content of package.json if present — used to detect React Native vs Ionic by inspecting dependencies"),
    },
  }, async ({ file_paths, package_json_content }) => {
    const result = detectProjectType(file_paths, package_json_content);
    const lines = [
      `Detected project type: ${result.projectType}`,
      `Confidence: ${result.confidence}`,
      `Reasoning: ${result.reasoning}`,
    ];
    if (result.suggestedDebugTemplate) {
      lines.push(`\nSuggested first step: call get_yaml_template with project_type="${result.suggestedDebugTemplate}" for an initial debug build.`);
      lines.push(`Once that build passes, use project_type="${result.projectType}" for release builds.`);
    }
    return {
      content: [{ type: "text", text: lines.join("\n") }],
    };
  });

}
