# PROMPT-6A Output — Bug Fix + Real Generation Prep

## Summary of Work Completed

Implemented all requested code changes across:
- `/Users/timzengerink/Documents/Coding Folder/Alexandria Cover designer/src/config.py`
- `/Users/timzengerink/Documents/Coding Folder/Alexandria Cover designer/src/output_exporter.py`
- `/Users/timzengerink/Documents/Coding Folder/Alexandria Cover designer/src/image_generator.py`
- `/Users/timzengerink/Documents/Coding Folder/Alexandria Cover designer/src/pipeline.py`
- `/Users/timzengerink/Documents/Coding Folder/Alexandria Cover designer/scripts/quality_review.py`
- `/Users/timzengerink/Documents/Coding Folder/Alexandria Cover designer/src/static/iterate.html`
- `/Users/timzengerink/Documents/Coding Folder/Alexandria Cover designer/.env.example`

---

## Task 1 — Fixed `output_exporter.py` hardcoded variant cap

### Changes
- Added new config field `MAX_EXPORT_VARIANTS` (env) with default `20` in `src/config.py`.
- Added dataclass field `max_export_variants` to runtime config.
- Replaced hardcoded fallback cap in exporter logic with configurable limit.
- Added optional `max_variants` override parameter to:
  - `export_book_variants(...)`
  - `batch_export(...)`
  - `_fallback_collect_variant_images(...)`
- Added CLI flag `--max-variants` in `src/output_exporter.py` to override limit at runtime.

Result: no more hardcoded `5` in fallback export path.

---

## Task 2 — Provider integration verification and code updates

### OpenRouter
- Updated generation endpoint to `POST /api/v1/chat/completions` with `modalities: ["image"]`.
- Preserved `Authorization: Bearer` auth.
- Added response parsing for `choices[0].message.images[].image_url.url` data URLs/HTTP URLs.
- Kept backward-compatible fallback parsing for legacy OpenAI-style image payloads.

### OpenAI
- Kept `POST https://api.openai.com/v1/images/generations` with `Authorization: Bearer`.
- Existing response extraction (`b64_json`) retained.

### Replicate
- Updated auth to `Authorization: Bearer`.
- Updated predictions payload from `model` to `version` (current Predictions API pattern).
- Improved output parsing to handle list items that can be URL strings or dicts.

### fal.ai
- Kept `POST https://fal.run/{model}` with `Authorization: Key ...`.
- Existing URL extraction remains valid.

### Google
- Kept `:generateContent` image flow and updated auth to `x-goog-api-key` header.
- Added one retry path when width/height `imageConfig` is rejected by a model.
- Added broader response parsing (`inlineData` + alternate generated image shapes).

### References used for verification
- [OpenRouter image generation docs](https://openrouter.ai/docs/features/multimodal/image-generation)
- [OpenRouter OpenAI compatibility docs](https://openrouter.ai/docs/api-reference/overview)
- [OpenAI Images API docs](https://platform.openai.com/docs/api-reference/images)
- [Replicate Predictions API docs](https://replicate.com/docs/reference/http)
- [fal.ai model endpoints docs](https://docs.fal.ai/model-apis/model-endpoints)
- [Google Gemini image generation docs](https://ai.google.dev/gemini-api/docs/image-generation)
- [Google API key auth docs](https://ai.google.dev/gemini-api/docs/api-key)

---

## Task 3 — `.env.example` coverage

- Rebuilt `.env.example` so every `os.getenv(...)` key used in code is present.
- Verified by script: `MISSING []`, `EXTRA []`.

---

## Task 4 — Added `--test-api-keys` to pipeline

### Changes
- Added `--test-api-keys` CLI flag to `src/pipeline.py`.
- Added reusable function `test_api_keys(...)` returning per-provider statuses:
  - `KEY_VALID`
  - `KEY_INVALID`
  - `KEY_MISSING`
- Implemented low-cost health/account/model-list probes (no image generation) for:
  - OpenRouter
  - OpenAI
  - Replicate
  - fal.ai
  - Google
- Supports optional provider filter via existing `--provider`.

### Runtime check result
- Command executed: `python3 src/pipeline.py --test-api-keys`
- Output:
  - `OPENROUTER — KEY_VALID — HTTP 200`
  - `OPENAI — KEY_VALID — HTTP 200`
  - `REPLICATE — KEY_MISSING — No key configured.`
  - `FAL — KEY_MISSING — No key configured.`
  - `GOOGLE — KEY_VALID — HTTP 200`

---

## Task 5 — Iterate page provider controls + connection test

### Changes in `/iterate`
- Added provider dropdown with providers:
  - `openrouter`, `openai`, `replicate`, `fal`, `google` (+ `all` aggregate)
- Added model-list filtering based on selected provider.
- Added `Test Connection` button calling backend endpoint `/api/test-connection`.
- Added provider status line showing per-provider key test result.
- Added provider to generation payload and wired backend to pass `provider_override`.

### Backend wiring
- `scripts/quality_review.py` now:
  - Emits `providers` + `provider_models` in `/api/iterate-data`.
  - Handles `POST /api/test-connection` by calling `pipeline.test_api_keys(...)`.
  - Accepts `provider` in `POST /api/generate` and passes provider override.

---

## Verification Checklist (Required)

1. `py_compile` passes for all modified files — **PASS**
2. `output_exporter.py` no longer has hardcoded `5` cap — **PASS**
3. New `max_export_variants` config field exists with default 20 — **PASS**
4. All 5 providers have correct endpoint URLs verified — **PASS**
5. All 5 providers have correct auth header format — **PASS**
6. `.env.example` has every env var referenced in code — **PASS**
7. `python3 src/pipeline.py --test-api-keys` runs without crash — **PASS**
8. `/iterate` page has provider selector — **PASS**
9. All existing imports still work after changes — **PASS**
10. `pytest tests/test_unit.py` still passes — **PASS**

---

## Commands Executed for Verification

- `python3 -m py_compile src/config.py src/output_exporter.py src/image_generator.py src/pipeline.py scripts/quality_review.py`
- `python3 src/pipeline.py --test-api-keys`
- `python3 src/pipeline.py --test-api-keys --provider openrouter`
- `python3 - <<'PY' ...` (env var coverage check)
- `python3 - <<'PY' ...` (import smoke test)
- `pytest tests/test_unit.py`
