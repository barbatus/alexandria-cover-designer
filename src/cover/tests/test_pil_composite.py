"""Tests for PIL-based cover compositing."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.cover.pil_composite import _extract_foreground, pil_composite

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


class TestPilComposite:
    """PIL-based compositing must produce correct output with gold frame intact."""

    def test_produces_output(
        self,
        sample_template_pdf: Path,
        sample_art_png: Path,
    ):
        out_jpg = OUTPUT_DIR / "pil_composited.jpg"

        results = pil_composite(
            source_pdf_path=sample_template_pdf,
            ai_art_paths=[sample_art_png],
            output_jpg_paths=[out_jpg],
        )

        assert out_jpg.exists()
        assert len(results) == 1
        assert results[0].size == (3784, 2777)

    def test_gold_frame_preserved(
        self,
        sample_template_pdf: Path,
        sample_art_png: Path,
    ):
        """Gold frame pixels must match the original template outside the art circle."""
        out_jpg = OUTPUT_DIR / "pil_composited_frame_check.jpg"

        results = pil_composite(
            source_pdf_path=sample_template_pdf,
            ai_art_paths=[sample_art_png],
            output_jpg_paths=[out_jpg],
        )

        foreground = _extract_foreground(sample_template_pdf)
        orig_arr = np.array(foreground.convert("RGB"))
        comp_arr = np.array(results[0])

        h, w = orig_arr.shape[:2]
        corner_orig = orig_arr[: h // 8, : w // 8]
        corner_comp = comp_arr[: h // 8, : w // 8]
        diff = np.abs(corner_orig.astype(float) - corner_comp.astype(float)).mean()
        assert diff < 2.0, f"Background corner changed: mean diff = {diff:.1f}"

    def test_saves_reference_images(
        self,
        sample_template_pdf: Path,
        sample_art_png: Path,
    ):
        out_jpg = OUTPUT_DIR / "pil_composited_final.jpg"

        pil_composite(
            source_pdf_path=sample_template_pdf,
            ai_art_paths=[sample_art_png],
            output_jpg_paths=[out_jpg],
        )

        assert out_jpg.exists()
