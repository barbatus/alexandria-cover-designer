# PROMPT-07H — Fix Medallion Bleed-Through by Increasing Art Diameter

**Priority:** CRITICAL — Original cover art is visibly bleeding through at the medallion boundary in every generated composite.

**Repo:** `ltvspot/alexandria-cover-designer`  
**Branch:** `master`  
**File to change:** `src/cover_compositor.py` — ONE line change + ONE constant addition.

---

## DESIGN PRESERVATION — DO NOT CHANGE

Only modify `src/cover_compositor.py` as specified below. Do NOT touch `index.html`, sidebar, navigation, color scheme, page layouts, CSS, frontend JS, `src/prompt_generator.py`, or any file not explicitly listed here.

---

## Root Cause

The current `else` branch in `composite_single()` (the medallion compositing pipeline) sets:

```python
art_diameter = punch_radius * 2 + 20  # 10px bleed on each side = 950px
```

(where `punch_radius` is a local variable set to `TEMPLATE_PUNCH_RADIUS = 465` on line 754)

The punch radius is 465px, so art extends only 10px (half of 20) beyond the punch boundary on each side. But the 4x-supersampled anti-aliased circle mask has a **transition zone ~8-12px wide** where alpha goes from 0 → 255. At pixels where alpha is, say, 128, you see **50% original cover art + 50% AI art** — the bleed-through Tim sees in his screenshots.

**The fix:** Increase art diameter so it extends **at least 50px** beyond the punch boundary on each side. This way, the entire anti-alias transition zone composites against AI art (not original cover art), and bleed-through becomes structurally impossible.

---

## The Change

### Step 1: Add a new constant near the top of the file

Find the constant `TEMPLATE_PUNCH_RADIUS = 465` (around line 46). Add one new constant directly after it:

```python
TEMPLATE_PUNCH_RADIUS = 465
TEMPLATE_SUPERSAMPLE_FACTOR = 4
ART_BLEED_PX = 60  # Extra px on each side beyond punch radius to cover AA transition
```

### Step 2: Change ONE line in the `else` branch of `composite_single()`

Find the line (around line 785):

```python
        art_diameter = punch_radius * 2 + 20  # 10px bleed on each side = 950px
```

Replace it with:

```python
        art_diameter = punch_radius * 2 + (ART_BLEED_PX * 2)  # 465*2 + 120 = 1050px
```

That's it. **Do not change anything else in the file.** The rest of the compositing pipeline is correct — the three-layer stack (canvas → art → template) is working. The ONLY problem is that `art_diameter` is too small.

---

## Math Verification

- `TEMPLATE_PUNCH_RADIUS = 465` → the transparent hole in the template has radius 465px
- Old: `punch_radius * 2 + 20 = 950` → art radius = 475 → only 10px overlap beyond punch boundary
- New: `punch_radius * 2 + (ART_BLEED_PX * 2) = 1050` → art radius = 525 → **60px overlap** beyond punch boundary
- The anti-alias transition zone is ~8-12px wide
- 60px > 12px, so the entire transition composites against solid AI art
- The template layer (topmost) covers everything outside the 465px hole anyway, so the extra art is invisible — it's hidden behind the original cover frame/ornaments

---

## What NOT to Change

**Leave ALL of these completely untouched:**
- The `if` branch (rectangle compositing)
- The `elif` branch (custom_mask compositing)
- The rest of the `else` branch — canvas creation, art cropping, art_layer paste, template creation, three-layer composite, validation_region
- All helper functions: `_find_template_for_cover()`, `_create_template_for_cover()`, `_legacy_medallion_composite()`, `_simple_center_crop()`, `_sample_cover_background()`, etc.
- The constants: `FALLBACK_CENTER_X`, `FALLBACK_CENTER_Y`, `FALLBACK_RADIUS`, `TEMPLATE_PUNCH_RADIUS`
- The geometry resolution, the template loading, everything else

**DO NOT refactor, restructure, or "improve" any other code.** This is a one-line surgical fix.

---

## Validation

### 1. Generate a cover for any book
- AI art must fill the entire medallion opening edge-to-edge
- **ZERO** visible original cover art at the medallion boundary
- Frame ornaments (scrollwork, beads, gold border) must be fully intact and undamaged
- Clean anti-aliased edge where art meets frame

### 2. Pixel-level check (REQUIRED)
After generating a composite, zoom in to 300-400% at the medallion boundary. At EVERY point around the circle where the frame meets the art:
- There should be NO trace of the original cover's artwork visible
- The transition should go cleanly from AI art → frame ornaments
- If you see any "ghosting" or "double image" effect, the fix did NOT work

### 3. Generate 3 variants
- All must have identical circle size and centering
- Only the art content should differ
- Check all 3 for bleed-through at the boundary

---

## Commit and Push

```bash
git add -A && git commit -m "fix: increase art_diameter from 950 to 1050px to eliminate medallion bleed-through (PROMPT-07H)

art_diameter was punch_radius*2+20 = 950px, giving only 10px overlap
beyond the 465px punch boundary. The 4x-supersampled anti-aliased mask
has a ~8-12px transition zone, so original cover art showed through at
semi-transparent pixels.

Changed to punch_radius*2+(ART_BLEED_PX*2) = 1050px, giving 60px
overlap — fully covering the AA transition. Bleed-through is now
structurally impossible. Added ART_BLEED_PX=60 constant." && git push
```
