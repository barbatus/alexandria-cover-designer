# PROMPT-07G — In-Memory PNG Template Compositor Fix

**Priority:** CRITICAL — The 07E/07F deployment still shows original cover art at the medallion boundary. The legacy fallback pipeline is being triggered because the template files were never deployed to Railway.

**Branch:** `master`

---

## DESIGN PRESERVATION — DO NOT CHANGE

Only modify `src/cover_compositor.py` as specified below. Do NOT touch `index.html`, sidebar, navigation, color scheme, page layouts, CSS, frontend JS, `src/prompt_generator.py`, or any file not explicitly listed here.

**This prompt changes ONE file:** `src/cover_compositor.py`
**This prompt changes ONE thing:** The `else` branch in `composite_single()`

---

## Root Cause

The 07F deployment added a template pipeline that:
1. Looks for a pre-generated PNG template on disk (`_find_template_for_cover`)
2. If not found, tries to generate one on disk (`_create_template_for_cover`)
3. If that fails, falls back to the legacy pipeline (`_legacy_medallion_composite`)

**Problem:** `config/templates/` was never deployed to Railway. Step 1 fails. Step 2 tries to write a large PNG to Railway's ephemeral filesystem, which either fails or produces incorrect results. Step 3 kicks in — running the exact same broken legacy code that has all three original bugs.

**Fix:** Generate the template entirely in memory. The cover image is already loaded in RAM. Punch the transparent hole in-memory and composite immediately. No file lookup, no disk write, no fallback to legacy. Zero failure modes.

---

## The Change

### Step 1: Find the `else` branch in `composite_single()`

In `src/cover_compositor.py`, find `composite_single()` (starts around line 681). Inside it, there is an if/elif/else chain:

- `if region_obj.region_type == "rectangle" ...` — **DO NOT TOUCH**
- `elif region_obj.region_type == "custom_mask" ...` — **DO NOT TOUCH**
- `else:` — **THIS IS WHAT YOU REPLACE**

The `else` branch currently starts around line 741 and runs to approximately line 803.

### Step 2: Replace the ENTIRE `else` branch with this code

Delete everything from `else:` to the end of that branch (just before the `output_path.parent.mkdir...` line that saves the JPEG). Replace with:

```python
    else:
        # ── In-memory PNG-template compositing pipeline ──────────────
        # Builds the frame template in RAM from the already-loaded cover.
        # Three layers: solid canvas -> AI art -> cover-with-transparent-hole.
        # The frame is ALWAYS the topmost layer, making bleed-through
        # structurally impossible. No disk I/O, no fallback needed.

        # Use FIXED center coordinates that match all 99 covers.
        # Do NOT use _resolve_medallion_geometry() — it uses dynamic
        # detection that can return slightly different centers, causing
        # misalignment between the art and the template hole.
        center_x = FALLBACK_CENTER_X   # 2864
        center_y = FALLBACK_CENTER_Y   # 1620
        punch_radius = TEMPLATE_PUNCH_RADIUS  # 465

        # ── 1. Build the template in memory ──
        # Take the original cover, punch a transparent circle at the
        # medallion center. This becomes the topmost layer.
        cover_rgba = cover.convert("RGBA")
        tmpl_w, tmpl_h = cover_rgba.size

        # 4x supersampled anti-aliased circle mask
        scale = 4
        mask_large = Image.new("L", (tmpl_w * scale, tmpl_h * scale), 255)
        draw_mask = ImageDraw.Draw(mask_large)
        cx_s, cy_s, r_s = center_x * scale, center_y * scale, punch_radius * scale
        draw_mask.ellipse((cx_s - r_s, cy_s - r_s, cx_s + r_s, cy_s + r_s), fill=0)
        mask = mask_large.resize((tmpl_w, tmpl_h), Image.LANCZOS)

        template = cover_rgba.copy()
        template.putalpha(mask)

        # ── 2. Sample background color from cover ──
        fill_rgb = _sample_cover_background(
            cover=cover,
            center_x=center_x,
            center_y=center_y,
            outer_radius=FALLBACK_RADIUS,
        )

        # ── 3. Solid canvas with sampled background color ──
        canvas = Image.new("RGBA", (cover_w, cover_h), (*fill_rgb, 255))

        # ── 4. Prepare AI art: simple center crop, scale to fill ──
        art_diameter = punch_radius * 2 + 20  # 10px bleed on each side = 950px
        art = _simple_center_crop(illustration)
        art = art.resize((art_diameter, art_diameter), Image.LANCZOS)

        # Flatten any transparency in AI art against background color
        # (prevents checkerboard artifacts from semi-transparent pixels)
        art_bg = Image.new("RGBA", (art_diameter, art_diameter), (*fill_rgb, 255))
        art_bg.alpha_composite(art)
        art = art_bg

        # ── 5. Paste art centered on medallion ──
        art_layer = Image.new("RGBA", (cover_w, cover_h), (0, 0, 0, 0))
        paste_x = center_x - art_diameter // 2
        paste_y = center_y - art_diameter // 2
        art_layer.paste(art, (paste_x, paste_y))

        # ── 6. Three-layer composite: canvas + art + template ──
        result = Image.alpha_composite(canvas, art_layer)
        result = Image.alpha_composite(result, template)
        composited_rgb = result.convert("RGB")

        validation_region = Region(
            center_x=center_x,
            center_y=center_y,
            radius=max(20, punch_radius),
            frame_bbox=region_obj.frame_bbox,
            region_type="circle",
        )
```

### What this code does differently from the current 07F implementation:

| Current 07F (broken) | New 07G (fix) |
|---|---|
| Looks for template file on disk | Builds template in memory from loaded cover |
| Falls back to legacy if file missing | No fallback — template is always built |
| Uses `_resolve_medallion_geometry()` for center | Uses fixed FALLBACK_CENTER_X/Y (2864, 1620) |
| No art transparency flattening | Flattens art against background color |
| `art_layer.alpha_composite()` for paste | `art_layer.paste()` for paste |

---

## What NOT to Remove

**Keep ALL existing functions in the file**, including:
- `_find_template_for_cover()`
- `_create_template_for_cover()`
- `_legacy_medallion_composite()`
- `_smart_square_crop()`
- `_load_global_compositing_mask()`
- `_combine_masks()`
- `_build_cover_overlay_with_punch()`
- `_build_circle_feather_mask()`
- `_simple_center_crop()`

They may be called from test code, other scripts, or the rectangle/custom_mask branches. Just replace the else-branch code that calls them in the medallion path.

---

## Validation

### 1. Generate a cover for any book
- AI art must fill the entire medallion opening edge-to-edge
- ZERO visible original cover art at the boundary
- Art must be centered within the frame circle
- Frame ornaments (scrollwork, beads, gold border) fully intact
- Clean anti-aliased edge where art meets frame

### 2. Generate 3 different covers
- All must have identical circle size and centering
- Only the art content should differ

### 3. Check Railway logs
- Must NOT contain "Falling back to legacy compositor pipeline"
- Should NOT see any disk I/O errors related to templates

### 4. Regression check
- If rectangle or custom_mask paths are used by any covers, test one of each

---

## Commit and Push

```bash
git add -A && git commit -m "fix: in-memory PNG template pipeline, no disk/legacy fallback (PROMPT-07G)

Replaces the disk-based template lookup + legacy fallback with a pure
in-memory pipeline. The cover template is built in RAM from the loaded
cover image - no file I/O, no fallback to the broken legacy code.

Key changes:
- Template generated in memory (cover -> RGBA -> punch transparent hole)
- Uses fixed center (2864, 1620) matching all 99 covers
- Art flattened against background color (no transparency artifacts)
- Legacy fallback path eliminated (was silently triggering old bugs)
- Zero failure modes: if cover is loaded, template is guaranteed" && git push
```
