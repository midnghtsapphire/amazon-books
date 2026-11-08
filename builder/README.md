# builder/

Book compiler + market intelligence — stage 2 of 3.

| File | Purpose |
| --- | --- |
| `book_builder.py` | Compiles drafts (or a user manuscript) into one master document, typesets an 8.5×11 interior PDF with real text (fpdf2), derives the true page count, then calls `packaging/kdp_packager.py` so the spine width is always computed from the real book. `--target-pages auto` compares against the market target |
| `market_scout.py` | Free-channel SEO/demand scout: ratings-weighted page-length stats per category (Google Books API), buyer search queries (Amazon autocomplete), length-vs-print-cost ink guardrail, offline genre matrix fallback. No keys, no paid tools |

Modes: `--from-drafts` (whole-book pipeline) · `--manuscript file.md` (you supply the text). Length targeting: `python market_scout.py "dark fantasy"` to scout, then `--target-pages auto` at build, or `orchestrator/... --until-pages N` to keep drafting until the book is long enough.
