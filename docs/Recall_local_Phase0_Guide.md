# Recall.local — Phase 0 Implementation Guide

**Purpose:** Step-by-step setup guide for getting Recall.local infrastructure running across your MacBook (dev machine) and AI lab server (runtime).  
**Prerequisite:** Read the Recall.local PRD v2.1 first. This guide covers the *how*, not the *what* or *why*.  
**Exit Criteria:** All services start, can communicate, LLM calls work through both Ollama and at least one cloud provider, and the unified ingestion webhook accepts a test payload.

---

## Your Setup (Two Machines)

| Machine | Role | What Lives Here |
|---|---|---|
| **MacBook** | Development, coding, Claude Code / Codex sessions | Git repo, code editor, iOS Shortcut, browser access to server UIs |
| **AI Lab Server** (Ubuntu, RTX 2060) | Runtime — all services, data, models | Docker Compose stack, Qdrant, Ollama, n8n, Open WebUI, SQLite, /data tree |

**Connection:** SSH from MacBook → server via Ghostty. Browser on MacBook → server UIs (n8n, Open WebUI, MkDocs). Optional: VS Code Remote-SSH for GUI editing on server files.

---

## Step 0: Decide Your Dev Workflow

You have two options. Pick one and stick with it.

### Option A: Code on MacBook, Deploy to Server (Recommended)

- Edit code locally on your MacBook in your preferred editor
- Git push to GitHub
- SSH into server, git pull, restart services
- Best for: clean separation, works with Claude Code locally, easy to hand off tasks to Codex

### Option B: Code Directly on Server via SSH

- SSH into server from Ghostty, edit files there (vim, nano, or VS Code Remote-SSH)
- Git repo lives on the server, push to GitHub as backup
- Best for: faster iteration loop, no sync delays, immediate testing
- Downside: Claude Code runs on the server (needs Node.js installed there)

### Hybrid (What You'll Probably Actually Do)

- Scaffold and plan on your MacBook with Claude Code
- SSH into the server for testing, debugging, and n8n workflow building
- Git repo on GitHub as the source of truth for both machines

---

## Step 1: Create the Repository

**On your MacBook:**

```bash
mkdir recall-local && cd recall-local
git init

# Create directory structure
mkdir -p docker
mkdir -p n8n/workflows
mkdir -p prompts
mkdir -p scripts/eval
mkdir -p scripts/extract
mkdir -p shortcuts
mkdir -p data/incoming
mkdir -p data/processed
mkdir -p data/artifacts/meetings
mkdir -p data/artifacts/evals
mkdir -p data/artifacts/ingestion
mkdir -p docs

# Placeholder files so Git tracks empty directories
touch data/incoming/.gitkeep
touch data/processed/.gitkeep
touch data/artifacts/.gitkeep
touch n8n/workflows/.gitkeep
touch shortcuts/.gitkeep

# Create .gitignore
cat > .gitignore << 'EOF'
# Data files (don't commit actual documents)
data/incoming/*
data/processed/*
data/artifacts/*
!data/**/.gitkeep

# Environment files with secrets
docker/.env

# Python
__pycache__/
*.pyc
.venv/

# n8n local data (runtime state, not workflow exports)
n8n/data/

# SQLite databases
*.db
*.sqlite

# OS
.DS_Store
EOF

# Initial commit
git add .
git commit -m "Phase 0: repo skeleton"
```

**Push to GitHub:**

```bash
# Create repo on GitHub first (or use gh cli)
gh repo create recall-local --private --source=. --push
# OR
git remote add origin git@github.com:YOUR_USERNAME/recall-local.git
git push -u origin main
```

**On your AI lab server:**

```bash
cd ~  # or wherever you keep projects
git clone git@github.com:YOUR_USERNAME/recall-local.git
cd recall-local
```

---

## Step 2: Inventory Your Existing Services

Before writing the Docker Compose, figure out what you already have running and how. SSH into your server and check:

```bash
# What Docker containers are running?
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"

# Is Ollama running? What models do you have?
ollama list

# Is Qdrant running? Check health
curl -s http://localhost:6333/healthz

# Is n8n running? What port?
curl -s http://localhost:5678/healthz

# Is Open WebUI running?
curl -s http://localhost:3000/health  # or whatever port you use
```

**Write down:**
- Which services are already Dockerized vs. running natively
- What ports they're on
- Where their data volumes are mounted
- Whether they're managed by an existing docker-compose file

This matters because you have two approaches for Phase 0:

### Approach A: Wrap Everything in One New Docker Compose
- Clean, reproducible, good for the portfolio
- Might mean migrating existing services and their data
- More work upfront

### Approach B: Add Only the New Pieces, Connect to Existing Services
- Leave Ollama, Qdrant, n8n, Open WebUI running as they are
- Add SQLite, MkDocs, and the ingestion webhook as new containers or scripts
- Connect them via your existing Docker network or host networking
- Faster to get started, clean up later

**Recommendation:** Start with Approach B. Get Recall.local working first, then consolidate into a clean Docker Compose for the portfolio. Don't let infrastructure reorganization block actual progress.

---

## Step 3: Create the Docker Compose (New Services Only)

This compose file adds the pieces you're missing. It assumes your existing services (Ollama, Qdrant, n8n, Open WebUI) are already running.

**On the server**, create `docker/docker-compose.yml`:

```yaml
# Recall.local - Additional Services
# Your existing stack (Ollama, Qdrant, n8n, Open WebUI) runs separately.
# This adds the Recall.local-specific pieces.

version: "3.8"

services:
  # ---- Artifact Viewer (MkDocs) ----
  mkdocs:
    image: squidfunk/mkdocs-material:latest
    container_name: recall-mkdocs
    ports:
      - "8100:8000"
    volumes:
      - ../docs:/docs
      - ../data/artifacts:/docs/docs/artifacts:ro
    restart: unless-stopped

  # ---- Python Environment for Scripts ----
  # Optional: run this if you want a containerized Python env
  # Otherwise, just install deps on the server directly
  # recall-scripts:
  #   build: ./scripts
  #   volumes:
  #     - ../data:/data
  #     - ../prompts:/prompts
  #     - ../scripts:/scripts

networks:
  default:
    name: recall-net
    # If your existing services are on a specific Docker network,
    # use 'external: true' and match that network name instead
```

**Create the environment file** `docker/.env.example`:

```bash
# ---- LLM Provider ----
# Options: ollama, anthropic, openai
RECALL_LLM_PROVIDER=ollama

# Ollama (local)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3:8b
OLLAMA_EMBED_MODEL=nomic-embed-text

# Anthropic (cloud escape hatch)
ANTHROPIC_API_KEY=sk-ant-xxxxx
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# OpenAI (cloud escape hatch)
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=gpt-4o-mini

# ---- Qdrant ----
QDRANT_HOST=http://localhost:6333
QDRANT_COLLECTION=recall_docs

# ---- n8n Webhook ----
N8N_HOST=http://localhost:5678
RECALL_WEBHOOK_PATH=/webhook/recall-ingest

# ---- Paths ----
DATA_INCOMING=/path/to/recall-local/data/incoming
DATA_PROCESSED=/path/to/recall-local/data/processed
DATA_ARTIFACTS=/path/to/recall-local/data/artifacts

# ---- Email Ingestion (Phase 1) ----
RECALL_EMAIL_HOST=imap.gmail.com
RECALL_EMAIL_USER=your-recall-inbox@gmail.com
RECALL_EMAIL_PASSWORD=app-password-here

# ---- Tailscale (optional, for mobile access) ----
# Your server's Tailscale IP (e.g., 100.x.x.x)
TAILSCALE_IP=
```

```bash
# Copy and fill in your values
cp docker/.env.example docker/.env
```

---

## Step 4: Set Up Python Environment on the Server

You need Python with a few key packages for the extraction and eval scripts. Do this directly on the server (containerize later if you want).

```bash
# On the server
cd ~/recall-local

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Core dependencies
pip install trafilatura        # URL/webpage text extraction
pip install qdrant-client      # Qdrant Python client
pip install httpx              # HTTP client for webhooks/APIs
pip install python-dotenv      # Load .env files
pip install pdfplumber         # PDF text extraction (better than PyPDF2)

# Optional but useful
pip install tiktoken           # Token counting for chunking
pip install rich               # Pretty terminal output for eval results

# Save requirements
pip freeze > requirements.txt
```

---

## Step 5: Create the Qdrant Collection

If you don't already have the `recall_docs` collection, create it:

```bash
# On the server, with your venv activated
python3 << 'EOF'
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

client = QdrantClient(host="localhost", port=6333)

# Check if collection exists
collections = [c.name for c in client.get_collections().collections]

if "recall_docs" not in collections:
    client.create_collection(
        collection_name="recall_docs",
        vectors_config=VectorParams(
            size=768,  # nomic-embed-text dimension — verify with your model
            distance=Distance.COSINE,
        ),
    )
    print("Created recall_docs collection")
else:
    print("recall_docs already exists")
    info = client.get_collection("recall_docs")
    print(f"  Vectors: {info.points_count}")
    print(f"  Dimension: {info.config.params.vectors.size}")
EOF
```

> **Important:** Verify the embedding dimension matches your Ollama embedding model. Run `ollama show nomic-embed-text` or check the model card. Common dimensions: nomic-embed-text = 768, mxbai-embed-large = 1024, all-minilm = 384. If you use a different model, adjust the `size` parameter.

---

## Step 6: Initialize SQLite Database

```bash
# On the server
python3 << 'EOF'
import sqlite3
import os

db_path = os.path.expanduser("~/recall-local/data/recall.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.executescript("""
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        workflow TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'started',
        started_at TEXT NOT NULL,
        ended_at TEXT,
        model TEXT,
        latency_ms INTEGER,
        input_hash TEXT,
        output_path TEXT
    );

    CREATE TABLE IF NOT EXISTS eval_results (
        eval_id TEXT PRIMARY KEY,
        question TEXT NOT NULL,
        expected_doc_id TEXT,
        actual_doc_id TEXT,
        citation_valid BOOLEAN,
        latency_ms INTEGER,
        passed BOOLEAN,
        run_date TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS alerts (
        alert_id TEXT PRIMARY KEY,
        severity TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        summary TEXT,
        run_id TEXT REFERENCES runs(run_id)
    );

    CREATE TABLE IF NOT EXISTS ingestion_log (
        ingest_id TEXT PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_ref TEXT,
        channel TEXT NOT NULL,
        doc_id TEXT,
        chunks_created INTEGER DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending',
        timestamp TEXT NOT NULL
    );
""")

conn.commit()
conn.close()
print(f"SQLite database initialized at {db_path}")
print("Tables: runs, eval_results, alerts, ingestion_log")
EOF
```

---

## Step 7: Create the LLM Abstraction Layer

This is the cloud escape hatch. A single Python module that routes LLM calls based on the environment variable.

**Create `scripts/llm_client.py`:**

```python
"""
Recall.local LLM Client — Thin abstraction over Ollama and cloud APIs.
Switch providers via RECALL_LLM_PROVIDER environment variable.
"""

import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "docker", ".env"))

PROVIDER = os.getenv("RECALL_LLM_PROVIDER", "ollama")


def generate(prompt: str, system: str = "", temperature: float = 0.3) -> str:
    """Generate text from the configured LLM provider."""
    if PROVIDER == "ollama":
        return _ollama_generate(prompt, system, temperature)
    elif PROVIDER == "anthropic":
        return _anthropic_generate(prompt, system, temperature)
    elif PROVIDER == "openai":
        return _openai_generate(prompt, system, temperature)
    else:
        raise ValueError(f"Unknown LLM provider: {PROVIDER}")


def embed(text: str) -> list[float]:
    """Generate embeddings. Always uses Ollama (local) for privacy."""
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    response = httpx.post(
        f"{host}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def _ollama_generate(prompt, system, temperature):
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3:8b")

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system

    response = httpx.post(f"{host}/api/generate", json=payload, timeout=120)
    response.raise_for_status()
    return response.json()["response"]


def _anthropic_generate(prompt, system, temperature):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": model,
        "max_tokens": 4096,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system

    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]


def _openai_generate(prompt, system, temperature):
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json={"model": model, "messages": messages, "temperature": temperature},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


# ---- Quick test ----
if __name__ == "__main__":
    print(f"Provider: {PROVIDER}")
    print("Testing generation...")
    result = generate("Say 'Recall.local is online' and nothing else.")
    print(f"Response: {result}")
    print("\nTesting embedding...")
    vec = embed("test embedding")
    print(f"Embedding dimension: {len(vec)}")
    print("\nAll systems go.")
```

---

## Step 8: Verify Connectivity (The Phase 0 Smoke Test)

Run this from the server to make sure everything can talk to everything:

```bash
# On the server, with venv activated
cd ~/recall-local

python3 << 'EOF'
import httpx
import sqlite3
import os

print("=" * 50)
print("Recall.local Phase 0 — Connectivity Check")
print("=" * 50)

checks = []

# 1. Ollama
try:
    r = httpx.get("http://localhost:11434/api/tags", timeout=5)
    models = [m["name"] for m in r.json().get("models", [])]
    print(f"\n✅ Ollama: {len(models)} models loaded")
    for m in models[:5]:
        print(f"   - {m}")
    checks.append(True)
except Exception as e:
    print(f"\n❌ Ollama: {e}")
    checks.append(False)

# 2. Qdrant
try:
    r = httpx.get("http://localhost:6333/collections", timeout=5)
    collections = [c["name"] for c in r.json().get("result", {}).get("collections", [])]
    print(f"\n✅ Qdrant: {len(collections)} collections")
    for c in collections:
        print(f"   - {c}")
    checks.append(True)
except Exception as e:
    print(f"\n❌ Qdrant: {e}")
    checks.append(False)

# 3. n8n
try:
    r = httpx.get("http://localhost:5678/healthz", timeout=5)
    print(f"\n✅ n8n: healthy (status {r.status_code})")
    checks.append(True)
except Exception as e:
    print(f"\n❌ n8n: {e}")
    checks.append(False)

# 4. SQLite
try:
    db_path = os.path.expanduser("~/recall-local/data/recall.db")
    conn = sqlite3.connect(db_path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t[0] for t in tables]
    print(f"\n✅ SQLite: {len(table_names)} tables at {db_path}")
    for t in table_names:
        print(f"   - {t}")
    conn.close()
    checks.append(True)
except Exception as e:
    print(f"\n❌ SQLite: {e}")
    checks.append(False)

# 5. LLM abstraction layer
try:
    from scripts.llm_client import generate, embed, PROVIDER
    print(f"\n✅ LLM client loaded (provider: {PROVIDER})")
    checks.append(True)
except Exception as e:
    print(f"\n❌ LLM client: {e}")
    checks.append(False)

# 6. Data directories
data_dirs = ["data/incoming", "data/processed", "data/artifacts"]
for d in data_dirs:
    path = os.path.expanduser(f"~/recall-local/{d}")
    if os.path.isdir(path):
        print(f"\n✅ {d}: exists")
    else:
        print(f"\n❌ {d}: missing")
        checks.append(False)
checks.append(True)

# Summary
print("\n" + "=" * 50)
passed = sum(checks)
total = len(checks)
if all(checks):
    print(f"🟢 ALL CHECKS PASSED ({passed}/{total})")
    print("Phase 0 exit criteria: MET")
else:
    print(f"🟡 {passed}/{total} checks passed")
    print("Phase 0 exit criteria: NOT YET MET")
print("=" * 50)
EOF
```

---

## Step 9: Set Up Tailscale (For Mobile Ingestion)

Tailscale gives your phone, MacBook, and server a private network so the ingestion webhook is reachable from anywhere without exposing ports to the internet.

```bash
# On the server (if not already installed)
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Note the Tailscale IP (100.x.x.x)
tailscale ip -4
```

Install Tailscale on your MacBook and iPhone too. Once all three devices are on the same Tailnet:

- MacBook browser → `http://100.x.x.x:5678` → n8n editor
- iPhone Shortcut → `http://100.x.x.x:5678/webhook/recall-ingest` → ingestion webhook
- Everything stays private, no port forwarding, no reverse proxy

---

## Step 10: Set Up MkDocs for Artifact Browsing

Create a minimal MkDocs config so you can browse artifacts in a browser:

**Create `docs/mkdocs.yml`:**

```yaml
site_name: Recall.local Artifacts
theme:
  name: material
  palette:
    primary: indigo
nav:
  - Home: index.md
  - Artifacts:
    - Meetings: artifacts/meetings/
    - Evaluations: artifacts/evals/
    - Ingestion: artifacts/ingestion/
```

**Create `docs/docs/index.md`:**

```markdown
# Recall.local Artifacts

Browse generated artifacts from Recall.local workflows.

- [Meeting Action Items](artifacts/meetings/)
- [Eval Reports](artifacts/evals/)
- [Ingestion Reports](artifacts/ingestion/)
```

**Start MkDocs:**

```bash
# Using Docker (from recall-local/docker/)
docker compose up -d mkdocs

# Or directly if you have mkdocs installed
cd docs && mkdocs serve -a 0.0.0.0:8100
```

Access at `http://your-server-ip:8100` (or Tailscale IP).

---

## Step 11: Test the LLM Escape Hatch

Run the LLM client test with each provider to confirm the abstraction works:

```bash
cd ~/recall-local
source .venv/bin/activate

# Test with Ollama (default)
RECALL_LLM_PROVIDER=ollama python3 scripts/llm_client.py

# Test with Anthropic (if you have an API key)
RECALL_LLM_PROVIDER=anthropic python3 scripts/llm_client.py

# Test with OpenAI (if you have an API key)
RECALL_LLM_PROVIDER=openai python3 scripts/llm_client.py
```

All three should return a response. If Ollama works but cloud fails, check your API keys in `docker/.env`.

---

## Phase 0 Checklist

Run through this before moving to Phase 1:

- [ ] Git repo created and pushed to GitHub
- [ ] Repo cloned on the AI lab server
- [ ] All directory structure in place (/data/incoming, /data/processed, /data/artifacts, etc.)
- [ ] Ollama running with at least one generation model + one embedding model
- [ ] Qdrant running with `recall_docs` collection created (correct embedding dimension)
- [ ] n8n running and accessible from MacBook browser
- [ ] Open WebUI running and connected to Ollama
- [ ] SQLite database initialized with all four tables
- [ ] `scripts/llm_client.py` working with Ollama
- [ ] Cloud escape hatch tested with at least one cloud provider
- [ ] Python venv set up with core dependencies (trafilatura, qdrant-client, pdfplumber, etc.)
- [ ] MkDocs serving /data/artifacts
- [ ] Tailscale installed on server, MacBook, and phone (all on same Tailnet)
- [ ] Phase 0 smoke test script passes all checks
- [ ] `.env` file configured (not committed to Git)

**When all boxes are checked: Phase 0 is done. Move to Phase 1 (RAG MVP + Multi-Source Ingestion + Eval Harness).**

---

## What's Next: Phase 1 Preview

Phase 1 implementation will be its own guide. High-level, you'll build:

1. **Chunking script** (`scripts/extract/chunker.py`) — heading-aware splitting with configurable token limits
2. **n8n Workflow 01** — folder watcher + unified webhook → extraction → chunking → embedding → Qdrant upsert
3. **n8n Workflow 02** — RAG query webhook → embed query → Qdrant search → LLM generate → validate → respond
4. **URL extractor** (`scripts/extract/url_extractor.py`) — Trafilatura wrapper for web page ingestion
5. **iOS Shortcut** — share sheet → POST to ingestion webhook
6. **Gmail forward-to-ingest** — n8n email trigger → attachment/body extraction → ingestion pipeline
7. **Output validator** (`scripts/validate_output.py`) — citation checking, JSON structure validation, retry logic
8. **Eval harness** (`scripts/eval/run_eval.py`) — test questions, expected citations, pass/fail reporting

Each of these is a well-scoped task you could hand to Claude Code or Codex with clear inputs and expected outputs.

---

*End of Phase 0 Guide*
