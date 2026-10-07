import { DisruptionApiClient } from "./client.js";
type JsonObject = Record<string, unknown>;
export type McpToolAnnotations = {
    readOnlyHint: boolean;
    destructiveHint: boolean;
    idempotentHint: boolean;
    openWorldHint: boolean;
};
export type McpTool = {
    name: string;
    description: string;
    inputSchema: JsonObject;
    annotations: McpToolAnnotations;
};
export declare const tools: McpTool[];
export declare function callTool(name: string, args?: JsonObject, client?: DisruptionApiClient): Promise<unknown>;
export {};
