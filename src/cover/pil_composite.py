"""PIL-based cover compositing — pixel-level alpha blend.

Three-layer approach:
  canvas (template with original cover) → art layer → frame overlay (gold frame on top).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# Medallion geometry (from cover_compositor.py constants)
DEFAULT_CENTER = (2864, 1620)
DEFAULT_ART_RADIUS = 600
DEFAULT_CLIP_RADIUS = 510
DEFAULT_FEATHER_PX = 0

JPEG_QUALITY = 100


def pil_composite(
    template_path: Path,
    frame_overlay_path: Path,
    art_png_path: Path,
    output_jpg_path: Path,
    center: tuple[int, int] = DEFAULT_CENTER,
    art_radius: int = DEFAULT_ART_RADIUS,
    clip_radius: int = DEFAULT_CLIP_RADIUS,
    feather_px: int = DEFAULT_FEATHER_PX,
) -> Image.Image:
    """Three-layer PIL composite: canvas → art → frame overlay.

    1. Start with the original template as the canvas (has navy bg, text, etc.)
    2. Paste prepared art at the medallion center, clipped to clip_radius
    3. Alpha-composite the frame overlay on top (preserves every gold pixel)
    """
    template = Image.open(template_path).convert("RGBA")
    frame_overlay = Image.open(frame_overlay_path).convert("RGBA")
    art = Image.open(art_png_path).convert("RGBA")

    cx, cy = center
    diameter = art_radius * 2
    art = art.resize((diameter, diameter), Image.LANCZOS)

    # Clip art to a circle at the gold frame inner edge
    clip_mask = Image.new("L", template.size, 0)
    draw = ImageDraw.Draw(clip_mask)
    draw.ellipse(
        (cx - clip_radius, cy - clip_radius, cx + clip_radius, cy + clip_radius),
        fill=255,
    )
    if feather_px > 0:
        clip_mask = clip_mask.filter(ImageFilter.GaussianBlur(feather_px))

    art_layer = Image.new("RGBA", template.size, (0, 0, 0, 0))
    art_layer.paste(art, (cx - art_radius, cy - art_radius))
    art_layer.putalpha(clip_mask)

    result = Image.alpha_composite(template, art_layer)

    # Frame overlay on top — restores all gold frame detail
    result = Image.alpha_composite(result, frame_overlay)

    composited_rgb = result.convert("RGB")
    output_jpg_path.parent.mkdir(parents=True, exist_ok=True)
    composited_rgb.save(
        output_jpg_path, format="JPEG", quality=JPEG_QUALITY, subsampling=0
    )
    return composited_rgb
