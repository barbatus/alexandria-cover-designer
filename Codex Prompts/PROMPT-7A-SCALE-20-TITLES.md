# Prompt 7A — Scale to 20 Titles + Prompt Tuning + Model Comparison

Read `Project state Alexandria Cover designer.md` for full context, especially decision D23 (start with 20 titles).

## What exists

- Full pipeline verified with real API generation (6C)
- At least 1-3 books successfully generated end-to-end with real AI images
- Quality gate, compositing, and export all working
- Webapp with /iterate and /review pages functional

## Task 1: Generate covers for books 1-20

Run the pipeline for the first 20 books with the best-performing model from 6C:

```bash
python3 src/pipeline.py --books 1-20 --variants 5 --resume
```

Use `--resume` so it skips any books already completed in 6C.

Monitor and report:
- Total generation time
- Total cost (from generation history)
- Success/failure count per book
- Any books that failed all 5 variants

## Task 2: Quality analysis

After generation completes:
1. Run quality gate on all 100 images (20 books × 5 variants)
2. Generate `data/quality_report.md`
3. Identify:
   - Books with ALL variants scoring below 0.7 (need prompt rewriting)
   - Books with high variation in scores (prompts are inconsistent)
   - Common quality issues across all books (e.g., text artifacts, wrong aspect ratio, color mismatch)
   - Top 5 best-scoring books and their prompts (what's working well)

## Task 3: Prompt tuning for underperformers

For any book where ALL 5 variants scored below 0.7:
1. Analyze the prompts in `config/book_prompts.json` for that book
2. Identify what's causing poor results (too vague? wrong art style? conflicting terms?)
3. Rewrite the 5 prompts for that book using the style anchors that performed best across other books
4. Save the improved prompts
5. Re-generate 5 variants for each fixed book
6. Compare new scores against old scores

## Task 4: Model comparison (if multiple providers available)

For 5 representative books (pick books 1, 5, 10, 15, 20):
```bash
python3 src/pipeline.py --book 1 --all-models --variants 3
python3 src/pipeline.py --book 5 --all-models --variants 3
python3 src/pipeline.py --book 10 --all-models --variants 3
python3 src/pipeline.py --book 15 --all-models --variants 3
python3 src/pipeline.py --book 20 --all-models --variants 3
```

Generate `data/model_rankings.json` with aggregated quality scores per model.
Identify the best model for this style of illustration.

If only one provider is available, skip this task and note it as SKIPPED.

## Task 5: Update prompt library with winners

Save the top 10 best-performing prompts to `config/prompt_library.json`:
- Extract the prompt text from the highest-scoring variants
- Make them title-agnostic (replace specific book title with `{title}`)
- Tag with appropriate style anchors
- Set quality_score from actual gate scores
- These will be available in the /iterate page prompt library panel

## Task 6: Regenerate catalog PDF

After all 20 books have real covers:
```bash
python3 scripts/generate_catalog.py --output-dir "Output Covers"
```

The catalog should now show real AI-generated covers instead of placeholder images.

## Verification Checklist

1. 20 books processed (or attempted) — PASS/FAIL
2. Total images generated (target: ~100) — count: ___
3. At least 80% of books (16+) have at least 1 variant scoring ≥ 0.7 — PASS/FAIL
4. `data/quality_report.md` generated with analysis — PASS/FAIL
5. `data/quality_scores.json` has entries for all generated images — PASS/FAIL
6. Underperforming books identified and prompts rewritten — PASS/FAIL
7. Re-generated variants for fixed books score higher than originals — PASS/FAIL
8. Model comparison completed for 5 books (or SKIPPED if single provider) — PASS/FAIL
9. `data/model_rankings.json` generated (or SKIPPED) — PASS/FAIL
10. Top 10 prompts saved to `config/prompt_library.json` — PASS/FAIL
11. Composited covers for all 20 books in `Output Covers/` — PASS/FAIL
12. Catalog PDF regenerated with real covers — PASS/FAIL
13. Total cost documented — PASS/FAIL
14. Total generation time documented — PASS/FAIL

Run every check. Report PASS/FAIL for each. Include total cost and generation time in your report.

Save output to `Codex Output Answers/PROMPT-7A-OUTPUT.md`.
