#!/usr/bin/env python3
"""Batch re-composite existing generated illustrations with current compositor code."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src import config
    from src import cover_compositor
    from src import safe_json
except ModuleNotFoundError:  # pragma: no cover
    import config  # type: ignore
    import cover_compositor  # type: ignore
    import safe_json  # type: ignore


FALLBACK_REGION: dict[str, Any] = {
    "center_x": 2864,
    "center_y": 1620,
    "radius": 500,
    "frame_bbox": [0, 0, 0, 0],
    "region_type": "circle",
}

VARIANT_PATTERN = re.compile(r"variant_(\d+)$", re.IGNORECASE)
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(slots=True)
class GeneratedVariant:
    book_number: int
    model: str
    variant: int
    path: Path


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_project_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def _load_catalog(runtime: config.Config) -> list[dict[str, Any]]:
    rows = safe_json.load_json(runtime.book_catalog_path, [])
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        number = _safe_int(row.get("number"), 0)
        if number <= 0:
            continue
        out.append(
            {
                "number": number,
                "title": str(row.get("title", f"Book {number}")),
                "folder_name": str(row.get("folder_name", "")).strip(),
            }
        )
    out.sort(key=lambda row: int(row["number"]))
    return out


def _find_cover_path(*, input_dir: Path, folder_name: str) -> Path | None:
    folder = input_dir / folder_name
    if not folder.exists() or not folder.is_dir():
        return None
    preferred = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg"}]
    if preferred:
        preferred.sort()
        return preferred[0]
    fallback = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    if fallback:
        fallback.sort()
        return fallback[0]
    return None


def _discover_generated_variants(generated_dir: Path) -> dict[int, list[GeneratedVariant]]:
    by_book: dict[int, list[GeneratedVariant]] = {}
    if not generated_dir.exists() or not generated_dir.is_dir():
        return by_book
    for book_dir in sorted(generated_dir.iterdir(), key=lambda p: _safe_int(p.name, 0)):
        if not book_dir.is_dir() or not book_dir.name.isdigit():
            continue
        book_number = int(book_dir.name)
        rows: list[GeneratedVariant] = []
        for model_dir in sorted(book_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            model = str(model_dir.name).strip() or "default"
            for candidate in sorted(model_dir.iterdir()):
                if not candidate.is_file() or candidate.suffix.lower() not in IMAGE_EXTS:
                    continue
                match = VARIANT_PATTERN.match(candidate.stem)
                if not match:
                    continue
                variant = _safe_int(match.group(1), 0)
                if variant <= 0:
                    continue
                rows.append(
                    GeneratedVariant(
                        book_number=book_number,
                        model=model,
                        variant=variant,
                        path=candidate,
                    )
                )
        rows.sort(key=lambda row: (row.model, row.variant, str(row.path)))
        if rows:
            by_book[book_number] = rows
    return by_book


def _validation_path(output_path: Path) -> Path:
    return output_path.with_suffix(output_path.suffix + ".validation.json")


def _frame_ok_from_validation(output_path: Path) -> tuple[bool, dict[str, Any]]:
    payload = safe_json.load_json(_validation_path(output_path), {})
    if not isinstance(payload, dict):
        return False, {"error": "validation payload missing"}
    metrics = payload.get("metrics", {}) if isinstance(payload.get("metrics"), dict) else {}
    frame_max_delta = float(metrics.get("frame_pixel_max_delta", 9999.0))
    frame_mean_delta = float(metrics.get("frame_pixel_mean_delta", 9999.0))
    issues = payload.get("issues", []) if isinstance(payload.get("issues"), list) else []
    frame_issue = any(str(issue) == "frame_pixels_changed" for issue in issues)
    frame_ok = (frame_max_delta <= 3.0) and (not frame_issue)
    return frame_ok, {
        "frame_pixel_max_delta": frame_max_delta,
        "frame_pixel_mean_delta": frame_mean_delta,
        "issues": [str(item) for item in issues if str(item).strip()],
    }


def run_batch_recomposite(
    *,
    runtime: config.Config,
    generated_dir: Path,
    output_dir: Path,
    catalog_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    cover_compositor.ensure_frame_overlays_exist(input_dir=runtime.input_dir, catalog_path=runtime.book_catalog_path)

    variants_by_book = _discover_generated_variants(generated_dir)
    total_catalog = len(catalog_rows)
    generated_books = len(variants_by_book)

    summary: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "catalog_id": runtime.catalog_id,
        "catalog_total_books": total_catalog,
        "books_with_illustrations": generated_books,
        "recomposited_books": 0,
        "passed_frame_check": 0,
        "failed_frame_check": 0,
        "failed_books": [],
        "skipped_no_illustration": 0,
        "variant_success": 0,
        "variant_failures": 0,
        "book_details": [],
    }

    for index, row in enumerate(catalog_rows, start=1):
        book_number = int(row["number"])
        title = str(row["title"])
        folder_name = str(row.get("folder_name", "")).strip()
        variants = variants_by_book.get(book_number, [])
        if not variants:
            summary["skipped_no_illustration"] = int(summary["skipped_no_illustration"]) + 1
            continue

        if index == 1 or index % 10 == 0 or index == total_catalog:
            print(f"[{index}/{total_catalog}] Processing book {book_number}: {title}")

        cover_path = _find_cover_path(input_dir=runtime.input_dir, folder_name=folder_name) if folder_name else None
        if cover_path is None:
            summary["recomposited_books"] = int(summary["recomposited_books"]) + 1
            summary["failed_frame_check"] = int(summary["failed_frame_check"]) + 1
            summary["failed_books"].append({"book_number": book_number, "error": "cover_not_found"})
            summary["book_details"].append(
                {
                    "book_number": book_number,
                    "book_title": title,
                    "status": "failed",
                    "error": "cover_not_found",
                    "variants_total": len(variants),
                    "variants_success": 0,
                    "variants_failed": len(variants),
                }
            )
            print(f"  FAIL book {book_number}: source cover not found for folder '{folder_name}'")
            continue

        book_success = 0
        book_fail = 0
        book_errors: list[str] = []
        variant_details: list[dict[str, Any]] = []
        for item in variants:
            out_path = output_dir / str(book_number) / item.model / f"variant_{item.variant}.jpg"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                cover_compositor.composite_single(
                    cover_path=cover_path,
                    illustration_path=item.path,
                    region=FALLBACK_REGION,
                    output_path=out_path,
                )
                frame_ok, info = _frame_ok_from_validation(out_path)
                if frame_ok:
                    book_success += 1
                    summary["variant_success"] = int(summary["variant_success"]) + 1
                else:
                    book_fail += 1
                    summary["variant_failures"] = int(summary["variant_failures"]) + 1
                    book_errors.append(
                        f"{item.model}/variant_{item.variant}: frame check failed "
                        f"(max_delta={float(info.get('frame_pixel_max_delta', 0.0)):.3f})"
                    )
                variant_details.append(
                    {
                        "model": item.model,
                        "variant": int(item.variant),
                        "generated_path": _to_project_relative(item.path),
                        "output_path": _to_project_relative(out_path),
                        "frame_ok": bool(frame_ok),
                        "frame_pixel_max_delta": float(info.get("frame_pixel_max_delta", 0.0)),
                        "frame_pixel_mean_delta": float(info.get("frame_pixel_mean_delta", 0.0)),
                    }
                )
            except Exception as exc:
                book_fail += 1
                summary["variant_failures"] = int(summary["variant_failures"]) + 1
                error_msg = f"{item.model}/variant_{item.variant}: {exc}"
                book_errors.append(error_msg)
                variant_details.append(
                    {
                        "model": item.model,
                        "variant": int(item.variant),
                        "generated_path": _to_project_relative(item.path),
                        "output_path": _to_project_relative(out_path),
                        "frame_ok": False,
                        "error": str(exc),
                    }
                )

        summary["recomposited_books"] = int(summary["recomposited_books"]) + 1
        if book_fail == 0:
            summary["passed_frame_check"] = int(summary["passed_frame_check"]) + 1
            status = "passed"
        else:
            summary["failed_frame_check"] = int(summary["failed_frame_check"]) + 1
            summary["failed_books"].append({"book_number": book_number, "errors": book_errors})
            status = "failed"
            print(f"  FAIL book {book_number}: {book_fail}/{len(variants)} variants failed frame check")

        summary["book_details"].append(
            {
                "book_number": book_number,
                "book_title": title,
                "status": status,
                "cover_path": _to_project_relative(cover_path),
                "variants_total": len(variants),
                "variants_success": int(book_success),
                "variants_failed": int(book_fail),
                "errors": book_errors,
                "variants": variant_details,
            }
        )

    summary["failed_books"] = sorted(
        [row for row in summary["failed_books"] if isinstance(row, dict)],
        key=lambda row: _safe_int(row.get("book_number"), 0),
    )
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    return summary


def _print_summary(summary: dict[str, Any]) -> None:
    failed_books = [_safe_int(row.get("book_number"), 0) for row in summary.get("failed_books", []) if isinstance(row, dict)]
    print("")
    print("Batch recomposite summary")
    print("=========================")
    print(f"Catalog books: {int(summary.get('catalog_total_books', 0))}")
    print(f"Books with illustrations: {int(summary.get('books_with_illustrations', 0))}")
    print(f"Re-composited: {int(summary.get('recomposited_books', 0))} books")
    print(f"Passed frame check: {int(summary.get('passed_frame_check', 0))}")
    print(f"Failed frame check: {int(summary.get('failed_frame_check', 0))}")
    print(f"Skipped (no illustration): {int(summary.get('skipped_no_illustration', 0))}")
    print(f"Variant success: {int(summary.get('variant_success', 0))}")
    print(f"Variant failures: {int(summary.get('variant_failures', 0))}")
    if failed_books:
        print(f"Failed books: {failed_books}")


def _run_cli() -> int:
    parser = argparse.ArgumentParser(description="Batch re-composite all existing generated variants")
    parser.add_argument("--catalog", default=config.DEFAULT_CATALOG_ID, help="Catalog id")
    parser.add_argument("--generated-dir", default="", help="Override generated directory")
    parser.add_argument("--output-dir", default="", help="Override composited output directory")
    parser.add_argument("--report-path", default="qa_output/classics/recomposite_summary.json", help="Write JSON summary here")
    args = parser.parse_args()

    runtime = config.get_config(args.catalog)
    generated_dir = Path(args.generated_dir).expanduser() if str(args.generated_dir).strip() else runtime.tmp_dir / "generated"
    output_dir = Path(args.output_dir).expanduser() if str(args.output_dir).strip() else runtime.tmp_dir / "composited"

    catalog_rows = _load_catalog(runtime)
    summary = run_batch_recomposite(
        runtime=runtime,
        generated_dir=generated_dir,
        output_dir=output_dir,
        catalog_rows=catalog_rows,
    )

    report_path = Path(args.report_path).expanduser()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    safe_json.atomic_write_json(report_path, summary)
    print(f"Summary report: {_to_project_relative(report_path)}")
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_cli())
