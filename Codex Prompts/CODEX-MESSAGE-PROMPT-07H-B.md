Implement PROMPT-07H-B-CATALOG-DEFAULT-FIX.md

The book dropdown only shows 2 test books ("Sample Book" and "Another Story") instead of the 99 real Alexandria Classics books. The root cause is a config setting, NOT a code bug.

**What to do:**
1. In `config/catalogs.json`, change `"default_catalog": "test-catalog"` to `"default_catalog": "classics"`

That's it. One field in one JSON file. The test catalog was accidentally set as the default. The "classics" catalog (99 books, real titles/authors) already exists and is fully populated. Read the full spec for validation instructions.

Then: `git add -A && git commit && git push`
