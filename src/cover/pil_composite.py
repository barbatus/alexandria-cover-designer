"""PIL-based cover compositing — art prep, PDF extraction, and alpha blend.

End-to-end pipeline:
  1. Read Im0 XObject geometry from the PDF template to derive art placement.
  2. Prepare AI art as RGBA PNG with feathered circular alpha edges.
  3. Extract the foreground layer (background + text + golden ring area) from the
     PDF's full-page image XObject with its SMask as the alpha channel.
  4. Composite prepared art behind the foreground via PIL alpha blend.

The gold scrollwork frame stays pixel-perfect — the SMask defines the
medallion opening where art shows through.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import fitz
from PIL import Image

from src.cover.art_prep import prepare_art_png

logger = logging.getLogger(__name__)

JPEG_QUALITY = 100
RENDER_DPI = 300

ART_MARGIN_PX = 80
ART_FEATHER_PX = 35
BORDER_TRIM_RATIO = 0.05


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


def _art_placement_from_pdf(
    source_pdf_path: Path,
    render_dpi: int = RENDER_DPI,
) -> dict[str, Any]:
    """Derive center and art_radius from the Im0 XObject in a PDF.

    Uses the cm-transform extraction to locate the art placement rectangle,
    then converts from PDF points to pixel coordinates.
    """
    transform = extract_im0_transform(source_pdf_path)

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

    return {
        "center": center,
        "art_radius": art_radius,
    }


def _extract_foreground(pdf_path: Path) -> Image.Image:
    """Extract the foreground layer from the PDF as an RGBA image."""
    doc = fitz.open(str(pdf_path))
    try:
        page = doc[0]
        images = page.get_images(full=True)

        for entry in images:
            xref, smask_xref, w, h = entry[0], entry[1], entry[2], entry[3]
            name = entry[7] if len(entry) > 7 else ""
            if name == "Im0" or (w < 100 and h < 100):
                continue
            if smask_xref > 0:
                img_pix = fitz.Pixmap(doc, xref)
                smask_pix = fitz.Pixmap(doc, smask_xref)

                if img_pix.n == 3:
                    img = Image.frombytes(
                        "RGB", (img_pix.width, img_pix.height), img_pix.samples
                    ).convert("RGBA")
                elif img_pix.n == 4:
                    img = Image.frombytes(
                        "RGBA", (img_pix.width, img_pix.height), img_pix.samples
                    )
                else:
                    continue

                smask = Image.frombytes(
                    "L", (smask_pix.width, smask_pix.height), smask_pix.samples
                )
                img.putalpha(smask)
                return img

        raise ValueError("No full-page image with SMask found in PDF")
    finally:
        doc.close()


def pil_composite(
    source_pdf_path: Path,
    ai_art_path: Path,
    output_jpg_path: Path,
    *,
    shape: str = "circle",
    margin_px: int = ART_MARGIN_PX,
    feather_px: int = ART_FEATHER_PX,
    border_trim_ratio: float = BORDER_TRIM_RATIO,
) -> Image.Image:
    """Composite AI art into a cover template.

    1. Read Im0 dimensions from the PDF to determine target art size.
    2. Prepare art as RGBA PNG with feathered edges.
    3. Extract the foreground layer from the PDF (background + text + gold
       frame + protrusions, with the medallion opening as transparent alpha).
    4. Place resized art behind the foreground — art shows through the opening.
    """
    source_pdf_path = Path(source_pdf_path)
    ai_art_path = Path(ai_art_path)
    output_jpg_path = Path(output_jpg_path)

    # Derive art placement geometry from the PDF's Im0 XObject.
    geo = _art_placement_from_pdf(source_pdf_path)
    center = geo["center"]
    art_radius = geo["art_radius"]
    diameter = art_radius * 2

    # Prepare art as RGBA PNG with feathered edges at the target diameter.
    art_png_path = output_jpg_path.with_name(output_jpg_path.stem + "_art_prepared.png")
    prepare_art_png(
        ai_art_path,
        art_png_path,
        target_width=diameter,
        target_height=diameter,
        shape=shape,
        margin_px=margin_px,
        feather_px=feather_px,
        border_trim_ratio=border_trim_ratio,
    )

    foreground = _extract_foreground(source_pdf_path)
    art = Image.open(art_png_path).convert("RGBA")

    cx, cy = center

    # Art layer behind the foreground
    art_layer = Image.new("RGBA", foreground.size, (0, 0, 0, 0))
    art_layer.paste(art, (cx - art_radius, cy - art_radius))

    # Foreground on top — SMask alpha reveals art through the medallion opening
    result = Image.alpha_composite(art_layer, foreground)

    # Clean up intermediate PNG.
    try:
        art_png_path.unlink()
    except OSError:
        pass

    composited_rgb = result.convert("RGB")
    output_jpg_path.parent.mkdir(parents=True, exist_ok=True)
    composited_rgb.save(
        output_jpg_path, format="JPEG", quality=JPEG_QUALITY, subsampling=0
    )
    return composited_rgb
