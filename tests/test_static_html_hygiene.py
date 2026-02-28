from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "src" / "static"


def _html_files() -> list[Path]:
    return sorted(STATIC_DIR.glob("*.html"))


def test_static_html_has_no_embedded_style_blocks():
    offenders = []
    for path in _html_files():
        text = path.read_text(encoding="utf-8")
        if "<style>" in text or "</style>" in text:
            offenders.append(str(path))
    assert offenders == []


def test_static_html_has_no_inline_style_attributes():
    offenders = []
    pattern = re.compile(r"\sstyle=\"")
    for path in _html_files():
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(str(path))
    assert offenders == []


def test_static_html_imports_shared_css_first():
    offenders = []
    shared_marker = '<link rel="stylesheet" href="/src/static/shared.css" />'
    link_pattern = re.compile(r"<link rel=\"stylesheet\" href=\"[^\"]+\" />")

    for path in _html_files():
        text = path.read_text(encoding="utf-8")
        links = link_pattern.findall(text)
        if not links:
            offenders.append(str(path))
            continue
        if links[0] != shared_marker:
            offenders.append(str(path))
    assert offenders == []


def test_static_inline_scripts_are_valid_javascript():
    if shutil.which("node") is None:
        pytest.skip("node not installed")

    inline_script_pattern = re.compile(
        r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
        flags=re.IGNORECASE | re.DOTALL,
    )

    failures = []
    for html_path in _html_files():
        text = html_path.read_text(encoding="utf-8")
        blocks = inline_script_pattern.findall(text)
        for index, block in enumerate(blocks, start=1):
            with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tmp:
                tmp.write(block)
                tmp_path = tmp.name
            try:
                proc = subprocess.run(
                    ["node", "--check", tmp_path],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                Path(tmp_path).unlink(missing_ok=True)
            if proc.returncode != 0:
                failures.append(f"{html_path.name} script#{index}: {proc.stderr or proc.stdout}")

    assert failures == []


def test_iterate_html_includes_drive_first_cover_preview_hooks():
    iterate_html = (STATIC_DIR / "iterate.html").read_text(encoding="utf-8")
    assert "coverPreviewBox" in iterate_html
    assert "/api/config/cover-source-default" in iterate_html
    assert "/cover-preview?" in iterate_html


def test_iterate_html_keeps_cover_source_selector_outside_quick_controls():
    iterate_html = (STATIC_DIR / "iterate.html").read_text(encoding="utf-8")
    quick_start = iterate_html.find('<div id="quickControls"')
    advanced_start = iterate_html.find('<div id="advancedControlsWrap"')
    assert quick_start >= 0
    assert advanced_start > quick_start
    quick_block = iterate_html[quick_start:advanced_start]
    assert "coverSourceSelect" not in quick_block
