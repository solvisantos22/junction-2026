# The agent's container. It holds no simulator code and no episode secrets: the
# rover is reachable only through the `lightlag` MCP service in the other container.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# An MCP client library, so scripts (and the reference run) can call the tools.
RUN pip install --no-cache-dir "mcp==2.3.0"

WORKDIR /app
