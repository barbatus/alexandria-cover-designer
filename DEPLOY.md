# Deployment Guide

## Local Docker
1. Copy `.env.example` to `.env` and set required variables.
2. Build and start:
```bash
docker compose up -d --build
```
3. Verify:
- Health: `http://localhost:8001/api/health`
- Iterate page: `http://localhost:8001/iterate`
- Review page: `http://localhost:8001/review`

## Railway Deployment
1. Create a Railway project.
2. Connect your GitHub repo.
3. Ensure Railway uses the included `Dockerfile` (also configured in `railway.toml`).
4. Add environment variables from the table below.
5. Deploy.
6. Verify health endpoint: `https://<your-railway-domain>/api/health`.

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `AI_PROVIDER` | Yes | Default provider for generation (`openrouter`, `openai`, etc.) |
| `AI_MODEL` | Yes | Default model used by pipeline |
| `ALL_MODELS` | Optional | Comma-separated models used by all-model mode |
| `OPENROUTER_API_KEY` | Required if using OpenRouter | OpenRouter API key |
| `OPENAI_API_KEY` | Required if using OpenAI | OpenAI API key |
| `GOOGLE_API_KEY` | Required if using Google | Google Generative API key |
| `FAL_API_KEY` | Required if using fal.ai | fal.ai API key |
| `REPLICATE_API_TOKEN` | Required if using Replicate | Replicate API token |
| `INPUT_DIR` | Optional | Input cover directory (default `Input Covers`) |
| `OUTPUT_DIR` | Optional | Output cover directory (default `Output Covers`) |
| `TMP_DIR` | Optional | Temp directory (default `tmp`) |
| `DATA_DIR` | Optional | Data directory (default `data`) |
| `CONFIG_DIR` | Optional | Config directory (default `config`) |
| `MIN_QUALITY_SCORE` | Optional | Quality threshold |
| `BOOK_SCOPE_LIMIT` | Optional | Default initial scope size |
| `MAX_EXPORT_VARIANTS` | Optional | Export fallback variant cap |
| `GDRIVE_OUTPUT_FOLDER_ID` | Optional | Google Drive target folder id |
| `GOOGLE_CREDENTIALS_PATH` | Optional | Drive OAuth/service credentials path |
| `HOST` | Optional | Bind host for web server (default `0.0.0.0`) |
| `PORT` | Optional | Web server port (default `8001`) |

## Google Drive Sync Setup

### OAuth / service credentials flow
1. Go to Google Cloud Console.
2. Enable **Google Drive API** for the project.
3. Create credentials:
- OAuth 2.0 Client ID (Desktop app), or
- Service Account JSON.
4. Save JSON as `config/credentials.json` (or set `GOOGLE_CREDENTIALS_PATH`).
5. Run sync:
```bash
python3 -m src.gdrive_sync --local-output-dir "Output Covers" --drive-folder-id "$GDRIVE_OUTPUT_FOLDER_ID" --credentials-path config/credentials.json
```

### rclone fallback
Use when OAuth setup is blocked/unavailable. Configure an `rclone` Google Drive remote named `gdrive`, then run:
```bash
bash scripts/rclone_sync.sh
```

## Which sync method to use
- Use `src.gdrive_sync` when you have Google credentials and want native API-based incremental sync.
- Use `scripts/rclone_sync.sh` when native OAuth setup is unavailable or blocked.
