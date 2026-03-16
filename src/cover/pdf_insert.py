"""Insert a prepared RGBA PNG into a cover template PDF.

The PNG carries its own feathered alpha channel, so the PDF renderer
handles the soft-edge blending natively.  The gold scrollwork frame in
the template is never touched — the art is placed underneath it via
the existing /SMask transparency in the PDF.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import fitz
from PIL import Image

logger = logging.getLogger(__name__)

RENDER_DPI = 300
JPEG_QUALITY = 100


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
    """Find the Im0 image XObject on a page and return (width, height).

    Looks for /Im0 first, then falls back to the first image with an SMask.
    """
    xref_list = page.get_images(full=True)
    if not xref_list:
        raise ValueError("PDF page has no image XObjects")

    # Each entry: (xref, smask_xref, width, height, bpc, colorspace, alt_cs, name, ...)
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


def render_pdf_to_jpg(
    *,
    source_pdf_path: Path,
    output_jpg_path: Path,
    render_dpi: int = RENDER_DPI,
    expected_output_size: tuple[int, int] | None = None,
) -> None:
    """Render first page of a PDF to JPG at target DPI."""
    output_jpg_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(source_pdf_path))
    try:
        if doc.page_count <= 0:
            raise ValueError("PDF has no pages")
        scale = float(render_dpi) / 72.0
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        if expected_output_size and image.size != expected_output_size:
            image = image.resize(expected_output_size, Image.LANCZOS)
        image.save(
            output_jpg_path,
            format="JPEG",
            quality=JPEG_QUALITY,
            subsampling=0,
            dpi=(render_dpi, render_dpi),
        )
    finally:
        doc.close()


def insert_art_into_pdf(
    *,
    source_pdf_path: Path,
    art_png_path: Path,
    output_pdf_path: Path,
    output_jpg_path: Path | None = None,
    render_dpi: int = RENDER_DPI,
    expected_output_size: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Insert an RGBA PNG into the cover template PDF and render to JPG.

    Steps:
      1. Read Im0 transform from source PDF to find the art placement rectangle.
      2. Insert the art PNG at that rectangle.
      3. Save modified PDF.
      4. Render to JPG at 300 DPI.
    """
    source_pdf_path = Path(source_pdf_path)
    art_png_path = Path(art_png_path)
    output_pdf_path = Path(output_pdf_path)

    if not source_pdf_path.exists():
        raise FileNotFoundError(f"Source PDF not found: {source_pdf_path}")
    if not art_png_path.exists():
        raise FileNotFoundError(f"Art PNG not found: {art_png_path}")

    transform = extract_im0_transform(source_pdf_path)
    rect = _im0_to_page_rect(transform)

    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(source_pdf_path))
    try:
        page = doc[0]
        page.insert_image(
            rect,
            filename=str(art_png_path),
            keep_proportion=True,
            overlay=False,  # place UNDER existing content (frame stays on top)
        )
        doc.save(str(output_pdf_path))
    finally:
        doc.close()

    result: dict[str, Any] = {
        "source_pdf": str(source_pdf_path),
        "art_png": str(art_png_path),
        "output_pdf": str(output_pdf_path),
        "im0_rect_pts": [rect.x0, rect.y0, rect.x1, rect.y1],
    }

    if output_jpg_path is not None:
        output_jpg_path = Path(output_jpg_path)
        render_pdf_to_jpg(
            source_pdf_path=output_pdf_path,
            output_jpg_path=output_jpg_path,
            render_dpi=render_dpi,
            expected_output_size=expected_output_size,
        )
        result["output_jpg"] = str(output_jpg_path)

    logger.info(
        "PDF art insertion complete: %s -> %s (rect=%.0f,%.0f,%.0f,%.0f)",
        source_pdf_path.name,
        output_pdf_path.name,
        rect.x0,
        rect.y0,
        rect.x1,
        rect.y1,
    )
    return result


def _im0_to_page_rect(transform: dict[str, Any]) -> fitz.Rect:
    """Convert the Im0 cm-transform into a PyMuPDF Rect (in PDF points).

    PDF coordinate system has origin at bottom-left, PyMuPDF Rect uses
    top-left origin.
    """
    a = transform["cm_a"]  # width in points
    d = transform["cm_d"]  # height in points
    tx = transform["cm_tx"]  # x offset from left
    ty = transform["cm_ty"]  # y offset from bottom
    page_h = transform["page_h_pts"]

    x0 = tx
    y0 = page_h - ty - d  # flip y: bottom-up -> top-down
    x1 = tx + a
    y1 = page_h - ty

    return fitz.Rect(x0, y0, x1, y1)
