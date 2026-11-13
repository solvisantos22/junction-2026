# The simulator's container: one Lightlag episode served over MCP.
# lightlag/ and lightlag_mcp/ here are copies made by harbor/sync_task.py.
FROM python:3.12-slim

WORKDIR /srv
COPY lightlag_mcp/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY lightlag/ lightlag/
COPY lightlag_mcp/ lightlag_mcp/

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
# 0.0.0.0 so the agent's container can reach it by service name.
CMD ["python", "-m", "lightlag_mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
