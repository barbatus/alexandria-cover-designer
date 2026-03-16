"""Tests for src.cover.pil_composite — PIL-based cover compositing."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.cover.art_prep import prepare_art_png
from src.cover.pil_composite import pil_composite

OUTPUT_DIR = Path(__file__).parent / "output2"
OUTPUT_DIR.mkdir(exist_ok=True)

CENTER_X, CENTER_Y = 2864, 1620


@pytest.fixture
def prepared_art(sample_art_png: Path, tmp_path: Path) -> Path:
    out = tmp_path / "prepared.png"
    prepare_art_png(
        sample_art_png,
        out,
        target_width=1000,
        target_height=1000,
        shape="circle",
        margin_px=20,
        feather_px=15,
    )
    return out


class TestPilComposite:
    """PIL-based compositing must produce correct output with gold frame intact."""

    def test_produces_output(
        self,
        sample_template_png: Path,
        sample_frame_overlay_png: Path,
        prepared_art: Path,
    ):
        out_jpg = OUTPUT_DIR / "pil_composited.jpg"

        result = pil_composite(
            template_path=sample_template_png,
            frame_overlay_path=sample_frame_overlay_png,
            art_png_path=prepared_art,
            output_jpg_path=out_jpg,
        )

        assert out_jpg.exists()
        assert result.size == (3784, 2777)

    def test_gold_frame_preserved(
        self,
        sample_template_png: Path,
        sample_frame_overlay_png: Path,
        prepared_art: Path,
    ):
        """Gold frame pixels must match the original template outside the art circle."""
        out_jpg = OUTPUT_DIR / "pil_composited_frame_check.jpg"

        composited = pil_composite(
            template_path=sample_template_png,
            frame_overlay_path=sample_frame_overlay_png,
            art_png_path=prepared_art,
            output_jpg_path=out_jpg,
        )

        original = Image.open(sample_template_png).convert("RGB")
        orig_arr = np.array(original)
        comp_arr = np.array(composited)

        h, w = orig_arr.shape[:2]
        corner_orig = orig_arr[: h // 8, : w // 8]
        corner_comp = comp_arr[: h // 8, : w // 8]
        diff = np.abs(corner_orig.astype(float) - corner_comp.astype(float)).mean()
        assert diff < 2.0, f"Background corner changed: mean diff = {diff:.1f}"

    def test_saves_reference_images(
        self,
        sample_template_png: Path,
        sample_frame_overlay_png: Path,
        prepared_art: Path,
    ):
        pil_composite(
            template_path=sample_template_png,
            frame_overlay_path=sample_frame_overlay_png,
            art_png_path=prepared_art,
            output_jpg_path=OUTPUT_DIR / "pil_composited_final.jpg",
        )

        assert (OUTPUT_DIR / "pil_composited_final.jpg").exists()
