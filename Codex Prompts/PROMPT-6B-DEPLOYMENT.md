# Prompt 6B — Git Repository + Dockerfile + Railway Deployment

Read `Project state Alexandria Cover designer.md` for full context.

The Cover Designer project has no version control, no Dockerfile, and no cloud deployment. This prompt sets all that up.

## What exists

- Full pipeline code in `src/` (12 Python modules, ~5,750 lines)
- Webapp in `scripts/quality_review.py` (serves /iterate and /review pages)
- Static HTML in `src/static/iterate.html` and `src/static/review.html`
- Config files in `config/` (book_catalog.json, cover_regions.json, prompt_library.json, etc.)
- Input covers in `Input Covers/`
- Generated test outputs in `Output Covers/` and `tmp/`
- `.env.example` with all config vars
- `requirements.txt` with all dependencies
- `.gitignore` exists

## Task 1: Initialize Git Repository

1. Verify `.gitignore` includes: `.env`, `tmp/`, `Output Covers/`, `__pycache__/`, `*.pyc`, `.venv/`, `data/generation_history.json`, `data/generation_failures.json`
2. Add to `.gitignore` if missing: `config/credentials.json`, `*.egg-info/`
3. `git init`
4. `git add` all appropriate files (NOT `Input Covers/` — too large, NOT `.env`, NOT `tmp/`)
5. `git commit -m "Initial commit: Alexandria Cover Designer pipeline"`

NOTE: Do NOT push to GitHub or create a remote repo yet. Tim will do that.

## Task 2: Create Dockerfile

Create `Dockerfile` based on Python 3.11-slim:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps for OpenCV headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/
COPY .env.example .env.example

# Static files for webapp
COPY src/static/ src/static/

# Create directories
RUN mkdir -p tmp data "Output Covers" "Input Covers"

EXPOSE ${PORT:-8001}

CMD ["python3", "scripts/quality_review.py", "--serve", "--port", "8001", "--output-dir", "Output Covers"]
```

Adjust based on what `quality_review.py` actually needs to run. Ensure:
- All `src/` imports work inside the container
- `config/` directory has book_catalog.json, cover_regions.json, prompt_library.json, prompt_templates.json, book_prompts.json, compositing_mask.png
- Static HTML files are accessible
- The server binds to `0.0.0.0` (not `127.0.0.1`) for Docker/Railway

**CRITICAL**: The webapp server in `quality_review.py` line 408 binds to `127.0.0.1`:
```python
server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
```
Change it to bind to `0.0.0.0` so it's accessible outside the container. Use a `HOST` env var with default `0.0.0.0`:
```python
host = os.environ.get("HOST", "0.0.0.0")
server = ThreadingHTTPServer((host, port), Handler)
```

## Task 3: Create docker-compose.yml

```yaml
version: "3.8"
services:
  cover-designer:
    build: .
    ports:
      - "${PORT:-8001}:8001"
    env_file: .env
    volumes:
      - ./Input Covers:/app/Input Covers:ro
      - ./Output Covers:/app/Output Covers
      - ./tmp:/app/tmp
      - ./data:/app/data
```

## Task 4: Create railway.toml

```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
healthcheckPath = "/api/health"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

## Task 5: Add /api/health endpoint

In `scripts/quality_review.py`, add a `GET /api/health` route that returns:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "books_cataloged": 99,
  "models_configured": ["list of model names from config"],
  "api_keys_configured": ["openrouter", "openai"]
}
```

Only list providers that have keys set in the environment.

## Task 6: Create DEPLOY.md

Write deployment instructions covering:
1. Local Docker: `docker compose up -d`
2. Railway: Create project, link GitHub repo, set env vars, deploy
3. Required env vars table (which are required vs optional)
4. How to verify deployment (health check URL)

## Task 7: Create .railwayignore

Exclude: `Input Covers/`, `Output Covers/`, `tmp/`, `.env`, `.git/`, `__pycache__/`, `*.pyc`, `data/generation_*.json`, `Codex Prompts/`, `Codex Output Answers/`, `*.pdf`

## Verification Checklist

1. `.gitignore` covers all sensitive/large files — PASS/FAIL
2. `git init` + initial commit succeeds — PASS/FAIL
3. `Dockerfile` builds without errors: `docker build -t cover-designer .` — PASS/FAIL
4. Container starts and `/api/health` returns 200 — PASS/FAIL
5. `/iterate` page loads in container — PASS/FAIL
6. `/review` page loads in container — PASS/FAIL
7. Server binds to 0.0.0.0 (not 127.0.0.1) — PASS/FAIL
8. `railway.toml` is valid TOML — PASS/FAIL
9. `.railwayignore` excludes Input/Output/tmp — PASS/FAIL
10. `DEPLOY.md` exists with clear instructions — PASS/FAIL
11. `/api/health` shows correct model count and key status — PASS/FAIL
12. `docker-compose.yml` is valid YAML — PASS/FAIL

Run every check. Report PASS/FAIL for each.

Save output to `Codex Output Answers/PROMPT-6B-OUTPUT.md`.
