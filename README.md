# Amazon Books — Autonomous Manuscript & KDP Packaging Pipeline

![Governance](https://img.shields.io/badge/Governance-REVVEL--STANDARDS-blueviolet)
![CO₂ Avoided](https://img.shields.io/badge/CO%E2%82%82_Avoided-~0.3kg%2Ftitle-brightgreen)
![Cover Art](https://img.shields.io/badge/Cover_Art-Grok_Imagine_%28xAI%29-orange)
![Milestone](https://img.shields.io/badge/celebration-whole--book--pipeline-gold)

One pipeline, three stages: the **orchestrator** writes the book, the
**builder** typesets it into a print interior, the **packager** wraps it in a
print-ready KDP cover (Grok Imagine art) and pre-answers the entire upload
wizard.

Governance: this project follows [REVVEL-STANDARDS.md](REVVEL-STANDARDS.md)
(organization & clarity, greener code, eco-metrics, celebration tags).

## Two ways in

| You have | You need | Run |
| --- | --- | --- |
| A finished book | A new cover only | `packaging/kdp_packager.py --cover-only --pages N --title "..."` |
| Nothing (or drafts) | The whole book **and** the cover | `builder/book_builder.py --from-drafts --title "..."` |
| A manuscript file (.md/.txt) | Typesetting + cover + answers | `builder/book_builder.py --manuscript my_book.md --title "..."` |
| No time for a terminal | Everything, in a browser | `web/` — open `index.html` (also auto-deployed to GitHub Pages) |

## Repo map

### Local Markdown drop folder

With Docker Desktop and the LM Studio API server running, use
`docker compose up -d --build manuscript-inbox`. Drop a UTF-8 `.md` file
in `local-books/inbox/` with this structure (use blank lines around headings):

```markdown
# My Book Title

<!-- target-chapters: 12 -->

## Chapter 1: Opening

Your first chapter goes here.

## Chapter 2: What happened next

Your second chapter goes here.
```

The watcher preserves the input, checkpoints each added chapter, then calls
the builder to make the interior PDF and the packager to produce the print
cover, ebook cover, and `kdp_answers.json`. Find them under
`local-books/output/<book>-<revision>/manuscript_workspace/`. The completed
Markdown and `complete.json` are one level above that folder. The local
service uses Gemma 3 4B and procedural covers. Set `BOOK_LOCAL_MODEL` before
starting Compose to select another loaded LM Studio model.

Use `docker compose logs -f manuscript-inbox` to see progress or errors.
Restart the service to retry a failed draft from its last saved chapter, or
edit the source to start a new revision. A manuscript that typesets below
the builder's paperback minimum stays as a draft. Increase the target
chapter count or add prose before retrying. To drop a large file while the
watcher is running, copy it with a temporary extension and rename it to
`.md` after the copy completes. The local service creates files for review
and manual KDP upload.

### Repository directories

| Path | Purpose |
| --- | --- |
| `orchestrator/` | Autonomous drafting engine: OSINT trend hooks, SQLite dedup telemetry, Voice DNA style lock, Markdown regression linter, cron/daemon modes |
| `builder/` | Compiles drafts → 8.5×11 interior PDF → derives page count → hands off to the packager. Includes `market_scout.py`: free-channel SEO intelligence that picks the length buyers actually prefer per category |
| `packaging/` | Wraparound cover composer (300 DPI, bleed, barcode zone), ebook front, `kdp_answers.json` manifest |
| `prompts/` | Voice DNA few-shot profile, cover & copy prompt packages |
| `web/` | KDP Packaging Studio — fully client-side browser build (no keys, no server) |
| `examples/` | Sample generated package for reference |
| `.github/workflows/` | Draft-structure governance lint + Pages deploy |

## Quick start (onboarding checklist)

1. `pip install -r requirements.txt`
2. **Cover art (Grok Imagine):** get a key at console.x.ai, then
   `export XAI_API_KEY=...` (without it, art falls back to the deterministic
   procedural engine — zero network, zero cost).
3. **Book text:** the orchestrator runs the **OpenRouter model chain first**
   (Nemotron 3 Ultra 550B `:free` → Gemma 4 31B `:free` → Gemma 3 4B paid
   last resort) and falls back to your local LM Studio node
   (`http://localhost:1234/v1/chat/completions`, model `google/gemma-3-4b:3`)
   when the cloud is unreachable. Set `OPENROUTER_API_KEY` (and optionally
   `OPENROUTER_MODELS`, a comma-separated chain) in your environment, or force
   a provider with `--provider local|openrouter|auto`.
   Run `python orchestrator/autonomous_agent_core.py --cron` per cycle.
4. Scout the market (optional, free): `python builder/market_scout.py "short stories anthology"` → target pages, buyer search terms, ink recommendation.
5. Build to that target: `python builder/book_builder.py --from-drafts --title "..." --target-pages auto` — or let the orchestrator draft until the target is met: `python orchestrator/autonomous_agent_core.py --until-pages 220`.
6. Upload day: open the generated `kdp_answers.json` next to the KDP wizard and copy each answer across.
7. **Cloud drafting (optional, free):** the `Autonomous Drafting Pipeline`
   workflow writes every 6 hours on GitHub Actions and commits drafts back to
   `main`. Add secret `OPENROUTER_API_KEY` (required), variable
   `OPENROUTER_MODELS` (optional chain override), secret `XAI_API_KEY`
   (optional covers) under Settings → Secrets and variables → Actions. Run it
   by hand anytime via Actions → Autonomous Drafting Pipeline → Run workflow —
   set *package_book* to `true` to get a full KDP package in `released/`.

## Eco impact (per REVVEL standards)

- **~0.3 kg CO₂ avoided per title**: exact-dimension preflight (spine math
  from the real page count, barcode/safe zones) eliminates the printed
  proof-copy iteration most covers burn through.
- Browser studio runs client-side: no cloud render farm, no upload round
  trips; the procedural art floor means even cover concepts can be drafted
  offline.

## Notes

- AI-content disclosure is pre-answered "Yes" in every manifest — KDP
  requires it for AI-generated text/images; it is not shown to buyers.
- Verify current printing rates in the KDP Royalty Calculator before publish
  day; Amazon revises periodically.
- The web studio never sees your API keys; Grok Imagine runs only in the
  local Python tooling where keys stay in your environment.
