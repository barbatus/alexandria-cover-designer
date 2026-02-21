# Cover Designer — All Remaining Codex Prompts

> **Instructions**: Send these to Codex in order: 6A → 6B → 6C → 7A → 7B.
> Each prompt is self-contained. Start a NEW Codex thread for each one.
>
> **Already complete (DO NOT re-send):** Prompts 1A, 1B, 2A, 2B, 3A, 3B, 4A, 4B, 5

---

## Prompt 6A — Bug Fix + API Verification + Test Command

```
Read `Project state Alexandria Cover designer.md` for full context, especially decisions D19-D23.

All pipeline code exists in src/ (12 modules). This prompt fixes known gaps and prepares for real API usage.

## Task 1: Fix output_exporter.py variant cap (BUG)

In `src/output_exporter.py`, around line 200, there is a hardcoded cap:

    if len(selected) >= 5:
        break

This contradicts Tim's decision D22 (configurable variation count — 5, 10, 20+).

Fix: Replace hardcoded `5` with a configurable value. Add `MAX_EXPORT_VARIANTS` to `.env.example` (default 20). Read from `src/config.py`. The function should accept an optional `max_variants` parameter that overrides the config default.

## Task 2: Verify all API provider integrations

Check each provider class in `src/image_generator.py` and verify the code is correctly structured for real API calls:

1. **OpenRouterProvider** — endpoint `https://openrouter.ai/api/v1/images/generations`, auth `Bearer $OPENROUTER_API_KEY`, response format extracts base64 or URL
2. **OpenAIProvider** — endpoint `https://api.openai.com/v1/images/generations`, auth `Bearer $OPENAI_API_KEY`
3. **ReplicateProvider** — uses `replicate` SDK's `replicate.run()` with proper model version
4. **FalProvider** — endpoint format and auth header correct for fal.ai
5. **GoogleProvider** — Imagen 4 endpoint and auth correct

For each provider:
- Verify the endpoint URL is correct (check against current docs — February 2026)
- Verify auth header format is correct
- Verify response parsing extracts image bytes properly
- Verify error handling catches 429 (rate limit), 401 (bad key), 500 (server error)
- If any provider has an incorrect URL or format, FIX IT

Do NOT call any real APIs. Just audit and fix the code.

## Task 3: Verify .env.example completeness

Check every `os.getenv()` and `os.environ.get()` call across ALL src/*.py files. Ensure every referenced env var exists in `.env.example` with a sensible default or placeholder comment.

## Task 4: Add --test-api-keys command to pipeline.py

Add a `--test-api-keys` CLI flag that:
1. Reads `.env` via python-dotenv
2. For each provider that has a key set, makes a minimal test call:
   - OpenRouter: `GET https://openrouter.ai/api/v1/models` with auth header
   - OpenAI: `GET https://api.openai.com/v1/models` with auth header
   - Replicate: `replicate.models.get("black-forest-labs/flux-2-pro")` (metadata only, no generation)
   - fal: health check or model list endpoint
   - Google: model list endpoint
3. Reports per provider: `PROVIDER — KEY VALID / KEY INVALID / KEY MISSING`
4. Incurs zero generation cost

## Task 5: Add provider selector to iterate page

In `src/static/iterate.html`, add a provider dropdown above the model selector:
- Options: openrouter, openai, replicate, fal, google, all
- When "all" is selected (default), show all models from all providers
- When a specific provider is selected, filter the model list to that provider's models only
- Pass the selected provider in the `/api/generate` POST body

In `scripts/quality_review.py`, update the `/api/generate` handler to accept and use the `provider` field.

## Verification Checklist

1. `py_compile` passes for all modified files — PASS/FAIL
2. `output_exporter.py` no longer has hardcoded `5` cap — PASS/FAIL
3. New `MAX_EXPORT_VARIANTS` env var in .env.example with default 20 — PASS/FAIL
4. All 5 provider classes have verified endpoint URLs — PASS/FAIL
5. All 5 provider classes have correct auth header format — PASS/FAIL
6. Error handling catches 429, 401, 500 for each provider — PASS/FAIL
7. `.env.example` covers every env var in codebase — PASS/FAIL
8. `python3 src/pipeline.py --test-api-keys` runs without crash — PASS/FAIL
9. iterate.html has provider dropdown — PASS/FAIL
10. `/api/generate` accepts provider field — PASS/FAIL
11. All existing imports still work — PASS/FAIL
12. `pytest tests/test_unit.py` passes — PASS/FAIL

Run every check. Report PASS/FAIL for each.

Save output to `Codex Output Answers/PROMPT-6A-OUTPUT.md`.
```

---

## Prompt 6B — Git Repository + Dockerfile + Railway Deployment

```
Read `Project state Alexandria Cover designer.md` for full context.

The Cover Designer project has no version control, no Dockerfile, and no cloud deployment. This prompt sets all that up.

**What exists:**
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
4. `git add` all appropriate files (NOT Input Covers/ — too large, NOT .env, NOT tmp/)
5. `git commit -m "Initial commit: Alexandria Cover Designer pipeline"`

NOTE: Do NOT push to GitHub or create a remote repo yet. Tim will do that.

## Task 2: Create Dockerfile

Create `Dockerfile` based on Python 3.11-slim:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps
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

Adjust based on what quality_review.py actually needs to run. Ensure:
- All `src/` imports work
- `config/` directory has book_catalog.json, cover_regions.json, prompt_library.json, prompt_templates.json, book_prompts.json, compositing_mask.png
- Static HTML files are accessible
- The server binds to 0.0.0.0 (not 127.0.0.1) for Docker/Railway

**CRITICAL**: The webapp server in `quality_review.py` binds to `127.0.0.1`. Change it to bind to `0.0.0.0` so it's accessible outside the container. Use `HOST` env var with default `0.0.0.0`.

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
  "api_keys_configured": ["openrouter", "openai"]  // only list providers that have keys set
}
```

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
10. `DEPLOY.md` exists with >500 chars — PASS/FAIL
11. `/api/health` shows correct model count and key status — PASS/FAIL
12. `docker-compose.yml` is valid YAML — PASS/FAIL

Run every check. Report PASS/FAIL for each.

Save output to `Codex Output Answers/PROMPT-6B-OUTPUT.md`.
```

---

## Prompt 6C — First Real Generation Test + Compositing Verification

```
Read `Project state Alexandria Cover designer.md` for full context.

**What exists:**
- Full pipeline (src/ — 12 modules), webapp (quality_review.py), Docker deployment (6B)
- API keys should now be configured in .env
- 99 books cataloged with 495 prompts ready

This prompt runs the first REAL AI image generation and verifies the full end-to-end pipeline.

## Task 1: Verify API keys are configured

Run `python3 src/pipeline.py --test-api-keys` and confirm at least ONE provider shows KEY VALID.

If NO keys are valid, STOP and report. Tim needs to configure .env first.

## Task 2: Single book test — Book #2 (Moby Dick)

Run the full pipeline for ONE book with ONE model and 3 variants:

```bash
python3 src/pipeline.py --book 2 --variants 3 --dry-run
```

Verify the dry run output looks correct (shows what would be generated), then run for real:

```bash
python3 src/pipeline.py --book 2 --variants 3
```

Check:
1. 3 images generated in `tmp/generated/2/`
2. Images are actual illustrations (not blank/placeholder), 1024×1024 pixels
3. Quality gate runs and scores each image
4. Compositing places illustrations into the Moby Dick cover
5. Output covers saved to `Output Covers/2. Moby Dick.../Variant-1/` through `Variant-3/`
6. Each variant folder has .jpg, .pdf, .ai files
7. The composited .jpg shows the illustration inside the gold medallion frame

## Task 3: Multi-model test

If more than one provider has valid keys, run:

```bash
python3 src/pipeline.py --book 1 --all-models --variants 2
```

Verify:
1. All configured models fire concurrently
2. Results are grouped by model in the output
3. Quality gate scores all results
4. Model leaderboard generated in `data/model_rankings.json`

## Task 4: Webapp generation test

Start the webapp:
```bash
python3 scripts/quality_review.py --serve --output-dir "Output Covers"
```

Then test the /iterate page programmatically:
1. `GET /api/iterate-data` returns books, models, style anchors
2. `POST /api/generate` with book=2, variants=2 triggers real generation
3. Response includes image paths that exist on disk
4. `/api/history?book=2` shows the generation history

## Task 5: Visual verification

For EACH generated cover:
1. Open the composited .jpg
2. Verify: illustration sits INSIDE the gold frame (not overlapping it)
3. Verify: everything OUTSIDE the medallion is pixel-identical to the original cover
4. Verify: no visible seam at the circle edge
5. Verify: the illustration is relevant to the book (not random/abstract)
6. Verify: .pdf opens correctly, full resolution
7. Verify: .ai file is a valid PDF-based Adobe Illustrator file

## Verification Checklist

1. At least one API key is valid — PASS/FAIL
2. Dry run shows correct generation plan — PASS/FAIL
3. Real generation produces 3 images for book #2 — PASS/FAIL
4. Images are 1024×1024, not blank/placeholder — PASS/FAIL
5. Quality gate scores all 3 images — PASS/FAIL
6. Compositing produces 3 cover variants — PASS/FAIL
7. Output folder structure correct (.jpg, .pdf, .ai per variant) — PASS/FAIL
8. Composited image: illustration inside frame, rest of cover untouched — PASS/FAIL
9. No visible seam at medallion edge — PASS/FAIL
10. Multi-model test (if applicable): all models fire — PASS/FAIL
11. Webapp /api/generate triggers real generation — PASS/FAIL
12. /api/history shows generation records — PASS/FAIL
13. .pdf file opens correctly — PASS/FAIL
14. .ai file is valid — PASS/FAIL

Run every check. Report PASS/FAIL for each. Include file sizes and image dimensions.

**IMPORTANT**: If generation fails due to API errors, document the exact error and which provider/model caused it. Do NOT retry endlessly — report after 3 failures per provider.

Save output to `Codex Output Answers/PROMPT-6C-OUTPUT.md`.
```

---

## Prompt 7A — Scale to 20 Titles + Prompt Tuning

```
Read `Project state Alexandria Cover designer.md` for full context, especially decision D23 (start with 20 titles).

**What exists:**
- Full pipeline verified with real API generation (6C)
- At least 1 book successfully generated end-to-end

This prompt scales to 20 titles and identifies prompt quality issues.

## Task 1: Generate covers for books 1-20

Run the pipeline for the first 20 books with the best-performing model from 6C:

```bash
python3 src/pipeline.py --books 1-20 --variants 5 --resume
```

Use `--resume` so it skips any books already completed in 6C.

Monitor and report:
- Total generation time
- Total cost (from generation history)
- Success/failure count per book
- Any books that failed all 5 variants

## Task 2: Quality analysis

After generation completes:
1. Run quality gate on all 100 images (20 books × 5 variants)
2. Generate `data/quality_report.md`
3. Identify:
   - Books with ALL variants scoring below 0.7 (need prompt rewriting)
   - Books with high variation in scores (prompts are inconsistent)
   - Common quality issues across books (e.g., text artifacts, wrong aspect ratio)
   - Top 5 best-scoring books and their prompts

## Task 3: Prompt tuning for underperformers

For any book where ALL 5 variants scored below 0.7:
1. Analyze the prompts in `config/book_prompts.json`
2. Identify what's causing poor results (too vague? wrong art style? conflicting terms?)
3. Rewrite the 5 prompts for that book using the style anchors that performed best
4. Save the improved prompts
5. Re-generate 5 variants for each fixed book

## Task 4: Model comparison (if multiple providers available)

For 5 representative books (pick books 1, 5, 10, 15, 20):
```bash
python3 src/pipeline.py --book 1 --all-models --variants 3
python3 src/pipeline.py --book 5 --all-models --variants 3
# ... etc for 10, 15, 20
```

Generate `data/model_rankings.json` with aggregated quality scores per model.
Identify the best model for this style of illustration.

## Task 5: Update prompt library

Save the top 10 best-performing prompts to `config/prompt_library.json`:
- Extract the prompt text from the highest-scoring variants
- Make them title-agnostic (replace specific book title with `{title}`)
- Tag with appropriate style anchors
- Set quality_score from actual gate scores

## Verification Checklist

1. 20 books processed (or attempted) — PASS/FAIL
2. At least 80% of books (16+) have at least 1 variant scoring ≥ 0.7 — PASS/FAIL
3. `data/quality_report.md` generated — PASS/FAIL
4. `data/quality_scores.json` has entries for all images — PASS/FAIL
5. Underperforming books identified and prompts rewritten — PASS/FAIL
6. Re-generated variants for fixed books score higher — PASS/FAIL
7. Model comparison completed for 5 books (if multi-provider) — PASS/FAIL
8. `data/model_rankings.json` generated — PASS/FAIL
9. Top 10 prompts saved to prompt_library.json — PASS/FAIL
10. Total cost documented — PASS/FAIL
11. Composited covers for all 20 books in Output Covers/ — PASS/FAIL
12. Catalog PDF regenerated with real covers — PASS/FAIL

Run every check. Report PASS/FAIL for each. Include total cost and generation time.

Save output to `Codex Output Answers/PROMPT-7A-OUTPUT.md`.
```

---

## Prompt 7B — Google Drive Sync + Final Integration

```
Read `Project state Alexandria Cover designer.md` for full context.

**What exists:**
- 20 books with real AI-generated covers in Output Covers/
- `src/gdrive_sync.py` exists but hasn't been tested with real credentials
- Target Drive folder: https://drive.google.com/drive/folders/1Vr184ZsX3k38xpmZkd8g2vwB5y9LYMRC

## Task 1: Test Google Drive sync

1. Verify `src/gdrive_sync.py` can authenticate:
   - Check for `config/credentials.json` (OAuth2 client credentials)
   - If missing, document the exact steps Tim needs to create it (Google Cloud Console → APIs → Drive API → OAuth → Desktop App)
   - If present, run the auth flow

2. Upload test: upload 1 variant from book #1 to the target Drive folder
3. Verify: file appears in Drive, correct folder structure
4. Upload 5 variants from book #2
5. Test resume: re-run upload for book #2 — should skip already-uploaded files

## Task 2: Bulk sync for 20 books

Upload all Output Covers for 20 books:

```bash
python3 -m src.gdrive_sync --input "Output Covers" --drive-folder-id 1Vr184ZsX3k38xpmZkd8g2vwB5y9LYMRC
```

Report: files uploaded, files skipped (already exist), any failures.

## Task 3: Pipeline integration

Add a `--sync` flag to `pipeline.py` that automatically uploads to Drive after generation:

```bash
python3 src/pipeline.py --book 1 --variants 3 --sync
```

This should:
1. Generate → Quality Gate → Composite → Export → Upload to Drive
2. Only upload variants that pass the quality gate

## Task 4: Add sync status to webapp

Add a "Sync to Drive" button on the `/review` page that:
1. Uploads all selected (winner) variants to Drive
2. Shows upload progress
3. Reports success/failure

Add the endpoint `POST /api/sync-to-drive` in `scripts/quality_review.py`.

## Task 5: Alternative sync (rclone fallback)

If Google OAuth setup is too complex (no credentials.json), provide a `scripts/rclone_sync.sh` fallback:

```bash
#!/bin/bash
# Requires: rclone configured with Google Drive remote named "gdrive"
rclone copy "Output Covers/" "gdrive:Alexandria Publishing/Output Covers/" \
  --include "*.jpg" --include "*.pdf" --include "*.ai" \
  --progress --transfers 4
```

Include setup instructions in DEPLOY.md.

## Verification Checklist

1. Google Drive auth works (OAuth or service account) — PASS/FAIL (or SKIPPED if no credentials)
2. Single file upload to Drive succeeds — PASS/FAIL
3. Folder structure created correctly in Drive — PASS/FAIL
4. Resume skips already-uploaded files — PASS/FAIL
5. Bulk sync for 20 books completes — PASS/FAIL
6. `--sync` flag works in pipeline.py — PASS/FAIL
7. "Sync to Drive" button on /review page works — PASS/FAIL
8. rclone fallback script exists — PASS/FAIL
9. DEPLOY.md updated with Drive sync instructions — PASS/FAIL
10. Upload progress reported — PASS/FAIL

Run every check. Report PASS/FAIL for each.

Save output to `Codex Output Answers/PROMPT-7B-OUTPUT.md`.
```

---

## Quick Reference: Full Execution Order

| Order | Prompt | What It Does | Prerequisites |
|-------|--------|-------------|---------------|
| ✅ | 1A — Cover Analysis | Extract regions from 99 covers | Done |
| ✅ | 1B — Prompt Engineering | Generate 495 prompts (5 per book) | Done |
| ✅ | 2A — Image Generation | Multi-provider generation pipeline | Done |
| ✅ | 2B — Quality Gate | Auto-filter and score images | Done |
| ✅ | 3A — Cover Composition | Composite illustrations into covers | Done |
| ✅ | 3B — Format Export | Export .jpg/.pdf/.ai | Done |
| ✅ | 4A — Batch Orchestration | End-to-end pipeline CLI | Done |
| ✅ | 4B — Google Drive Sync | Upload to Drive | Done |
| ✅ | 5 — Visual QA Webapp | /iterate and /review pages | Done |
| ➡️ | **6A — Bug Fix + API Prep** | Fix 5-variant cap, verify APIs, add --test-api-keys | None |
| ➡️ | **6B — Deployment** | Git repo, Dockerfile, Railway config | 6A |
| ➡️ | **6C — First Real Gen** | Real AI generation for 1-3 books | 6A + Tim sets up .env |
| ➡️ | **7A — Scale to 20** | Generate 20 books, tune prompts, model comparison | 6C |
| ➡️ | **7B — Drive Sync** | Upload to Google Drive, pipeline integration | 7A |

## What Tim Needs to Do (Between Prompts)

**Before 6C:**
1. Sign up for OpenRouter at https://openrouter.ai (one API key covers FLUX 2 Pro + many models)
2. Copy `.env.example` to `.env`
3. Paste your OpenRouter API key as `OPENROUTER_API_KEY=sk-or-...`
4. Run `python3 src/pipeline.py --test-api-keys` to verify

**Before 7B:**
1. Go to Google Cloud Console → Enable Drive API
2. Create OAuth 2.0 credentials (Desktop App)
3. Download as `config/credentials.json`
4. First run will open browser for auth consent

**After 6B (optional):**
1. Create GitHub repo: `gh repo create ltvspot/alexandria-cover-designer --private`
2. Push: `git remote add origin ... && git push -u origin main`
3. Deploy to Railway: `railway init && railway up`
