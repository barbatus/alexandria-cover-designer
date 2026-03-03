# PROMPT-07H-C — Fix Perceived Lack of Variation Between Variants

**Priority:** MEDIUM — Variants 1 and 2 always use the same two war-themed styles, making outputs look similar despite different AI art content.

**Repo:** `ltvspot/alexandria-cover-designer`  
**Branch:** `master`  
**File to change:** `src/prompt_generator.py` — Change ONE constant.

---

## DESIGN PRESERVATION — DO NOT CHANGE

Only modify `src/prompt_generator.py` as specified below. Do NOT touch `index.html`, sidebar, navigation, color scheme, page layouts, CSS, frontend JS, `src/cover_compositor.py`, or any file not explicitly listed here.

---

## Root Cause

In `src/prompt_generator.py`, `select_diverse_styles()` uses a **2+3+5 plan**:
- Variants 1-2: Always `FIXED_VARIANT_STYLE_IDS` = `["sevastopol-conflict", "cossack-epic"]`
- Variants 3-5: Seeded shuffle of `CURATED_VARIANT_STYLE_IDS` (8 diverse styles)
- Variants 6-10: Wildcard pool

The problem: "sevastopol-conflict" (Crimean War military painting) and "cossack-epic" (cavalry battle painting) are **both** dark military/war themes with very similar palettes (crimson, burnt sienna, smoke grey, gold). When a user generates 2-5 variants, the first two ALWAYS look like war paintings regardless of the book's subject matter.

For a book like "A Room with a View" (Edwardian romance set in Florence), getting two military battle paintings as the first two options is jarring and makes the system look like it's producing identical outputs.

---

## The Change

### Replace the FIXED_VARIANT_STYLE_IDS constant

Find (around line 88-91):

```python
FIXED_VARIANT_STYLE_IDS: list[str] = [
    "sevastopol-conflict",
    "cossack-epic",
]
```

Replace with:

```python
FIXED_VARIANT_STYLE_IDS: list[str] = [
    "pre-raphaelite-v2",
    "baroque-v2",
]
```

### Also update CURATED_VARIANT_STYLE_IDS to backfill

Since we moved "pre-raphaelite-v2" to fixed, remove it from curated and add one of the removed war styles as a curated option (so it's still available, just not forced):

Find (around line 93-102):

```python
CURATED_VARIANT_STYLE_IDS: list[str] = [
    "golden-atmosphere",
    "venetian-renaissance",
    "dutch-golden-age",
    "dark-romantic-v2",
    "pre-raphaelite-v2",
    "art-nouveau-v2",
    "ukiyo-e-v2",
    "noir-v2",
]
```

Replace with:

```python
CURATED_VARIANT_STYLE_IDS: list[str] = [
    "golden-atmosphere",
    "venetian-renaissance",
    "dutch-golden-age",
    "dark-romantic-v2",
    "sevastopol-conflict",
    "art-nouveau-v2",
    "ukiyo-e-v2",
    "noir-v2",
]
```

**Do not change anything else.** No refactoring, no restructuring.

---

## Why These Choices

**"pre-raphaelite-v2"** (variant 1): Lush, hyper-detailed, jewel-toned colors, flowing hair, botanical detail, ethereal beauty. Visually VERY different from the next style and extremely versatile across literary genres.

**"baroque-v2"** (variant 2): Dramatic chiaroscuro, crimson + gold, dynamic diagonal composition, extreme physicality. Totally different look from Pre-Raphaelite — dark vs. bright, tight vs. flowing, dramatic vs. serene.

Together, these two anchors give the user two strikingly different looks for ANY book as their first two variants. War themes still appear as curated options (variant 3+) when the shuffle selects them.

---

## Validation

### 1. Generate 5 variants for a non-war book (e.g., "A Room with a View", "Emma", "The Secret Garden")
- Variant 1 should have a Pre-Raphaelite style (lush, jewel-toned, botanical detail)
- Variant 2 should have a Baroque style (dramatic chiaroscuro, diagonal composition)
- Variants 3-5 should be visibly different from each other and from 1-2
- All 5 should feel appropriate for the book's subject matter

### 2. Generate 5 variants for a war/adventure book (e.g., "War and Peace", "The Iliad")
- Same style sequence but content should adapt to the subject
- Still visually diverse across all 5 variants

---

## Commit and Push

```bash
git add -A && git commit -m "fix: diversify fixed variant styles from war themes to Pre-Raphaelite + Baroque (PROMPT-07H-C)

FIXED_VARIANT_STYLE_IDS always forced 'sevastopol-conflict' and
'cossack-epic' as the first two variants. Both are dark military/war
themes with similar palettes, making outputs look identical for
non-war books.

Changed fixed anchors to 'pre-raphaelite-v2' (lush, botanical,
jewel-toned) and 'baroque-v2' (dramatic chiaroscuro). These two
produce strikingly different results and work well across all genres.
War styles moved to curated pool (still available from variant 3+)." && git push
```
