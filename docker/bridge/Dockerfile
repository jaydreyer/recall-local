FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts ./scripts
COPY prompts ./prompts
COPY config ./config

EXPOSE 8090

CMD ["python3", "scripts/phase1/ingest_bridge_api.py", "--host", "0.0.0.0", "--port", "8090"]
