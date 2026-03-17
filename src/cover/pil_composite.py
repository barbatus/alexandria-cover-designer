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
from pathlib import Path

import fitz
from PIL import Image

from src.cover.art_prep import prepare_art_png
from src.cover.region import region_from_pdf

logger = logging.getLogger(__name__)

JPEG_QUALITY = 100
RENDER_DPI = 300

ART_MARGIN_PX = 80
ART_FEATHER_PX = 35
BORDER_TRIM_RATIO = 0.05


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
    ai_art_paths: list[Path],
    output_jpg_paths: list[Path],
    *,
    shape: str = "circle",
    margin_px: int = ART_MARGIN_PX,
    feather_px: int = ART_FEATHER_PX,
    border_trim_ratio: float = BORDER_TRIM_RATIO,
    save: bool = True,
) -> list[Image.Image]:
    """Composite AI art(s) into a cover template.

    1. Read Im0 dimensions from the PDF to determine target art size.
    2. Prepare each art as RGBA PNG with feathered edges.
    3. Extract the foreground layer from the PDF (background + text + gold
       frame + protrusions, with the medallion opening as transparent alpha).
    4. Place resized art behind the foreground — art shows through the opening.

    Returns a list of composited RGB images, one per art/output pair.
    """
    source_pdf_path = Path(source_pdf_path)

    # Derive art placement geometry from the PDF's Im0 XObject.
    region = region_from_pdf(source_pdf_path)
    center = region["center"]
    art_radius = region["art_radius"]
    diameter = art_radius * 2

    foreground = _extract_foreground(source_pdf_path)
    cx, cy = center

    results: list[Image.Image] = []

    for ai_art_path, out_path in zip(ai_art_paths, output_jpg_paths):
        # Prepare art as RGBA PNG with feathered edges at the target diameter.
        art_png_path = out_path.with_name(out_path.stem + "_art_prepared.png")
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

        art = Image.open(art_png_path).convert("RGBA")

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
        if save:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            composited_rgb.save(
                out_path, format="JPEG", quality=JPEG_QUALITY, subsampling=0
            )
        results.append(composited_rgb)

    return results
