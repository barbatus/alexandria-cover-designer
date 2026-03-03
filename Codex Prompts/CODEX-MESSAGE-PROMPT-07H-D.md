Implement PROMPT-07H-D-DOWNLOAD-EXPORT-OVERHAUL.md

Downloads currently produce a single low-res JPG with a cryptic filename like `1-openrouter_google_gemini-2.5-flash-image-v5-composite-3.jpg`. This needs a complete overhaul.

**What to do:**
1. In `src/static/js/pages/iterate.js`:
   - Replace the `downloadComposite` method to build a ZIP (using JSZip from CDN) containing the composite JPG and raw illustration JPG
   - Both files named after the book: `{title} — {author}.jpg` and `{title} — {author} (illustration).jpg`
   - ZIP named: `{number}. {title} — {author}.zip`
   - Change button label from "⬇ Composite" to "⬇ Download"
   - Update `downloadGenerated` to use the same book-based naming
2. In `src/static/js/app.js`: verify the composited blob is fetched at full resolution (3784×2777), not from a thumbnail

The composite JPG must be exactly 3784×2777 at 300 DPI. Read the full spec for implementation details and validation instructions.

Then: `git add -A && git commit && git push`
