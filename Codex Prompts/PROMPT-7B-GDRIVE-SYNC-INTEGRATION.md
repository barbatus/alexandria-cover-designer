# Prompt 7B — Google Drive Sync + Final Integration

Read `Project state Alexandria Cover designer.md` for full context.

## What exists

- 20 books with real AI-generated covers in `Output Covers/`
- `src/gdrive_sync.py` exists but hasn't been tested with real credentials
- Target Drive folder: https://drive.google.com/drive/folders/1Vr184ZsX3k38xpmZkd8g2vwB5y9LYMRC
- Webapp deployed with /iterate and /review pages
- Quality report and model rankings generated

## Task 1: Test Google Drive authentication

1. Check if `config/credentials.json` exists (OAuth2 client credentials)
2. If missing: document the exact steps Tim needs to create it:
   - Go to Google Cloud Console → APIs & Services → Enable Drive API
   - Create OAuth 2.0 credentials → Desktop App
   - Download JSON → save as `config/credentials.json`
   - First run will open browser for consent
3. If present: run the auth flow and verify it works
4. Upload 1 test file from `Output Covers/` book #1 variant 1 to the target Drive folder
5. Verify: file appears in Drive, correct name

## Task 2: Folder structure sync

Upload all variants for book #2 to Drive:
- Create folder: `Output Covers/2. Moby Dick.../Variant-1/` etc. in Drive
- Upload .jpg, .pdf, .ai for each variant
- Verify folder structure matches local

## Task 3: Bulk sync for 20 books

Upload all Output Covers for the 20 generated books:

```bash
python3 -m src.gdrive_sync --input "Output Covers" --drive-folder-id 1Vr184ZsX3k38xpmZkd8g2vwB5y9LYMRC
```

Report:
- Files uploaded count
- Files skipped (already exist) count
- Any failures and their errors
- Total upload time

## Task 4: Resume test

Re-run the same upload command. It should skip ALL files that were already uploaded:

```bash
python3 -m src.gdrive_sync --input "Output Covers" --drive-folder-id 1Vr184ZsX3k38xpmZkd8g2vwB5y9LYMRC
```

Verify: 0 new uploads, all skipped.

## Task 5: Pipeline --sync flag

Add a `--sync` flag to `pipeline.py` that automatically uploads to Drive after generation:

```bash
python3 src/pipeline.py --book 1 --variants 3 --sync
```

This should:
1. Run the full pipeline: Generate → Quality Gate → Composite → Export
2. After export, upload the output files to Drive
3. Only upload variants that pass the quality gate (score ≥ threshold)
4. Report upload status at the end

## Task 6: Add sync button to webapp

In `scripts/quality_review.py`, add:
1. `POST /api/sync-to-drive` endpoint that uploads all selected (winner) variants to Drive
2. Show upload progress in the response

In `src/static/review.html`, add:
1. "Sync Winners to Drive" button next to "Save Selections" button
2. When clicked, sends selected variants to `/api/sync-to-drive`
3. Shows progress/result message

## Task 7: rclone fallback script

If Google OAuth setup is not available (no credentials.json), create `scripts/rclone_sync.sh`:

```bash
#!/bin/bash
# Requires: rclone configured with Google Drive remote named "gdrive"
# Setup: rclone config → New remote → Google Drive → follow prompts
rclone copy "Output Covers/" "gdrive:Alexandria Publishing/Output Covers/" \
  --include "*.jpg" --include "*.pdf" --include "*.ai" \
  --progress --transfers 4
```

Update `DEPLOY.md` with:
- Google Drive OAuth setup instructions
- rclone alternative setup instructions
- Which method to use when

## Verification Checklist

1. Google Drive auth works (OAuth or service account) — PASS/FAIL (or SKIPPED + instructions documented)
2. Single file upload to Drive succeeds — PASS/FAIL
3. Folder structure created correctly in Drive — PASS/FAIL
4. All 3 file types upload (.jpg, .pdf, .ai) — PASS/FAIL
5. Resume skips already-uploaded files — PASS/FAIL
6. Bulk sync for 20 books completes — PASS/FAIL
7. `--sync` flag works in pipeline.py — PASS/FAIL
8. "Sync Winners to Drive" button on /review page — PASS/FAIL
9. `/api/sync-to-drive` endpoint works — PASS/FAIL
10. rclone fallback script exists and is documented — PASS/FAIL
11. `DEPLOY.md` updated with Drive sync instructions — PASS/FAIL
12. Upload progress reported during bulk sync — PASS/FAIL

Run every check. Report PASS/FAIL for each.

Save output to `Codex Output Answers/PROMPT-7B-OUTPUT.md`.
