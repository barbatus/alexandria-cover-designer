"""Prompt 3A cover compositing: replace center illustration while preserving template."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

try:
    from src import config
except ModuleNotFoundError:  # pragma: no cover
    import config  # type: ignore


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Region:
    center_x: int
    center_y: int
    radius: int
    frame_bbox: tuple[int, int, int, int]


def composite_single(
    cover_path: Path,
    illustration_path: Path,
    region: dict[str, Any],
    output_path: Path,
    feather_px: int = 15,
    frame_overlap_px: int = 18,
) -> Path:
    """Composite one illustration into a cover image."""
    cover = Image.open(cover_path).convert("RGB")
    illustration = Image.open(illustration_path).convert("RGBA")

    if cover.size != (3784, 2777):
        logger.warning("Cover %s has unexpected size %s", cover_path, cover.size)

    region_obj = _region_from_dict(region)
    cover_w, cover_h = cover.size

    effective_radius = max(20, region_obj.radius - frame_overlap_px)
    diameter = effective_radius * 2

    illustration = illustration.resize((diameter, diameter), Image.LANCZOS)
    illustration = _color_match_illustration(cover=cover, illustration=illustration, region=region_obj)

    full_overlay = Image.new("RGBA", (cover_w, cover_h), (0, 0, 0, 0))
    top_left = (region_obj.center_x - effective_radius, region_obj.center_y - effective_radius)
    full_overlay.paste(illustration, top_left)

    mask = _build_feather_mask(
        width=cover_w,
        height=cover_h,
        center_x=region_obj.center_x,
        center_y=region_obj.center_y,
        radius=effective_radius,
        feather_px=feather_px,
    )
    full_overlay.putalpha(mask)

    composited_rgba = Image.alpha_composite(cover.convert("RGBA"), full_overlay)
    composited_rgb = composited_rgba.convert("RGB")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    composited_rgb.save(output_path, format="JPEG", quality=100, subsampling=0, dpi=(300, 300))
    return output_path


def generate_fit_overlay(cover_path: Path, region: dict[str, Any], output_path: Path) -> Path:
    """Generate visual overlay for fit verification in review UI."""
    base = Image.open(cover_path).convert("RGBA")
    draw = ImageDraw.Draw(base, "RGBA")
    reg = _region_from_dict(region)

    comp_radius = max(20, reg.radius - 18)

    # Compositing boundary (semi-transparent red fill)
    draw.ellipse(
        (
            reg.center_x - comp_radius,
            reg.center_y - comp_radius,
            reg.center_x + comp_radius,
            reg.center_y + comp_radius,
        ),
        outline=(255, 64, 64, 230),
        width=6,
        fill=(255, 64, 64, 40),
    )

    # Frame edge boundary
    draw.ellipse(
        (
            reg.center_x - reg.radius,
            reg.center_y - reg.radius,
            reg.center_x + reg.radius,
            reg.center_y + reg.radius,
        ),
        outline=(255, 210, 90, 230),
        width=4,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    base.save(output_path, format="PNG")
    return output_path


def composite_all_variants(
    book_number: int,
    input_dir: Path,
    generated_dir: Path,
    output_dir: Path,
    regions: dict[str, Any],
) -> list[Path]:
    """Composite all available generated variants for one book."""
    cover_path = _find_cover_jpg(input_dir, book_number)
    region = _region_for_book(regions, book_number)

    image_rows = _collect_generated_for_book(generated_dir, book_number)
    if not image_rows:
        raise FileNotFoundError(f"No generated images found for book {book_number} in {generated_dir}")

    outputs: list[Path] = []
    for row in image_rows:
        if row["model"] == "default":
            out_path = output_dir / str(book_number) / f"variant_{row['variant']}.jpg"
        else:
            out_path = output_dir / str(book_number) / row["model"] / f"variant_{row['variant']}.jpg"

        composite_single(
            cover_path=cover_path,
            illustration_path=row["path"],
            region=region,
            output_path=out_path,
        )
        outputs.append(out_path)

    # Always provide one fit overlay per book for review.
    generate_fit_overlay(
        cover_path=cover_path,
        region=region,
        output_path=output_dir / str(book_number) / "fit_overlay.png",
    )

    return outputs


def batch_composite(
    input_dir: Path,
    generated_dir: Path,
    output_dir: Path,
    regions_path: Path,
    *,
    book_numbers: list[int] | None = None,
    max_books: int = 20,
) -> dict[str, Any]:
    """Composite all generated books with error isolation."""
    regions = json.loads(regions_path.read_text(encoding="utf-8"))
    generated_books = sorted(
        [int(path.name) for path in generated_dir.iterdir() if path.is_dir() and path.name.isdigit()]
    )

    if book_numbers:
        target_books = [b for b in generated_books if b in set(book_numbers)]
    else:
        target_books = generated_books[:max_books]

    summary = {
        "processed_books": 0,
        "success_books": 0,
        "failed_books": 0,
        "outputs": 0,
        "errors": [],
    }

    for book_number in target_books:
        summary["processed_books"] += 1
        try:
            outputs = composite_all_variants(
                book_number=book_number,
                input_dir=input_dir,
                generated_dir=generated_dir,
                output_dir=output_dir,
                regions=regions,
            )
            summary["success_books"] += 1
            summary["outputs"] += len(outputs)
        except Exception as exc:  # pragma: no cover - defensive
            summary["failed_books"] += 1
            summary["errors"].append({"book_number": book_number, "error": str(exc)})
            logger.error("Compositing failed for book %s: %s", book_number, exc)

    return summary


def _region_from_dict(region: dict[str, Any]) -> Region:
    bbox = region.get("frame_bbox", [0, 0, 0, 0])
    return Region(
        center_x=int(region["center_x"]),
        center_y=int(region["center_y"]),
        radius=int(region["radius"]),
        frame_bbox=(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])),
    )


def _build_feather_mask(
    *,
    width: int,
    height: int,
    center_x: int,
    center_y: int,
    radius: int,
    feather_px: int,
) -> Image.Image:
    yy, xx = np.ogrid[:height, :width]
    dist = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)

    alpha = np.zeros((height, width), dtype=np.float32)
    inner = radius - feather_px
    alpha[dist <= inner] = 255.0

    feather_zone = (dist > inner) & (dist <= radius)
    alpha[feather_zone] = np.clip((radius - dist[feather_zone]) / max(1, feather_px) * 255.0, 0, 255)
    return Image.fromarray(alpha.astype(np.uint8), mode="L")


def _color_match_illustration(cover: Image.Image, illustration: Image.Image, region: Region) -> Image.Image:
    """Nudge illustration color temperature toward region context."""
    cover_arr = np.array(cover.convert("RGB"), dtype=np.float32)
    ill_arr = np.array(illustration.convert("RGB"), dtype=np.float32)

    yy, xx = np.ogrid[:cover_arr.shape[0], :cover_arr.shape[1]]
    dist = np.sqrt((xx - region.center_x) ** 2 + (yy - region.center_y) ** 2)

    # Sample a ring just inside the frame where illustration should harmonize.
    ring = (dist >= region.radius - 60) & (dist <= region.radius - 10)
    if not np.any(ring):
        return illustration

    target_mean = cover_arr[ring].mean(axis=0)
    ill_mean = ill_arr.reshape(-1, 3).mean(axis=0)

    scale = np.clip((target_mean + 1.0) / (ill_mean + 1.0), 0.78, 1.22)
    matched = np.clip(ill_arr * scale, 0, 255).astype(np.uint8)

    alpha = np.array(illustration)[..., 3:4] if illustration.mode == "RGBA" else np.full((*matched.shape[:2], 1), 255, dtype=np.uint8)
    rgba = np.concatenate([matched, alpha], axis=2)
    return Image.fromarray(rgba, mode="RGBA")


def _load_catalog(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_cover_jpg(input_dir: Path, book_number: int) -> Path:
    catalog = _load_catalog(config.BOOK_CATALOG_PATH)
    match = None
    for entry in catalog:
        if int(entry.get("number", 0)) == int(book_number):
            match = entry
            break
    if not match:
        raise KeyError(f"Book {book_number} not found in catalog")

    folder = input_dir / str(match["folder_name"])
    if not folder.exists():
        raise FileNotFoundError(f"Cover folder missing: {folder}")

    jpg_candidates = sorted(folder.glob("*.jpg"))
    if not jpg_candidates:
        raise FileNotFoundError(f"No JPG found in {folder}")
    return jpg_candidates[0]


def _region_for_book(regions_payload: dict[str, Any], book_number: int) -> dict[str, Any]:
    for row in regions_payload.get("covers", []):
        if int(row.get("cover_id", 0)) == int(book_number):
            return row
    return regions_payload.get("consensus_region", {})


def _collect_generated_for_book(generated_dir: Path, book_number: int) -> list[dict[str, Any]]:
    base = generated_dir / str(book_number)
    if not base.exists():
        return []

    rows: list[dict[str, Any]] = []

    # Model-grouped outputs
    for model_dir in sorted([path for path in base.iterdir() if path.is_dir()]):
        if model_dir.name == "history":
            continue
        for image in sorted(model_dir.glob("variant_*.png")):
            variant = _parse_variant(image.stem)
            rows.append({"model": model_dir.name, "variant": variant, "path": image})

    # Default outputs
    for image in sorted(base.glob("variant_*.png")):
        variant = _parse_variant(image.stem)
        rows.append({"model": "default", "variant": variant, "path": image})

    dedup: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        dedup[(row["model"], row["variant"])] = row

    return sorted(dedup.values(), key=lambda row: (row["model"], row["variant"]))


def _parse_variant(stem: str) -> int:
    if "variant_" not in stem:
        return 0
    token = stem.split("variant_", 1)[1].split("_", 1)[0]
    try:
        return int(token)
    except ValueError:
        return 0


def _parse_books(raw: str | None) -> list[int] | None:
    if not raw:
        return None

    books: set[int] = set()
    for piece in raw.split(","):
        token = piece.strip()
        if not token:
            continue
        if "-" in token:
            start_str, end_str = token.split("-", 1)
            start, end = int(start_str), int(end_str)
            for value in range(min(start, end), max(start, end) + 1):
                books.add(value)
        else:
            books.add(int(token))

    return sorted(books)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prompt 3A cover compositing")
    parser.add_argument("--input-dir", type=Path, default=config.INPUT_DIR)
    parser.add_argument("--generated-dir", type=Path, default=config.TMP_DIR / "generated")
    parser.add_argument("--output-dir", type=Path, default=config.TMP_DIR / "composited")
    parser.add_argument("--regions-path", type=Path, default=config.CONFIG_DIR / "cover_regions.json")
    parser.add_argument("--book", type=int, default=None)
    parser.add_argument("--books", type=str, default=None)
    parser.add_argument("--max-books", type=int, default=20)

    args = parser.parse_args()
    regions = json.loads(args.regions_path.read_text(encoding="utf-8"))

    if args.book is not None:
        outputs = composite_all_variants(
            book_number=args.book,
            input_dir=args.input_dir,
            generated_dir=args.generated_dir,
            output_dir=args.output_dir,
            regions=regions,
        )
        logger.info("Composited %d files for book %s", len(outputs), args.book)
        return 0

    books = _parse_books(args.books)
    summary = batch_composite(
        input_dir=args.input_dir,
        generated_dir=args.generated_dir,
        output_dir=args.output_dir,
        regions_path=args.regions_path,
        book_numbers=books,
        max_books=args.max_books,
    )
    logger.info("Batch compositing summary: %s", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
