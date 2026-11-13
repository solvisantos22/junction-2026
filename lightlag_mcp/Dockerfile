# The simulator as a sidecar service. NOT YET BUILT OR RUN: Docker was not available
# when this was written. Build from the repository root:
#
#   docker build -f lightlag_mcp/Dockerfile -t lightlag-mcp .
#   docker run --rm -p 8000:8000 -e LIGHTLAG_SEED=7 -e LIGHTLAG_DELAY=3 lightlag-mcp
#
# The seed, the evaluator token and the artifact directory belong to whoever runs
# this container. None of them must be visible from the agent's container.
FROM python:3.12-slim

WORKDIR /srv
COPY lightlag_mcp/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY lightlag/ lightlag/
COPY lightlag_mcp/ lightlag_mcp/

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
# 0.0.0.0 so other containers can reach it by service name. Bound to 127.0.0.1 the
# server rejects requests addressed to any other host name.
CMD ["python", "-m", "lightlag_mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
