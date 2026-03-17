"""Batch cover compositor — orchestrates single and multi-variant compositing.

Supports two compositing modes:
  - "pil": deterministic PIL alpha-blend using PDF template SMask (default).
  - "llm": LLM-based blending  for art replacement.

"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from src import config, safe_json
from src.cover.llm_composite import llm_composite
from src.cover.pil_composite import pil_composite
from src.logger import get_logger

logger = get_logger(__name__)

EXPECTED_COVER_SIZE = (3784, 2777)
EXPECTED_DPI = 300


def composite(
    *,
    source_pdf_path: Path,
    ai_art_paths: list[Path],
    output_jpg_paths: list[Path],
    shape: str = "circle",
    mode: Literal["pil" | "llm"] = "pil",
    center: tuple[int, int] | None = None,
    width: int = 0,
    height: int = 0,
) -> dict[str, Any]:
    if mode == "llm":
        if center is None:
            raise ValueError("center is required for llm mode")
        llm_composite(
            book_cover_pdf_path=source_pdf_path,
            ai_art_paths=ai_art_paths,
            output_jpg_paths=output_jpg_paths,
            center=center,
            width=width,
            height=height,
        )
    else:
        pil_composite(
            source_pdf_path=source_pdf_path,
            ai_art_paths=ai_art_paths,
            output_jpg_paths=output_jpg_paths,
            shape=shape,
        )

    return {
        "success": True,
        "output_jpgs": [str(p) for p in output_jpg_paths],
        "mode": mode,
    }


def composite_all_variants(
    *,
    book_number: int,
    input_dir: Path,
    generated_dir: Path,
    output_dir: Path,
    catalog_path: Path = config.BOOK_CATALOG_PATH,
    shape: str = "circle",
) -> list[Path]:
    """Composite all generated variants for one book."""
    source_pdf = _find_source_pdf_for_book(input_dir, book_number, catalog_path)
    if source_pdf is None:
        raise FileNotFoundError(f"No source PDF found for book {book_number}")

    image_rows = _collect_generated_for_book(generated_dir, book_number)
    if not image_rows:
        raise FileNotFoundError(f"No generated variants for book {book_number}")

    art_paths: list[Path] = []
    outputs: list[Path] = []
    report_items: list[dict[str, Any]] = []

    for row in image_rows:
        model = str(row["model"])
        variant = int(row["variant"])

        if model == "default":
            out_jpg = output_dir / str(book_number) / f"variant_{variant}.jpg"
        else:
            out_jpg = output_dir / str(book_number) / model / f"variant_{variant}.jpg"

        art_paths.append(row["path"])
        outputs.append(out_jpg)
        report_items.append(
            {
                "output_path": str(out_jpg),
                "valid": True,
                "issues": [],
                "mode": "pil_composite",
                "variant": variant,
                "model": model,
            }
        )

    composite(
        source_pdf_path=source_pdf,
        ai_art_paths=art_paths,
        output_jpg_paths=outputs,
        shape=shape,
    )

    report = {
        "book_number": int(book_number),
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(report_items),
        "invalid": 0,
        "items": report_items,
    }
    report_path = output_dir / str(book_number) / "composite_validation.json"
    safe_json.atomic_write_json(report_path, report)

    logger.info(
        "Composited %d variants for book %d via PDF insert",
        len(outputs),
        book_number,
    )
    return outputs


def _find_source_pdf_for_book(
    input_dir: Path, book_number: int, catalog_path: Path
) -> Path | None:
    """Find the source PDF template for a book from the catalog."""
    catalog = safe_json.load_json(catalog_path, [])
    if not isinstance(catalog, list):
        return None
    for entry in catalog:
        if not isinstance(entry, dict):
            continue
        try:
            num = int(entry.get("number", 0))
        except (TypeError, ValueError):
            continue
        if num == book_number:
            folder_name = str(entry.get("folder_name", "")).strip()
            if not folder_name:
                continue
            folder = input_dir / folder_name
            if folder.exists():
                pdfs = sorted(p for p in folder.glob("*.pdf") if p.is_file())
                if pdfs:
                    return pdfs[0]
                ais = sorted(p for p in folder.glob("*.ai") if p.is_file())
                if ais:
                    return ais[0]
    return None


def _collect_generated_for_book(
    generated_dir: Path, book_number: int
) -> list[dict[str, Any]]:
    """Gather all generated variant images for a book, deduped by (model, variant)."""
    base = generated_dir / str(book_number)
    if not base.exists():
        return []

    rows: list[dict[str, Any]] = []
    exts = {".png", ".jpg", ".jpeg", ".webp"}

    for model_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        if model_dir.name == "history":
            continue
        for img in sorted(model_dir.glob("variant_*.*")):
            if img.suffix.lower() in exts:
                rows.append(
                    {
                        "model": model_dir.name,
                        "variant": _parse_variant(img.stem),
                        "path": img,
                    }
                )

    for img in sorted(base.glob("variant_*.*")):
        if img.suffix.lower() in exts:
            rows.append(
                {
                    "model": "default",
                    "variant": _parse_variant(img.stem),
                    "path": img,
                }
            )

    dedup: dict[tuple[str, int], dict[str, Any]] = {}
    for r in rows:
        dedup[(r["model"], r["variant"])] = r
    return sorted(dedup.values(), key=lambda r: (r["model"], r["variant"]))


def _parse_variant(stem: str) -> int:
    if "variant_" not in stem:
        return 0
    token = stem.split("variant_", 1)[1].split("_", 1)[0]
    try:
        return int(token)
    except ValueError:
        return 0
