# packaging/

KDP packager — stage 3 of 3.

| File | Purpose |
| --- | --- |
| `kdp_packager.py` | Wraparound print cover (300 DPI, bleed + safe + barcode zones) as PDF/PNG, ebook front JPG, pre-answered `kdp_answers.json` upload manifest |

Modes: full book (called by `builder/`) · `--cover-only` (you have a book, need a cover). Art backends: `--art-backend xai` (Grok Imagine, needs `XAI_API_KEY`, default) · `openrouter` · `procedural` (offline floor).
