Implement PROMPT-07H-COMPOSITOR-ART-DIAMETER-FIX.md

This is a ONE-LINE fix in `src/cover_compositor.py`. The AI art diameter in the medallion compositing pipeline is too small (950px), leaving only 10px overlap beyond the punch boundary. The anti-aliased mask transition zone is ~8-12px, so original cover art bleeds through.

**What to do:**
1. Add constant `ART_BLEED_PX = 60` after `TEMPLATE_SUPERSAMPLE_FACTOR = 4` (near line 47)
2. Change the ONE line `art_diameter = punch_radius * 2 + 20` to `art_diameter = punch_radius * 2 + (ART_BLEED_PX * 2)`
3. This changes art_diameter from 950px to 1050px — 60px overlap on each side instead of 10px

**Do NOT change anything else.** No refactoring, no restructuring. Read the full spec for pixel-level validation instructions.

Then: `git add -A && git commit && git push`
