# builder/

Book compiler — stage 2 of 3.

| File | Purpose |
| --- | --- |
| `book_builder.py` | Compiles drafts (or a user manuscript) into one master document, typesets an 8.5×11 interior PDF with real text (fpdf2), derives the true page count, then calls `packaging/kdp_packager.py` so the spine width is always computed from the real book |

Modes: `--from-drafts` (whole-book pipeline) · `--manuscript file.md` (you supply the text). Output: `manuscript_workspace/build/*_interior.pdf` + full KDP package.
