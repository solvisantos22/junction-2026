# The agent's container. It holds no simulator code and no campaign secrets: the
# rover is reachable only through the `lightlag` MCP service in the other container.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# An MCP client library and a small helper, so a program can call the five tools.
RUN pip install --no-cache-dir "mcp==2.3.0"

WORKDIR /app
COPY lightlag_client.py /app/lightlag_client.py
# Starts the agent's program outside the reach of its shell tool's time limit.
COPY detach.py /app/detach.py
