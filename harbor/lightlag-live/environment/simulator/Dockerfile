# The simulator's container: one Lightlag Live campaign served over MCP.
# The packages here are copies made by lightlag_live/make_task.py.
FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY lightlag/ lightlag/
COPY lightlag_dynamic/ lightlag_dynamic/
COPY lightlag_live/ lightlag_live/

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
# 0.0.0.0 so the agent's container can reach it by service name.
CMD ["python", "-m", "lightlag_live", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
