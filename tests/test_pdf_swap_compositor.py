from __future__ import annotations

import numpy as np
import pytest

from src import pdf_swap_compositor as psc


def test_detect_blend_radius_from_smask_returns_fixed_default_radius():
    smask = np.full((21, 21), 255, dtype=np.uint8)
    yy, xx = np.ogrid[:21, :21]
    dist = np.sqrt((xx - 10) ** 2 + (yy - 10) ** 2)
    smask[dist >= 8] = 200

    assert psc.detect_blend_radius_from_smask(smask) == psc.DEFAULT_BLEND_RADIUS


def test_build_art_mask_fades_before_preserved_ring():
    mask = psc._build_art_mask(width=21, height=21, outer_radius=8, feather_px=4)

    assert mask[10, 10] == pytest.approx(1.0)
    assert mask[10, 17] == pytest.approx(0.25, abs=0.05)
    assert mask[0, 0] == pytest.approx(0.0)
