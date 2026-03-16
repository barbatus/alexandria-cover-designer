"""Prepare AI art as an RGBA PNG with feathered circular alpha for PDF insertion."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

DEFAULT_FEATHER_PX = 35
DEFAULT_MARGIN_PX = 80

BORDER_TRIM_MAX_RATIO = 0.20
UNIFORM_MARGIN_COLOR_TOL = 26.0
UNIFORM_MARGIN_STD_MAX = 22.0
UNIFORM_MARGIN_MATCH_RATIO = 0.90
UNIFORM_MARGIN_MAX_TRIM_RATIO = 0.22


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
    art = trim_uniform_margins(art)

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


def trim_uniform_margins(image: Image.Image) -> Image.Image:
    """Trim solid-color margins that AI generators sometimes add around images."""
    rgb = np.array(image.convert("RGB"), dtype=np.float32)
    h, w = rgb.shape[:2]
    if h < 64 or w < 64:
        return image

    patch = max(4, min(h, w) // 40)
    corners = np.concatenate(
        [
            rgb[:patch, :patch].reshape(-1, 3),
            rgb[:patch, w - patch :].reshape(-1, 3),
            rgb[h - patch :, :patch].reshape(-1, 3),
            rgb[h - patch :, w - patch :].reshape(-1, 3),
        ]
    )
    corner_color = np.median(corners, axis=0)

    def _uniform(line: np.ndarray) -> bool:
        if line.size == 0:
            return False
        diff = np.abs(line - corner_color).mean(axis=1)
        return (
            float(np.mean(diff <= UNIFORM_MARGIN_COLOR_TOL))
            >= UNIFORM_MARGIN_MATCH_RATIO
            and float(np.std(line, axis=0).mean()) <= UNIFORM_MARGIN_STD_MAX
        )

    max_trim_x = int(w * UNIFORM_MARGIN_MAX_TRIM_RATIO)
    max_trim_y = int(h * UNIFORM_MARGIN_MAX_TRIM_RATIO)

    left = 0
    while left < max_trim_x and _uniform(rgb[:, left]):
        left += 1
    right = 0
    while right < max_trim_x and _uniform(rgb[:, w - 1 - right]):
        right += 1
    top = 0
    while top < max_trim_y and _uniform(rgb[top]):
        top += 1
    bottom = 0
    while bottom < max_trim_y and _uniform(rgb[h - 1 - bottom]):
        bottom += 1

    if left + right + top + bottom <= 0:
        return image

    new_w, new_h = w - left - right, h - top - bottom
    if new_w < max(64, int(w * 0.55)) or new_h < max(64, int(h * 0.55)):
        return image

    return image.crop((left, top, w - right, h - bottom))
