FROM python:3.12-slim

WORKDIR /app

# Install the package (and its single runtime dep, the MCP SDK).
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

# MCP server speaks over stdio.
ENTRYPOINT ["mcp-architect"]
