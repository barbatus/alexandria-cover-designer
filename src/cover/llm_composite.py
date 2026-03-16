"""LLM-based cover compositing — use a vision model to blend art into the frame.

Pipeline:
  1. Render the cover PDF to get the full cover image (with old art).
  2. Crop the golden ring region as a rectangle from the rendered cover.
  3. Send the cropped region + new art to an LLM via OpenRouter.
  4. Paste the LLM result back into the cover image and save as JPG.
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Any

import fitz
import requests
from PIL import Image

from src import config as cfg

logger = logging.getLogger(__name__)

JPEG_QUALITY = 100
RENDER_DPI = 300

# Padding around the art area to include the full golden ring in the crop.
RING_PAD_PX = 120

LLM_PROMPT = (
    "You are given two images:\n"
    "1. A cropped section of a book cover containing a golden ornamental ring/frame "
    "with old artwork inside it.\n"
    "2. New artwork that should replace the old artwork inside the golden ring.\n\n"
    "Replace the old artwork inside the golden ring with the new artwork. "
    "The golden ring frame, its ornamental details, and any protrusions must remain "
    "perfectly intact and unchanged. Blend the new art naturally into the circular "
    "opening so it looks like the original cover was designed with this art. "
    "Keep the same lighting, color temperature, and style consistency. "
    "Return ONLY the edited image at the exact same dimensions as image 1."
)


def _image_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    """Encode a PIL image to a base64 data URI."""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = "image/png" if fmt == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{encoded}"


def _call_openrouter(
    cropped: Image.Image,
    new_art: Image.Image,
    *,
    api_key: str,
    model: str = "google/gemini-3-pro-image-preview",
    timeout: int = 120,
) -> Image.Image:
    """Send images to OpenRouter and get edited image back."""
    crop_b64 = _image_to_base64(cropped)
    art_b64 = _image_to_base64(new_art)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": LLM_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": crop_b64},
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": art_b64},
                    },
                ],
            }
        ],
        "modalities": ["image", "text"],
        "stream": False,
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://alexandria-cover-designer.local",
            "X-Title": "Alexandria Cover Designer",
        },
        json=payload,
        timeout=timeout,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"OpenRouter error {response.status_code}: {response.text[:500]}"
        )

    return _parse_openrouter_image(response.json())


def _parse_openrouter_image(body: dict[str, Any]) -> Image.Image:
    """Extract an image from an OpenRouter response (multiple formats)."""
    for choice in body.get("choices") or []:
        message = choice.get("message", {})
        if not isinstance(message, dict):
            continue

        for key in ("images", "content"):
            parts = message.get(key)
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                ref = part.get("image_url", "")
                if isinstance(ref, dict):
                    ref = ref.get("url", "")
                parsed = _decode_image_ref(str(ref or ""))
                if parsed is not None:
                    return parsed

    raise RuntimeError("OpenRouter response missing image payload")


def _decode_image_ref(ref: str) -> Image.Image | None:
    """Decode a base64 data URI or download an HTTP URL to a PIL image."""
    ref = ref.strip()
    if not ref:
        return None
    if ref.startswith("data:image") and "," in ref:
        encoded = ref.split(",", 1)[1]
        return Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")
    if ref.startswith("http"):
        resp = requests.get(ref, timeout=60)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
    return None


def _render_pdf(pdf_path: Path, dpi: int = RENDER_DPI) -> Image.Image:
    """Render the first page of a PDF to a PIL RGB image."""
    doc = fitz.open(str(pdf_path))
    try:
        scale = float(dpi) / 72.0
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()


def llm_composite(
    source_pdf_path: Path,
    ai_art_path: Path,
    output_jpg_path: Path,
    *,
    center: tuple[int, int],
    width: int,
    height: int,
    model: str = "google/gemini-3-pro-image-preview",
    ring_pad_px: int = RING_PAD_PX,
) -> Image.Image:
    """Composite AI art into a cover PDF using an LLM for blending.

    1. Render the cover PDF to get the full image (with old art).
    2. Crop the medallion region (center +/- width/height + padding).
    3. Send cropped region + new art to the LLM via OpenRouter.
    4. Paste the LLM result back and save as JPG.
    """
    source_pdf_path = Path(source_pdf_path)
    ai_art_path = Path(ai_art_path)
    output_jpg_path = Path(output_jpg_path)

    cx, cy = center
    half_w = width // 2
    half_h = height // 2

    cover = _render_pdf(source_pdf_path)
    new_art = Image.open(ai_art_path).convert("RGBA")

    # Crop the medallion rectangle (art area + ring padding).
    x0 = max(0, cx - half_w - ring_pad_px)
    y0 = max(0, cy - half_h - ring_pad_px)
    x1 = min(cover.width, cx + half_w + ring_pad_px)
    y1 = min(cover.height, cy + half_h + ring_pad_px)
    cropped = cover.crop((x0, y0, x1, y1))

    # Resize new art to fit the medallion.
    art_resized = new_art.resize((width, height), Image.LANCZOS)

    logger.info(
        "LLM composite: crop=(%d,%d,%d,%d) %dx%d, art=%dx%d, model=%s",
        x0,
        y0,
        x1,
        y1,
        cropped.width,
        cropped.height,
        art_resized.width,
        art_resized.height,
        model,
    )

    # Call LLM via OpenRouter.
    edited = _call_openrouter(cropped, art_resized, api_key=cfg.OPENROUTER_API_KEY, model=model)

    # Resize LLM output to match the original crop size and paste back.
    edited = edited.resize((x1 - x0, y1 - y0), Image.LANCZOS)
    result = cover.copy()
    result.paste(edited, (x0, y0))

    # Save JPG.
    output_jpg_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_jpg_path, format="JPEG", quality=JPEG_QUALITY, subsampling=0)

    logger.info("LLM composite saved: %s", output_jpg_path)
    return result
