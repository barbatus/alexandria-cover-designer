"""Art placement region — shared geometry for PIL and LLM compositing."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, TypedDict

import fitz

RENDER_DPI = 300


class Region(TypedDict):
    center: tuple[int, int]
    art_radius: int


def region_from_pdf(
    pdf_path: Path, render_dpi: int = RENDER_DPI
) -> Region:
    """Derive art placement region from the Im0 XObject in a PDF."""
    transform = extract_im0_transform(pdf_path)

    scale = render_dpi / 72.0
    a = transform["cm_a"]
    d = transform["cm_d"]
    tx = transform["cm_tx"]
    ty = transform["cm_ty"]
    page_h = transform["page_h_pts"]

    x0 = tx * scale
    y0 = (page_h - ty - d) * scale
    x1 = (tx + a) * scale
    y1 = (page_h - ty) * scale

    center = (round((x0 + x1) / 2), round((y0 + y1) / 2))
    art_radius = round(max(x1 - x0, y1 - y0) / 2)

    return Region(center=center, art_radius=art_radius)


def extract_im0_transform(pdf_path: Path) -> dict[str, Any]:
    """Extract Im0 dimensions and cm-transform from the PDF content stream.

    Returns dict with keys: im0_w, im0_h, cm_a, cm_d, cm_tx, cm_ty,
    page_w_pts, page_h_pts.
    """
    doc = fitz.open(str(pdf_path))
    try:
        if doc.page_count == 0:
            raise ValueError("Source PDF has no pages")
        page = doc[0]

        im0_w, im0_h = _find_im0_dimensions(page)

        stream = page.read_contents().decode("latin-1")

        cm_pattern = re.compile(
            r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+cm"
        )
        matches = list(cm_pattern.finditer(stream))

        im0_pos = stream.find("/Im0")
        if im0_pos < 0:
            im0_pos = stream.find("Do")

        best = None
        for m in matches:
            if m.start() < im0_pos:
                best = m
        if best is None:
            raise ValueError("Could not find cm transform for Im0")

        rect = page.rect
        page_w = float(rect.width)
        page_h = float(rect.height)

        return {
            "im0_w": im0_w,
            "im0_h": im0_h,
            "cm_a": float(best.group(1)),
            "cm_d": float(best.group(4)),
            "cm_tx": float(best.group(5)),
            "cm_ty": float(best.group(6)),
            "page_w_pts": page_w,
            "page_h_pts": page_h,
        }
    finally:
        doc.close()


def _find_im0_dimensions(page: fitz.Page) -> tuple[int, int]:
    """Find the Im0 image XObject on a page and return (width, height)."""
    xref_list = page.get_images(full=True)
    if not xref_list:
        raise ValueError("PDF page has no image XObjects")

    for entry in xref_list:
        _xref, smask_xref, w, h = entry[0], entry[1], entry[2], entry[3]
        name = entry[7] if len(entry) > 7 else ""
        if name == "Im0":
            return (int(w), int(h))

    for entry in xref_list:
        _xref, smask_xref, w, h = entry[0], entry[1], entry[2], entry[3]
        if smask_xref > 0:
            return (int(w), int(h))

    raise ValueError("No image XObject with SMask found (expected /Im0)")
