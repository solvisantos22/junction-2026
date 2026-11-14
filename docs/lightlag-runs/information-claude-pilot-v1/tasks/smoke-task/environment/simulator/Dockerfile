FROM python:3.12-slim
WORKDIR /srv
RUN pip install --no-cache-dir "mcp==2.3.0"
COPY lightlag_information/ lightlag_information/
COPY finish.py finish.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
CMD ["python", "-m", "lightlag_information.serve", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
