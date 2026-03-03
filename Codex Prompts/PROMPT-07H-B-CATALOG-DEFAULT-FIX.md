# PROMPT-07H-B — Fix Book Dropdown Showing Only 2 Test Books (Default Catalog)

**Priority:** HIGH — The book selector dropdown shows only "Sample Book" and "Another Story" instead of the 99 real Alexandria Classics books.

**Repo:** `ltvspot/alexandria-cover-designer`  
**Branch:** `master`  
**File to change:** `config/catalogs.json` — ONE field change.

---

## DESIGN PRESERVATION — DO NOT CHANGE

Only modify `config/catalogs.json` as specified below. Do NOT touch `index.html`, sidebar, navigation, color scheme, page layouts, CSS, frontend JS, `src/cover_compositor.py`, `src/prompt_generator.py`, `scripts/quality_review.py`, or any file not explicitly listed here.

---

## Root Cause

In `config/catalogs.json`, the default catalog is set to the **test catalog** which only contains 2 placeholder books:

```json
{
  "default_catalog": "test-catalog",
  ...
}
```

The system has two catalogs defined:
- **`classics`** — 99 real Alexandria Classics books with proper titles and authors (data in `config/book_catalog.json`)
- **`test-catalog`** — 2 placeholder books ("Sample Book" and "Another Story") meant for development only (data in `config/book_catalog_test-catalog.json`)

**How the bug manifests:**

1. The frontend `drive.js` calls `/cgi-bin/catalog.py` and `/cgi-bin/catalog.py/status` **without a `?catalog=` parameter**
2. The server (`scripts/quality_review.py`) resolves the catalog using the `default_catalog` from `config/catalogs.json`
3. Since `default_catalog` is `"test-catalog"`, the server builds the CGI catalog cache from the test catalog data (2 books)
4. The book dropdown populates from this cache and only shows 2 books

**Important:** The standalone `cgi-bin/catalog.py` file in the repo is **dead code** — it is never executed. The server (`scripts/quality_review.py`) handles all `/cgi-bin/` routes inline. The CGI catalog cache (`catalog_cache.json`) is built from the active runtime's iterate data, NOT from Google Drive sync. So the fix must target the catalog config, not the CGI script.

---

## The Change

In `config/catalogs.json`, change:

```json
"default_catalog": "test-catalog"
```

to:

```json
"default_catalog": "classics"
```

That's it. **One field. Do not change anything else.**

The full file after the change should look like:

```json
{
  "default_catalog": "classics",
  "catalogs": [
    {
      "id": "classics",
      "name": "Alexandria Classics",
      "book_count": 99,
      "catalog_file": "config/book_catalog.json",
      "prompts_file": "config/book_prompts.json",
      "input_covers_dir": "Input Covers",
      "output_covers_dir": "Output Covers",
      "cover_style": "navy_gold_medallion",
      "status": "complete"
    },
    {
      "id": "test-catalog",
      "name": "Alexandria Test Catalog",
      "book_count": 2,
      "catalog_file": "config/book_catalog_test-catalog.json",
      "prompts_file": "config/book_prompts_test-catalog.json",
      "input_covers_dir": "tmp/test_catalog_input",
      "output_covers_dir": "Output Covers Test",
      "cover_style": "navy_gold_medallion",
      "status": "imported"
    }
  ]
}
```

---

## Why This Fixes It

- After deploy, when the frontend calls `/cgi-bin/catalog.py` without a `?catalog=` param, the server defaults to `classics` instead of `test-catalog`
- The `classics` catalog has 99 books with proper titles and authors in `config/book_catalog.json`
- The iterate data is built from this catalog, populating the CGI cache with all 99 books
- The book dropdown will show all 99 real books with correct titles and authors
- The test catalog remains available via `?catalog=test-catalog` for development use

---

## What NOT to Change

**Leave ALL of these completely untouched:**
- `scripts/quality_review.py` — the server code is working correctly; it just defaults to the wrong catalog
- `cgi-bin/catalog.py` — dead code, never used by the running server
- `src/static/js/drive.js` — the frontend code is fine; fixing the default catalog solves the issue without requiring URL parameter changes
- `config/book_catalog.json` — the actual book data is correct and complete
- `config/book_catalog_test-catalog.json` — keep the test catalog as-is for development

**DO NOT refactor, restructure, or "improve" any other code.** This is a one-field config change.

---

## Validation

### 1. Open the app in the browser
- Navigate to `https://web-production-900a7.up.railway.app/#iterate`
- The book dropdown should populate with 99 books (real titles and authors like "A Room with a View — E. M. Forster", etc.)
- You should NOT see "Sample Book" or "Another Story" in the dropdown (unless you explicitly switch to test-catalog)

### 2. Check the catalog status
- Open browser DevTools → Console
- Run: `fetch('/cgi-bin/catalog.py/status').then(r=>r.json()).then(d=>console.log(d))`
- The `count` field should show 99 (not 2)

### 3. Check the catalog data
- Run: `fetch('/cgi-bin/catalog.py').then(r=>r.json()).then(d=>console.log(d.count, d.books[0]))`
- Should show count 99 and first book should be a real title (e.g., "A Room with a View")
- Books should have `title`, `author`, and `folder_name` populated

### 4. Verify test catalog is still accessible
- Run: `fetch('/cgi-bin/catalog.py?catalog=test-catalog').then(r=>r.json()).then(d=>console.log(d.count))`
- Should still return 2 books (test catalog preserved)

---

## Commit and Push

```bash
git add -A && git commit -m "fix: change default catalog from test-catalog to classics (PROMPT-07H-B)

default_catalog in config/catalogs.json was set to 'test-catalog' (2 placeholder
books) instead of 'classics' (99 real Alexandria books). The frontend CGI
endpoints don't pass a catalog parameter, so they always used the default.

Changed default_catalog to 'classics' so all API endpoints return real book
data by default. Test catalog remains accessible via ?catalog=test-catalog." && git push
```
