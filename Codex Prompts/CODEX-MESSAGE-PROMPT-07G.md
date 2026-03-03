# Codex Message for PROMPT-07G

## What to paste in the Codex chat:

---

**CRITICAL: Only modify `src/cover_compositor.py`. Do NOT touch any other file. Preserve the current design/UI/UX exactly as it is.**

Read `Codex Prompts/PROMPT-07G-INMEMORY-TEMPLATE-FIX.md` in the repo.

**PROBLEM:** The 07F PNG template pipeline tries to load template files from disk. Those files were never deployed to Railway. The compositor silently falls back to the legacy pipeline, which has all three original bugs (art too small, off-center, original art visible).

**THE FIX:** Replace the `else` branch in `composite_single()` (~line 741) with a pure in-memory pipeline. Build the template in RAM from the already-loaded cover image. No disk I/O. No fallback to legacy. Zero failure modes.

**EXACT CHANGES TO `src/cover_compositor.py`:**

Find the `else:` branch in `composite_single()` (the medallion path, ~line 741 to ~line 803). Replace the ENTIRE `else` block with this pipeline:

1. Use FIXED center: `center_x = FALLBACK_CENTER_X` (2864), `center_y = FALLBACK_CENTER_Y` (1620). Do NOT call `_resolve_medallion_geometry()` — dynamic detection returns different centers, causing misalignment.

2. Build template in memory:
   - `cover_rgba = cover.convert("RGBA")`
   - Create 4x supersampled circle mask at (2864, 1620) with r=TEMPLATE_PUNCH_RADIUS (465)
   - `template = cover_rgba.copy()` then `template.putalpha(mask)`

3. Sample background: `fill_rgb = _sample_cover_background(cover, center_x, center_y, FALLBACK_RADIUS)`

4. Canvas: `Image.new("RGBA", (cover_w, cover_h), (*fill_rgb, 255))`

5. Art: `_simple_center_crop(illustration)` then resize to `punch_radius * 2 + 20` (950px). Flatten transparency against fill_rgb.

6. Paste art at `(center_x - art_diameter//2, center_y - art_diameter//2)` using `.paste()`.

7. Composite: `canvas + art_layer + template` using `Image.alpha_composite()` twice. Convert to RGB.

**DO NOT REMOVE** any existing functions. Just replace the else-branch code.

**DO NOT ADD** prompt changes, dropdown fixes, or any other changes. This prompt is compositor-only.

**VERIFY:** Generate a cover. Art fills medallion edge-to-edge. Zero original cover art visible. Frame intact.

```bash
git add -A && git commit -m "fix: in-memory PNG template pipeline, no disk/legacy fallback (PROMPT-07G)" && git push
```

---
