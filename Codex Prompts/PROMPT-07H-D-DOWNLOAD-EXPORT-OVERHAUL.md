# PROMPT-07H-D — Download/Export Overhaul: ZIP Packaging, Correct Naming, Full Resolution

**Priority:** HIGH — Downloads produce wrong-sized images with meaningless filenames. Must match source cover conventions exactly.

**Repo:** `ltvspot/alexandria-cover-designer`  
**Branch:** `master`  
**Files to change:**
- `src/static/js/pages/iterate.js` — download button logic and filenames
- `src/static/js/app.js` — ensure full-resolution composite blob is stored

---

## DESIGN PRESERVATION — DO NOT CHANGE

Only modify the files listed above. Do NOT touch `index.html`, sidebar, navigation, color scheme, page layouts, CSS, `src/cover_compositor.py`, `src/prompt_generator.py`, `config/catalogs.json`, or any file not explicitly listed here.

---

## Current Problems

### Problem 1: Download dimensions are wrong
The downloaded composite JPG is ~1472×1080 instead of the source cover dimensions (3784×2777 at 300 DPI). The server-side compositor (`src/cover_compositor.py`) saves composites at full resolution with `quality=100, subsampling=0, dpi=(300, 300)` — but the frontend is either:
- Storing a lower-resolution blob from a thumbnail endpoint, OR
- The `fetchImageBlob` call in `app.js` is fetching a path that returns a resized image

**The download MUST produce a JPG at exactly 3784×2777 pixels at 300 DPI** — identical dimensions to the source cover files.

### Problem 2: Download is a single JPG, should be a ZIP
Currently clicking "Composite" downloads a single JPG. Tim needs a ZIP file containing:
1. **Composite JPG** — the final composited cover at full resolution (3784×2777 at 300 DPI)
2. **Raw illustration JPG** — the AI-generated illustration (the raw image before compositing)

Both files must use the naming convention from the source covers (see below).

### Problem 3: Filenames don't match source naming convention
Current filename: `1-openrouter_google_gemini-2.5-flash-image-v5-composite-3.jpg`

The output naming must mirror the source cover naming convention in Google Drive:
- **Source folder**: `1. A Room with a View — E. M. Forster`
- **Source files**: `A Room with a View — E. M. Forster.jpg`, `.ai`, `.pdf`

The download ZIP and its contents should be named following the same pattern:
- **ZIP filename**: `{number}. {title} — {author}.zip`
- **Composite JPG inside ZIP**: `{title} — {author}.jpg`
- **Raw illustration inside ZIP**: `{title} — {author} (illustration).jpg`

Where `{number}`, `{title}`, and `{author}` come from the book's catalog entry.

Example for book 1:
- ZIP: `1. A Room with a View — E. M. Forster.zip`
- Inside: `A Room with a View — E. M. Forster.jpg` (composite)
- Inside: `A Room with a View — E. M. Forster (illustration).jpg` (raw)

### Problem 4: Button label should say "Download" not "Composite"
The "⬇ Composite" button should say "⬇ Download" since it now downloads a ZIP package.

---

## The Changes

### Change 1: Fix composite blob resolution in `src/static/js/app.js`

In the `compositing` step (around line 414-428), verify that `fetchImageBlob` is fetching from the FULL-RESOLUTION server path, not from a thumbnail URL. The `best.compositedPath` should point to the full-res file (e.g., `Output Covers/classics/1/variant_3.jpg`).

If the composited blob is being sourced from a thumbnail or preview path, change it to use the direct file path. The blob stored in `job.composited_image_blob` MUST be the full-resolution image.

Add a debug check: after fetching the blob, verify its size is reasonable (a 3784×2777 JPG at quality 100 should be 1-6 MB, NOT ~100-600 KB which would indicate a thumbnail).

### Change 2: Replace single-file download with ZIP in `src/static/js/pages/iterate.js`

**Step 2a: Add JSZip dependency**

Add JSZip via CDN to the page. In `src/static/js/pages/iterate.js` (or in the HTML that loads it), ensure JSZip is available. The simplest approach: add a dynamic import at the top of the download function that loads JSZip from CDN if not already loaded:

```javascript
async function ensureJSZip() {
  if (window.JSZip) return window.JSZip;
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';
    script.onload = () => resolve(window.JSZip);
    script.onerror = () => reject(new Error('Failed to load JSZip'));
    document.head.appendChild(script);
  });
}
```

**Step 2b: Replace `downloadComposite` method**

Replace the `downloadComposite` method (lines 796-805) with a new method that builds a ZIP:

```javascript
async downloadComposite(jobId) {
  const job = DB.dbGet('jobs', jobId);
  if (!job) return;

  // Get book metadata for naming
  const book = DB.dbGet('books', job.book_id);
  const title = book?.title || `Book ${job.book_id}`;
  const author = book?.author || 'Unknown';
  const number = book?.number || job.book_id;
  const baseName = `${title} — ${author}`;
  const zipName = `${number}. ${baseName}.zip`;

  // Get image sources
  const compositeHref = resolvePreviewSources(job, 'download-composite', false)[0] || '';
  const rawHref = resolvePreviewSources(job, 'download-raw', true)[0] || '';

  if (!compositeHref && !rawHref) return;

  try {
    const JSZip = await ensureJSZip();
    const zip = new JSZip();

    // Fetch composite at full resolution
    if (compositeHref) {
      const resp = await fetch(compositeHref, { cache: 'no-store' });
      if (resp.ok) {
        const blob = await resp.blob();
        zip.file(`${baseName}.jpg`, blob);
      }
    }

    // Fetch raw illustration
    if (rawHref) {
      const resp = await fetch(rawHref, { cache: 'no-store' });
      if (resp.ok) {
        const blob = await resp.blob();
        zip.file(`${baseName} (illustration).jpg`, blob);
      }
    }

    // Generate and download ZIP
    const zipBlob = await zip.generateAsync({ type: 'blob' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(zipBlob);
    a.download = zipName;
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (err) {
    console.error('ZIP download failed:', err);
    // Fallback: download composite as single file
    if (compositeHref) {
      const a = document.createElement('a');
      a.href = compositeHref;
      a.download = `${baseName}.jpg`;
      a.click();
    }
  }
},
```

**Step 2c: Update `downloadGenerated` method for consistent naming**

Replace the `downloadGenerated` method (lines 807-816):

```javascript
downloadGenerated(jobId) {
  const job = DB.dbGet('jobs', jobId);
  if (!job) return;
  const href = resolvePreviewSources(job, 'download-raw', true)[0] || '';
  if (!href) return;

  const book = DB.dbGet('books', job.book_id);
  const title = book?.title || `Book ${job.book_id}`;
  const author = book?.author || 'Unknown';
  const baseName = `${title} — ${author}`;

  const a = document.createElement('a');
  a.href = href;
  a.download = `${baseName} (illustration).jpg`;
  a.click();
},
```

**Step 2d: Change the button label**

Find (around line 714):
```javascript
<button class="btn btn-secondary btn-sm" data-dl-comp="${job.id}" ${showDownloads ? '' : 'disabled'}>⬇ Composite</button>
```

Replace with:
```javascript
<button class="btn btn-secondary btn-sm" data-dl-comp="${job.id}" ${showDownloads ? '' : 'disabled'}>⬇ Download</button>
```

---

## Important Notes on Book Metadata Access

The book metadata (title, author, number) is available in the frontend via `DB.dbGet('books', bookId)` since books are stored in IndexedDB when the catalog loads. The `job.book_id` field contains the book number.

If `DB.dbGet('books', job.book_id)` returns null (e.g., before catalog sync), fall back gracefully using the job's existing data.

---

## What NOT to Change

**Leave ALL of these completely untouched:**
- `src/cover_compositor.py` — server-side compositing is correct
- `src/static/js/compositor.js` — client-side compositing logic
- `src/static/js/drive.js` — catalog loading
- The generation pipeline in `app.js` (except the blob resolution fix)
- All other pages (review, compare, batch, etc.)
- The "⬇ Raw" button behavior — keep it as a single-file JPG download (with corrected naming)
- The "💾 Prompt" button — leave as-is

---

## Validation

### 1. Generate a cover for any book (e.g., Book 1 — "A Room with a View")

### 2. Click "⬇ Download" (was "⬇ Composite")
- A ZIP file should download named `1. A Room with a View — E. M. Forster.zip`
- Inside the ZIP:
  - `A Room with a View — E. M. Forster.jpg` — the full composite
  - `A Room with a View — E. M. Forster (illustration).jpg` — the raw AI art

### 3. Verify composite dimensions
- Open the composite JPG from the ZIP
- Dimensions MUST be **3784 × 2777 pixels**
- DPI MUST be **300**
- File size should be 1-6 MB (NOT ~600 KB which would indicate a thumbnail)
- The medallion/ornaments must be fully intact

### 4. Click "⬇ Raw"
- Downloads a single JPG named `A Room with a View — E. M. Forster (illustration).jpg`

### 5. Test with a book that has special characters (e.g., Book 2: "Moby Dick' Or, The Whale")
- ZIP name should handle the apostrophe and comma gracefully
- Files inside ZIP should be named correctly

---

## Commit and Push

```bash
git add -A && git commit -m "feat: ZIP download with correct naming and full-resolution composites (PROMPT-07H-D)

Download button now produces a ZIP containing the full-resolution composite
JPG (3784×2777 at 300 DPI) and the raw AI illustration, both named after
the book's title and author matching the source cover convention.

Changes:
- Replaced single-file composite download with ZIP (via JSZip CDN)
- Download filenames use '{title} — {author}' pattern from catalog
- Raw download also uses consistent book-based naming
- Button label changed from 'Composite' to 'Download'
- Ensured composite blob is fetched at full resolution" && git push
```
