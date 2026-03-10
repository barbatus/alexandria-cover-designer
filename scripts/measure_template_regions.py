#!/usr/bin/env python3
"""Measure mixed-case tagline regions in Alexandria cover template PDFs.

This scans template PDFs, extracts text blocks via PyMuPDF, and reports the
mixed-case front-cover tagline block that appears between the uppercase
subtitle and the medallion area. The output can be emitted as JSON or a simple
table for manual inspection.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import fitz  # type: ignore


TAGLINE_VERTICAL_LIMIT_RATIO = 0.55
TAGLINE_RIGHT_COLUMN_MIN_RATIO = 0.45
TAGLINE_RIGHT_EDGE_MIN_RATIO = 0.55


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _text_is_all_caps(text: str) -> bool:
    letters = [char for char in str(text or "") if char.isalpha()]
    return bool(letters) and all(char.upper() == char for char in letters)


def _text_has_mixed_case(text: str) -> bool:
    letters = [char for char in str(text or "") if char.isalpha()]
    if len(letters) < 6:
        return False
    return any(char.islower() for char in letters) and any(char.isupper() for char in letters)


def _candidate_blocks(page: fitz.Page) -> list[dict[str, Any]]:
    page_width = float(page.rect.width)
    page_height = float(page.rect.height)
    raw_blocks = page.get_text("blocks")
    candidates: list[dict[str, Any]] = []
    for x0, y0, x1, y1, text, *_rest in raw_blocks:
        cleaned = _clean_text(text)
        if not cleaned:
            continue
        if x0 < page_width * TAGLINE_RIGHT_COLUMN_MIN_RATIO or x1 < page_width * TAGLINE_RIGHT_EDGE_MIN_RATIO:
            continue
        if y0 > page_height * TAGLINE_VERTICAL_LIMIT_RATIO:
            continue
        candidates.append(
            {
                "x0": float(x0),
                "y0": float(y0),
                "x1": float(x1),
                "y1": float(y1),
                "text": cleaned,
            }
        )
    return candidates


def _measure_tagline(pdf_path: Path) -> dict[str, Any]:
    with fitz.open(str(pdf_path)) as doc:
        if doc.page_count <= 0:
            return {"path": str(pdf_path), "status": "empty"}
        page = doc[0]
        candidates = _candidate_blocks(page)
        page_height = float(page.rect.height)
        author_candidates = [
            block
            for block in candidates
            if _text_is_all_caps(str(block["text"])) and float(block["y0"]) >= page_height * 0.38
        ]
        author_top = min((float(block["y0"]) for block in author_candidates), default=page_height * TAGLINE_VERTICAL_LIMIT_RATIO)
        matches = [
            block
            for block in candidates
            if _text_has_mixed_case(str(block["text"])) and float(block["y1"]) <= author_top
        ]
        if not matches:
            return {
                "path": str(pdf_path),
                "status": "not_found",
                "page_width": float(page.rect.width),
                "page_height": float(page.rect.height),
            }
        best = min(matches, key=lambda block: (float(block["y0"]), -float(block["x1"])))
        return {
            "path": str(pdf_path),
            "status": "ok",
            "page_width": float(page.rect.width),
            "page_height": float(page.rect.height),
            "tagline": best,
            "author_top": author_top,
        }


def _discover_pdfs(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*.pdf") if path.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        default="/Users/timzengerink/Documents/Coding Folder/Alexandria Cover designer/Input Covers",
        help="Template PDF path or directory to scan",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a plain-text table")
    args = parser.parse_args()

    source = Path(args.input).expanduser()
    pdfs = _discover_pdfs(source)
    rows = [_measure_tagline(path) for path in pdfs]

    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0

    print("status\tfile\ty0\ty1\ttext")
    for row in rows:
        tagline = row.get("tagline") if isinstance(row, dict) else None
        print(
            "\t".join(
                [
                    str(row.get("status", "")),
                    str(Path(str(row.get("path", ""))).name),
                    f"{float(tagline.get('y0', 0.0)):.1f}" if isinstance(tagline, dict) else "",
                    f"{float(tagline.get('y1', 0.0)):.1f}" if isinstance(tagline, dict) else "",
                    _clean_text(str(tagline.get("text", ""))) if isinstance(tagline, dict) else "",
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
