# Prompt 6A — Bug Fix + Real Generation Preparation

Read `Project state Alexandria Cover designer.md` for full context, especially decisions D19-D23.

## Context

All 9 prompts (1A through 5) have been completed. The full pipeline exists:
- `src/cover_analyzer.py` — region detection
- `src/prompt_generator.py` — prompt engineering (495 prompts for 99 books)
- `src/image_generator.py` — multi-provider AI generation
- `src/prompt_library.py` — prompt library with style anchors
- `src/quality_gate.py` — automated quality scoring
- `src/cover_compositor.py` — compositing into covers
- `src/output_exporter.py` — export to .jpg/.pdf/.ai
- `src/pipeline.py` — end-to-end orchestrator
- `src/gdrive_sync.py` — Google Drive upload
- `src/archiver.py` — archive management
- `scripts/quality_review.py` — QA webapp
- `scripts/generate_catalog.py` — catalog PDF

The pipeline was tested with mock/placeholder images. Now we need to prepare for REAL AI image generation with actual API keys.

## Task 1: Fix output_exporter.py variant cap (BUG)

In `src/output_exporter.py`, around line 200, there is a hardcoded cap:

```python
if len(selected) >= 5:
    break
```

This contradicts Tim's decision D22 (configurable variation count — generate 5, 10, 20+ variants).

**Fix:** Replace the hardcoded `5` with a configurable value from `src/config.py`. Add a new config field `max_export_variants` defaulting to `20`. The function should accept an optional `max_variants` parameter that overrides the config default.

## Task 2: Verify all API provider integrations are properly coded

Check each provider in `src/image_generator.py` and verify:

1. **OpenRouter** — correct endpoint URL, proper auth header (`Authorization: Bearer`), correct request format for image generation models (FLUX 2 Pro, etc.)
2. **OpenAI** — correct endpoint for GPT Image 1 (`/v1/images/generations`), proper auth
3. **Replicate** — correct SDK usage for `replicate.run()`, proper model version strings
4. **fal.ai** — correct endpoint format, proper auth header
5. **Google Cloud** — correct Imagen 4 / Nano Banana endpoint, proper auth

For each provider, verify:
- The API endpoint URL is correct and current (February 2026)
- The authentication header format is correct
- The request/response parsing handles the actual API response format
- Error handling catches common API errors (rate limits, auth failures, model not found)
- The response correctly extracts the image bytes/URL

**Do NOT call any real APIs.** Just verify the code is correctly structured for when real keys are provided.

## Task 3: Verify .env.example has all required keys

Check `.env.example` against every `os.getenv()` call in the codebase. Ensure no env vars are referenced in code but missing from `.env.example`.

## Task 4: Add a --test-api-keys flag to pipeline.py

Add a `--test-api-keys` CLI flag that:
1. Reads `.env`
2. For each configured provider, makes a minimal API call (e.g., a tiny 64×64 test generation or an API health check)
3. Reports: PROVIDER — KEY VALID / KEY INVALID / KEY MISSING
4. Does NOT generate any real images or incur significant cost

This lets Tim verify his API keys work before running the full pipeline.

## Task 5: Add --provider flag to iterate page

The `/iterate` webapp page should allow selecting which provider to use (not just which model). Verify the iterate.html has:
- Provider dropdown (openrouter, openai, replicate, fal, google)
- Model list updates based on selected provider
- "Test Connection" button that calls the --test-api-keys logic for that provider

If any of these are missing, add them.

## Verification Checklist

1. `py_compile` passes for all modified files — PASS/FAIL
2. `output_exporter.py` no longer has hardcoded `5` cap — PASS/FAIL
3. New `max_export_variants` config field exists with default 20 — PASS/FAIL
4. All 5 providers have correct endpoint URLs verified — PASS/FAIL
5. All 5 providers have correct auth header format — PASS/FAIL
6. `.env.example` has every env var referenced in code — PASS/FAIL
7. `python3 src/pipeline.py --test-api-keys` runs without crash (keys will fail, that's OK) — PASS/FAIL
8. `/iterate` page has provider selector — PASS/FAIL
9. All existing imports still work after changes — PASS/FAIL
10. `pytest tests/test_unit.py` still passes — PASS/FAIL

Run every check. Report PASS/FAIL for each.

Save your output to `Codex Output Answers/PROMPT-6A-OUTPUT.md`.
