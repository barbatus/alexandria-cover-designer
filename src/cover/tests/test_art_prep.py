"""Tests for src.cover.art_prep — RGBA PNG preparation with feathered alpha."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from PIL import Image

from src.cover.art_prep import prepare_art_png


class TestPrepareArtPngCircle:
    """Circle-mode output must be RGBA with a feathered alpha channel."""

    def test_output_is_rgba_png(self, sample_art_png: Path, tmp_path: Path):
        out_png = tmp_path / "prepared.png"

        prepare_art_png(
            sample_art_png,
            out_png,
            target_width=400,
            target_height=400,
            shape="circle",
        )

        assert out_png.exists()
        with Image.open(out_png) as result:
            assert result.mode == "RGBA"

    def test_center_is_opaque(self, sample_art_png: Path, tmp_path: Path):
        out_png = tmp_path / "prepared.png"

        prepare_art_png(
            sample_art_png,
            out_png,
            target_width=400,
            target_height=400,
            shape="circle",
        )

        with Image.open(out_png) as result:
            alpha = np.array(result)[:, :, 3]
            cy, cx = alpha.shape[0] // 2, alpha.shape[1] // 2
            assert alpha[cy, cx] == 255, "Centre pixel must be fully opaque"

    def test_corners_are_transparent(self, sample_art_png: Path, tmp_path: Path):
        out_png = tmp_path / "prepared.png"

        prepare_art_png(
            sample_art_png,
            out_png,
            target_width=400,
            target_height=400,
            shape="circle",
        )

        with Image.open(out_png) as result:
            alpha = np.array(result)[:, :, 3]
            assert alpha[0, 0] == 0, "Top-left corner must be transparent"
            assert alpha[0, -1] == 0, "Top-right corner must be transparent"
            assert alpha[-1, 0] == 0, "Bottom-left corner must be transparent"
            assert alpha[-1, -1] == 0, "Bottom-right corner must be transparent"

    def test_feather_creates_gradient(self, sample_art_png: Path, tmp_path: Path):
        out_png = tmp_path / "prepared.png"

        prepare_art_png(
            sample_art_png,
            out_png,
            target_width=400,
            target_height=400,
            shape="circle",
            feather_px=30,
        )

        with Image.open(out_png) as result:
            alpha = np.array(result)[:, :, 3]
            mid_row = alpha[alpha.shape[0] // 2, :]
            unique = set(mid_row)
            assert len(unique) > 2, "Feathered edge should have gradient alpha values"

    def test_output_is_square_for_circle(self, sample_art_png: Path, tmp_path: Path):
        out_png = tmp_path / "prepared.png"

        prepare_art_png(
            sample_art_png,
            out_png,
            target_width=400,
            target_height=400,
            shape="circle",
        )

        with Image.open(out_png) as result:
            w, h = result.size
            assert w == h == 400


class TestPrepareArtPngRect:
    """Rectangle-mode output must be RGBA with feathered rect alpha."""

    def test_output_is_rgba(self, sample_art_png: Path, tmp_path: Path):
        out_png = tmp_path / "prepared.png"

        prepare_art_png(
            sample_art_png,
            out_png,
            target_width=500,
            target_height=400,
            shape="rect",
        )

        assert out_png.exists()
        with Image.open(out_png) as result:
            assert result.mode == "RGBA"
            assert result.size == (500, 400)

    def test_center_opaque_corners_transparent(self, sample_art_png: Path, tmp_path: Path):
        out_png = tmp_path / "prepared.png"

        prepare_art_png(
            sample_art_png,
            out_png,
            target_width=500,
            target_height=400,
            shape="rect",
        )

        with Image.open(out_png) as result:
            alpha = np.array(result)[:, :, 3]
            cy, cx = alpha.shape[0] // 2, alpha.shape[1] // 2
            assert alpha[cy, cx] == 255
            assert alpha[0, 0] == 0
