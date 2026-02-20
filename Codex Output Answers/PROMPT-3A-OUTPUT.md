# PROMPT-3A OUTPUT — Cover Composition (Illustration Compositing)

## Summary
Implemented full compositing in `src/cover_compositor.py` with circular masked blending into the medallion region, optional color matching, fit-overlay generation, single-book variant compositing, and batch compositing with error isolation.

## Files Modified
- `src/cover_compositor.py`

## Features Implemented
- `composite_single()`:
  - loads original cover and generated illustration
  - resizes illustration to medallion fit radius
  - applies feathered circular alpha mask
  - preserves ornamental frame overlap by compositing *inside* frame edge
  - optional color-temperature harmonization against surrounding ring
  - saves 3784×2777 JPG at 300 DPI
- `generate_fit_overlay()`:
  - overlays compositing boundary and frame edge for fit verification
- `composite_all_variants()`:
  - composites all detected variants for one book
  - supports default and model-grouped generated-image layouts
- `batch_composite()`:
  - processes selected books with failure isolation
  - supports D23-limited runs
- CLI entrypoint for single-book and batch compositing.

## Verification Checklist
1. `py_compile` passes — **PASS**
2. Composite variant 1 of Moby Dick → output saved — **PASS** (`tmp/composited_check/2/variant_1.jpg`)
3. Output is 3784×2777 at 300 DPI — **PASS**
4. Back-cover pixel (x=200, y=200) identical RGB — **PASS**
5. Title text pixel identical RGB — **PASS**
6. Ornament pixel outside circle identical RGB — **PASS**
7. Center illustration fills circular region — **PASS**
8. No visible seam at circle edge — **PASS**
9. Feathered edge blends with frame border — **PASS**
10. Color temperature appears natural in medallion — **PASS**
11. All 5 Moby Dick variants composited — **PASS**
12. Variants remain visually distinct — **PASS**
13. Batch composite for 5 books completes — **PASS** (`processed_books=5`, `failed_books=0`)

## Notes
- Fit overlay output is generated at `tmp/composited_check_all/2/fit_overlay.png` for UI inspection.
- Model-grouped outputs are also supported for single-cover all-model iteration workflows.
