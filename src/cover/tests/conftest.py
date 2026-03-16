"""Shared fixtures for src/cover tests."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_art_png() -> Path:
    """Real AI-generated art PNG fixture."""
    p = FIXTURES_DIR / "sample_art.png"
    assert p.exists(), f"Fixture missing: {p}"
    return p


@pytest.fixture
def sample_template_pdf() -> Path:
    """Pre-built cover template PDF with Im0 placeholder for art insertion."""
    p = FIXTURES_DIR / "template.pdf"
    assert p.exists(), f"Fixture missing: {p}"
    return p


@pytest.fixture
def sample_template_png() -> Path:
    """Original cover template PNG (A Christmas Carol)."""
    p = FIXTURES_DIR / "template_dickens.png"
    assert p.exists(), f"Fixture missing: {p}"
    return p


@pytest.fixture
def sample_frame_overlay_png() -> Path:
    """Gold frame overlay RGBA PNG (transparent art opening)."""
    p = FIXTURES_DIR / "frame_overlay_dickens.png"
    assert p.exists(), f"Fixture missing: {p}"
    return p
