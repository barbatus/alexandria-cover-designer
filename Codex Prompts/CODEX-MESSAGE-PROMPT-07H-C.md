Implement PROMPT-07H-C-VARIANT-DIVERSITY-FIX.md

Variants 1 and 2 always use the same two war-themed styles ("sevastopol-conflict" and "cossack-epic"), making all outputs look like dark military paintings regardless of book genre.

**What to do:**
1. In `src/prompt_generator.py`, change `FIXED_VARIANT_STYLE_IDS` from `["sevastopol-conflict", "cossack-epic"]` to `["pre-raphaelite-v2", "baroque-v2"]`
2. In `CURATED_VARIANT_STYLE_IDS`, replace `"pre-raphaelite-v2"` with `"sevastopol-conflict"` (moves war style to curated pool instead of forced)

Two constant changes. No refactoring. Read the full spec for validation instructions.

Then: `git add -A && git commit && git push`
