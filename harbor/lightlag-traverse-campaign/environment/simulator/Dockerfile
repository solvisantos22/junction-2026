# The simulator's container: a Lightlag Traverse campaign served over MCP, one mission
# after another; the missions' seeds come from LIGHTLAG_SEEDS (docker-compose.yaml).
# The packages here are copies made by lightlag_traverse/make_task.py.
FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY lightlag/ lightlag/
COPY lightlag_mcp/ lightlag_mcp/
COPY lightlag_traverse/ lightlag_traverse/

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
# 0.0.0.0 so the agent's container can reach it by service name.
CMD ["python", "-m", "lightlag_traverse.server", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
