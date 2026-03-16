"""Tests for src.cover.pdf_insert — PDF art insertion and rendering."""

from __future__ import annotations

from pathlib import Path

import fitz
import numpy as np
from PIL import Image

from src.cover.art_prep import prepare_art_png
from src.cover.pdf_insert import (
    insert_art_into_pdf,
    render_pdf_to_jpg,
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


class TestRenderPdfToJpg:
    """render_pdf_to_jpg must produce a valid JPEG from a PDF."""

    def test_output_exists(self, sample_template_pdf: Path, tmp_path: Path):
        out = tmp_path / "render.jpg"

        render_pdf_to_jpg(source_pdf_path=sample_template_pdf, output_jpg_path=out)

        assert out.exists()
        with Image.open(out) as img:
            assert img.format == "JPEG"
            assert img.size[0] > 0 and img.size[1] > 0

    def test_render_at_300dpi(self, sample_template_pdf: Path, tmp_path: Path):
        out = tmp_path / "render.jpg"

        render_pdf_to_jpg(
            source_pdf_path=sample_template_pdf, output_jpg_path=out, render_dpi=300
        )

        with Image.open(out) as img:
            # At 300 DPI the pixel width should be ~page_w_pts * 300/72
            doc = fitz.open(str(sample_template_pdf))
            expected_w = int(doc[0].rect.width * 300 / 72)
            doc.close()
            assert abs(img.size[0] - expected_w) <= 2

    def test_resize_to_expected_size(self, sample_template_pdf: Path, tmp_path: Path):
        out = tmp_path / "render.jpg"
        target = (800, 600)

        render_pdf_to_jpg(
            source_pdf_path=sample_template_pdf,
            output_jpg_path=out,
            expected_output_size=target,
        )

        with Image.open(out) as img:
            assert img.size == target


class TestInsertArtIntoPdf:
    """insert_art_into_pdf must place art under the frame and render correctly."""

    def test_produces_output_pdf(
        self, sample_template_pdf: Path, sample_art_png: Path, tmp_path: Path
    ):
        prepared = tmp_path / "prepared.png"
        prepare_art_png(
            sample_art_png,
            prepared,
            target_width=1000,
            target_height=1000,
            shape="circle",
            margin_px=20,
            feather_px=15,
        )

        out_pdf = OUTPUT_DIR / "composited.pdf"
        result = insert_art_into_pdf(
            source_pdf_path=sample_template_pdf,
            art_png_path=prepared,
            output_pdf_path=out_pdf,
        )

        assert out_pdf.exists()
        assert result["output_pdf"] == str(out_pdf)
        assert len(result["im0_rect_pts"]) == 4

    def test_produces_output_jpg(
        self, sample_template_pdf: Path, sample_art_png: Path, tmp_path: Path
    ):
        prepared = tmp_path / "prepared.png"
        prepare_art_png(
            sample_art_png,
            prepared,
            target_width=1000,
            target_height=1000,
            shape="circle",
            margin_px=20,
            feather_px=15,
        )

        out_pdf = tmp_path / "output.pdf"
        out_jpg = OUTPUT_DIR / "composited.jpg"
        result = insert_art_into_pdf(
            source_pdf_path=sample_template_pdf,
            art_png_path=prepared,
            output_pdf_path=out_pdf,
            output_jpg_path=out_jpg,
        )

        assert out_jpg.exists()
        assert "output_jpg" in result
        with Image.open(out_jpg) as img:
            assert img.format == "JPEG"
            assert img.size[0] > 0

    def test_art_is_under_frame(
        self, sample_template_pdf: Path, sample_art_png: Path, tmp_path: Path
    ):
        """The gold frame ring should still be visible after art insertion."""
        prepared = OUTPUT_DIR / "prepared_art.png"
        prepare_art_png(
            sample_art_png,
            prepared,
            target_width=1000,
            target_height=1000,
            shape="circle",
            margin_px=20,
            feather_px=15,
        )

        out_pdf = tmp_path / "output.pdf"
        out_jpg = OUTPUT_DIR / "composited_frame_check.jpg"
        insert_art_into_pdf(
            source_pdf_path=sample_template_pdf,
            art_png_path=prepared,
            output_pdf_path=out_pdf,
            output_jpg_path=out_jpg,
        )

        # Render the template (with hole) for comparison
        orig_jpg = OUTPUT_DIR / "original_template.jpg"
        render_pdf_to_jpg(source_pdf_path=sample_template_pdf, output_jpg_path=orig_jpg)

        with Image.open(orig_jpg) as orig, Image.open(out_jpg) as composited:
            orig_arr = np.array(orig)
            comp_arr = np.array(composited)

            # The frame area (edges outside the art circle) should be similar
            # between original and composited — frame pixels not damaged
            h, w = orig_arr.shape[:2]
            # Check top-left corner (pure background, no art)
            corner_orig = orig_arr[: h // 8, : w // 8]
            corner_comp = comp_arr[: h // 8, : w // 8]
            diff = np.abs(corner_orig.astype(float) - corner_comp.astype(float)).mean()
            assert diff < 5.0, (
                f"Background corner changed too much: mean diff = {diff:.1f}"
            )
