# GEMINI.md

## Project Overview

This project is a TypeScript-based MCP (Model Context Protocol) server named `mcp-trinv-server`. It is designed to augment AI assistants like Gemini and Claude with tools to interact with the TRINV service. The server provides functionalities to search for French communes by name fragments and to find cadastral parcels within a commune based on their surface area.

The core logic is implemented in `src/index.ts`. It uses the `@modelcontextprotocol/sdk` for creating the MCP server and `zod` for schema validation. The server exposes two main tools: `trinv-chercher-commune` and `trinv-chercher-parcelle`. These tools make REST API calls to the TRINV API (`https://trinv.fr/api/...`) to fetch the required data.

The project is configured to be built from the `src` directory into the `dist` directory, as specified in `tsconfig.json`. The `package.json` file defines the project's dependencies, scripts, and metadata.

## Building and Running

### Building the project

To build the project, run the following command:

```bash
npm run build
```

This command executes `tsc` to compile the TypeScript code from `src` to JavaScript in `dist` and then makes the main script executable.

### Running the server

The server is intended to be run as a command-line tool. Once built, it can be started with:

```bash
./dist/index.js
```

Alternatively, during development, you can run the compiled output directly:

```bash
node dist/index.js
```

The server uses a stdio transport layer to communicate with the AI assistant.

## Development Conventions

*   **Language:** TypeScript
*   **Code Style:** The code follows standard TypeScript conventions. It uses `async/await` for asynchronous operations and defines types for the data structures exchanged with the TRINV API.
*   **Dependencies:** Project dependencies are managed with `npm`. Key dependencies include `@modelcontextprotocol/sdk` and `zod`. Development dependencies include `typescript`, `@types/node`, and `@google/gemini-cli`.
*   **Modularity:** The server is organized into a single main file (`src/index.ts`) that defines the server and its tools.
*   **API Interaction:** The server interacts with the TRINV API using `fetch`. The API endpoints are `https://trinv.fr/api/countybyfragment.json` and `https://trinv.fr/api/areas.json`.
*   **Error Handling:** Basic error handling is in place, with errors being thrown for failed API requests or ambiguous inputs.
*   **Caching:** The server implements a simple in-memory cache using `Map` objects to store results from the `trinv-chercher-commune` tool, which are then used by the `trinv-chercher-parcelle` tool.
