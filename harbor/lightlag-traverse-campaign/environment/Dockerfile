# The agent's container. It holds no simulator and no mission secrets: the rover is
# reachable only through the `lightlag` MCP service in the other container.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# An MCP client library and a small helper, so a program can call the five tools.
RUN pip install --no-cache-dir "mcp==2.3.0"

WORKDIR /app
COPY lightlag_client.py /app/lightlag_client.py
# The published ground model as code: how height, slope and a drive are computed.
COPY lightlag_surface.py /app/lightlag_surface.py
# Starts a long-running program outside the reach of the shell tool's time limit.
COPY detach.py /app/detach.py
