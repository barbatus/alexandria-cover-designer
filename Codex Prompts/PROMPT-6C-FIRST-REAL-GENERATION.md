# Prompt 6C — First Real Generation Test + Compositing Verification

Read `Project state Alexandria Cover designer.md` for full context.

## What exists

- Full pipeline (src/ — 12 modules), webapp (quality_review.py), Docker deployment (6B)
- API keys should now be configured in `.env`
- 99 books cataloged with 495 prompts ready
- Provider selector and test-connection button on iterate page (6A)
- Dockerfile and Railway config (6B)

## Task 1: Verify API keys are configured

Run `python3 src/pipeline.py --test-api-keys` and confirm at least ONE provider shows KEY VALID.

If NO keys are valid, STOP and report. Tim needs to configure `.env` first.

## Task 2: Single book test — Book #2 (Moby Dick)

Run the full pipeline for ONE book with ONE model and 3 variants.

First dry run:
```bash
python3 src/pipeline.py --book 2 --variants 3 --dry-run
```

Verify the dry run output looks correct (shows what would be generated), then run for real:
```bash
python3 src/pipeline.py --book 2 --variants 3
```

Check:
1. 3 images generated in `tmp/generated/2/`
2. Images are actual AI-generated illustrations (not blank/placeholder), 1024×1024 pixels
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
1. `GET /api/iterate-data` returns books, models, providers, style anchors
2. `POST /api/generate` with `{"book": 2, "variants": 2, "models": [...], "provider": "openrouter"}` triggers real generation
3. Response includes image paths that exist on disk
4. `GET /api/history?book=2` shows the generation history
5. `POST /api/test-connection` with `{"provider": "openrouter"}` returns valid status

## Task 5: Visual verification

For EACH generated cover:
1. Open the composited .jpg
2. Verify: illustration sits INSIDE the gold frame (not overlapping it)
3. Verify: everything OUTSIDE the medallion is pixel-identical to the original cover
4. Verify: no visible seam at the circle edge
5. Verify: the illustration is thematically relevant to the book (not random/abstract)
6. Verify: .pdf opens correctly, full resolution
7. Verify: .ai file is a valid PDF-based file

## Task 6: Clean up old mock data

Delete the old mock/placeholder images from the previous Codex test runs:
- Remove old files in `tmp/generated/` from before this real generation
- Remove old files in `Output Covers/` that were generated with mock images (the ones with geometric/abstract patterns)
- Keep ONLY the new real AI-generated outputs
- Update `data/generation_history.json` to only contain real generation records

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
11. Webapp `/api/generate` triggers real generation — PASS/FAIL
12. `/api/history` shows generation records — PASS/FAIL
13. .pdf file opens correctly — PASS/FAIL
14. .ai file is valid — PASS/FAIL
15. Old mock data cleaned up — PASS/FAIL

Run every check. Report PASS/FAIL for each. Include file sizes and image dimensions in your report.

**IMPORTANT**: If generation fails due to API errors, document the exact error message and which provider/model caused it. Do NOT retry endlessly — report after 3 failures per provider.

Save output to `Codex Output Answers/PROMPT-6C-OUTPUT.md`.
