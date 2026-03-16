"""Prepare AI art as an RGBA PNG with feathered circular alpha for PDF insertion."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

DEFAULT_FEATHER_PX = 35
DEFAULT_MARGIN_PX = 80

BORDER_TRIM_MAX_RATIO = 0.20


def prepare_art_png(
    ai_art_path: Path,
    output_png_path: Path,
    *,
    target_width: int,
    target_height: int,
    shape: str = "circle",
    margin_px: int = DEFAULT_MARGIN_PX,
    feather_px: int = DEFAULT_FEATHER_PX,
    border_trim_ratio: float = 0.05,
) -> Path:
    """Load AI art, crop/resize, apply feathered alpha mask, save as RGBA PNG.

    The resulting PNG has transparent, soft-faded edges so that when placed
    on the PDF, the template background shows through gradually at the boundary.
    """
    with Image.open(ai_art_path) as src:
        art = src.convert("RGBA")

    art = strip_border(art, ratio=border_trim_ratio)

    if shape == "circle":
        side = min(target_width, target_height)
        art = center_crop_square(art)
        art = art.resize((side, side), Image.LANCZOS)
        art = apply_circle_alpha(art, margin_px=margin_px, feather_px=feather_px)
    else:
        art = ImageOps.fit(art, (target_width, target_height), method=Image.LANCZOS)
        art = apply_rect_alpha(art, margin_px=margin_px, feather_px=feather_px)

    output_png_path.parent.mkdir(parents=True, exist_ok=True)
    art.save(output_png_path, format="PNG")
    return output_png_path


def apply_circle_alpha(
    img: Image.Image, *, margin_px: int, feather_px: int
) -> Image.Image:
    """Apply a feathered circular alpha mask centered on the image."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    inset = margin_px
    draw.ellipse((inset, inset, w - inset, h - inset), fill=255)

    if feather_px > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather_px))

    img.putalpha(mask)
    return img


def apply_rect_alpha(
    img: Image.Image, *, margin_px: int, feather_px: int
) -> Image.Image:
    """Apply a feathered rectangular alpha mask."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    inset = margin_px
    draw.rounded_rectangle(
        (inset, inset, w - inset, h - inset),
        radius=max(1, min(40, margin_px // 2)),
        fill=255,
    )

    if feather_px > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather_px))

    img.putalpha(mask)
    return img


def center_crop_square(image: Image.Image) -> Image.Image:
    """Center-crop an image to a square."""
    w, h = image.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return image.crop((left, top, left + side, top + side))


def strip_border(image: Image.Image, *, ratio: float = 0.05) -> Image.Image:
    """Crop a symmetric outer strip to remove AI-added border artifacts."""
    ratio = max(0.0, min(BORDER_TRIM_MAX_RATIO, float(ratio)))
    if ratio <= 0:
        return image
    w, h = image.size
    tx = int(round(w * ratio / 2.0))
    ty = int(round(h * ratio / 2.0))
    if (w - 2 * tx) < 64 or (h - 2 * ty) < 64:
        return image
    return image.crop((tx, ty, w - tx, h - ty))
