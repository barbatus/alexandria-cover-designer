"""Prompt 4B Google Drive sync with API mode and local fallback mode."""

from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import shutil
from pathlib import Path
from typing import Any

try:
    from google.oauth2 import service_account  # type: ignore
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    from googleapiclient.discovery import build  # type: ignore
    from googleapiclient.http import MediaFileUpload  # type: ignore

    GOOGLE_API_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    GOOGLE_API_AVAILABLE = False

try:
    from src import config
except ModuleNotFoundError:  # pragma: no cover
    import config  # type: ignore


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]
SYNC_STATE_PATH = config.DATA_DIR / "gdrive_sync_state.json"


def authenticate(credentials_path: Path):
    """Authenticate to Google Drive API using service account or OAuth client JSON."""
    if not GOOGLE_API_AVAILABLE:
        raise RuntimeError(
            "Google Drive dependencies are not installed. Install: "
            "google-api-python-client, google-auth-oauthlib, google-auth-httplib2"
        )

    if not credentials_path.exists():
        raise FileNotFoundError(f"Credentials file not found: {credentials_path}")

    payload = json.loads(credentials_path.read_text(encoding="utf-8"))
    if payload.get("type") == "service_account":
        creds = service_account.Credentials.from_service_account_file(str(credentials_path), scopes=SCOPES)
        return build("drive", "v3", credentials=creds)

    # OAuth desktop flow fallback.
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)
    return build("drive", "v3", credentials=creds)


def sync_to_drive(
    local_output_dir: Path,
    drive_folder_id: str,
    credentials_path: Path,
    incremental: bool = True,
) -> dict[str, Any]:
    """Sync local output structure to Google Drive (or local fallback mirror)."""
    if drive_folder_id.startswith("local:"):
        mirror_dir = Path(drive_folder_id.split("local:", 1)[1])
        return _sync_to_local_mirror(local_output_dir, mirror_dir, incremental)

    service = authenticate(credentials_path)
    state = _load_sync_state()

    summary = {
        "mode": "google_api",
        "uploaded": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
    }

    if not local_output_dir.exists():
        raise FileNotFoundError(f"Local output directory not found: {local_output_dir}")

    folder_cache: dict[tuple[str, str], str] = {}

    files = [path for path in local_output_dir.rglob("*") if path.is_file()]
    total = len(files)

    for index, file_path in enumerate(files, start=1):
        rel = file_path.relative_to(local_output_dir)
        try:
            parent_id = drive_folder_id
            for part in rel.parts[:-1]:
                parent_id = _ensure_remote_folder(
                    service=service,
                    parent_id=parent_id,
                    folder_name=part,
                    cache=folder_cache,
                )

            logger.info("[%d/%d] Uploading %s", index, total, rel)
            outcome = _upload_file(
                service=service,
                parent_id=parent_id,
                local_path=file_path,
                incremental=incremental,
                state=state,
            )
            summary[outcome] += 1
        except Exception as exc:  # pragma: no cover - defensive
            summary["failed"] += 1
            summary["errors"].append({"file": str(rel), "error": str(exc)})

    _save_sync_state(state)
    return summary


def get_sync_status(drive_folder_id: str, credentials_path: Path) -> dict[str, Any]:
    """Get sync status for Google Drive or local mirror fallback."""
    if drive_folder_id.startswith("local:"):
        mirror_dir = Path(drive_folder_id.split("local:", 1)[1])
        return {
            "mode": "local_mirror",
            "mirror_dir": str(mirror_dir),
            "file_count": len(list(mirror_dir.rglob("*"))) if mirror_dir.exists() else 0,
        }

    service = authenticate(credentials_path)
    response = service.files().list(
        q=f"'{drive_folder_id}' in parents and trashed=false",
        fields="files(id, name, mimeType)",
        pageSize=1000,
    ).execute()

    files = response.get("files", [])
    return {
        "mode": "google_api",
        "drive_folder_id": drive_folder_id,
        "item_count": len(files),
        "folders": sum(1 for row in files if row.get("mimeType") == "application/vnd.google-apps.folder"),
        "files": sum(1 for row in files if row.get("mimeType") != "application/vnd.google-apps.folder"),
    }


def _sync_to_local_mirror(local_output_dir: Path, mirror_dir: Path, incremental: bool) -> dict[str, Any]:
    mirror_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "mode": "local_mirror",
        "uploaded": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
    }

    files = [path for path in local_output_dir.rglob("*") if path.is_file()]
    total = len(files)

    for idx, source in enumerate(files, start=1):
        rel = source.relative_to(local_output_dir)
        target = mirror_dir / rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            logger.info("[%d/%d] Mirroring %s", idx, total, rel)

            if incremental and target.exists() and target.stat().st_size == source.stat().st_size:
                summary["skipped"] += 1
                continue

            shutil.copy2(source, target)
            summary["uploaded"] += 1
        except Exception as exc:  # pragma: no cover - defensive
            summary["failed"] += 1
            summary["errors"].append({"file": str(rel), "error": str(exc)})

    return summary


def _ensure_remote_folder(
    *,
    service,
    parent_id: str,
    folder_name: str,
    cache: dict[tuple[str, str], str],
) -> str:
    key = (parent_id, folder_name)
    if key in cache:
        return cache[key]

    q = (
        f"name='{_escape_query(folder_name)}' and '{parent_id}' in parents "
        "and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    resp = service.files().list(q=q, fields="files(id, name)", pageSize=1).execute()
    files = resp.get("files", [])
    if files:
        folder_id = files[0]["id"]
        cache[key] = folder_id
        return folder_id

    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = service.files().create(body=metadata, fields="id").execute()
    folder_id = created["id"]
    cache[key] = folder_id
    return folder_id


def _upload_file(*, service, parent_id: str, local_path: Path, incremental: bool, state: dict[str, Any]) -> str:
    rel_key = str(local_path)
    mime_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"

    q = (
        f"name='{_escape_query(local_path.name)}' and '{parent_id}' in parents "
        "and trashed=false"
    )
    existing = service.files().list(q=q, fields="files(id, name, size)", pageSize=1).execute().get("files", [])

    if existing:
        remote = existing[0]
        if incremental and str(local_path.stat().st_size) == str(remote.get("size", "")):
            return "skipped"

        media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=False)
        service.files().update(fileId=remote["id"], media_body=media).execute()
        state[rel_key] = {"id": remote["id"], "size": local_path.stat().st_size}
        return "uploaded"

    metadata = {"name": local_path.name, "parents": [parent_id]}
    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=False)
    created = service.files().create(body=metadata, media_body=media, fields="id").execute()
    state[rel_key] = {"id": created["id"], "size": local_path.stat().st_size}
    return "uploaded"


def _escape_query(value: str) -> str:
    return value.replace("'", "\\'")


def _load_sync_state() -> dict[str, Any]:
    if not SYNC_STATE_PATH.exists():
        return {}
    try:
        return json.loads(SYNC_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_sync_state(state: dict[str, Any]) -> None:
    SYNC_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYNC_STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prompt 4B Google Drive sync")
    parser.add_argument("--local-output-dir", type=Path, default=config.OUTPUT_DIR)
    parser.add_argument("--drive-folder-id", type=str, default=config.GDRIVE_OUTPUT_FOLDER_ID)
    parser.add_argument("--credentials-path", type=Path, default=Path(config.GOOGLE_CREDENTIALS_PATH or "credentials.json"))
    parser.add_argument("--no-incremental", action="store_true")
    parser.add_argument("--status", action="store_true")

    args = parser.parse_args()

    try:
        if args.status:
            status = get_sync_status(args.drive_folder_id, args.credentials_path)
            print(json.dumps(status, indent=2))
            return 0

        summary = sync_to_drive(
            local_output_dir=args.local_output_dir,
            drive_folder_id=args.drive_folder_id,
            credentials_path=args.credentials_path,
            incremental=not args.no_incremental,
        )
        print(json.dumps(summary, indent=2))
        return 0 if summary.get("failed", 0) == 0 else 1
    except Exception as exc:  # pragma: no cover - CLI boundary
        logger.error("Sync failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
