import { Agent, MCPServerStreamableHttp, run } from "@openai/agents";
import { OpenAI } from "openai";
import dotenv from "dotenv";

/* load environment variables */
dotenv.config();
const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

/* mcp server definition */
const mcpServer = new MCPServerStreamableHttp({
    url: 'http://localhost:9010/mcp',
    name: 'GIS MCP server'
});

/* agent definition */
const gisAgent = new Agent({
    client,
    name: 'GIS Agent',
    instructions: 'You must always use the MCP tools to answer GIS questions.',
    mcpServers: [mcpServer]
});

/* Perform a query */
await mcpServer.connect();

const result = await run(
    gisAgent,
    "Calculate distance between points (0,0) and (1,1)",
);

await mcpServer.close();

console.log(result.finalOutput);
