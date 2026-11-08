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
3. **Book text (optional):** point `orchestrator/autonomous_agent_core.py`'s
   `API_URL` at your local inference node (LM Studio default:
   `http://localhost:1234/v1/chat/completions`) and run
   `python orchestrator/autonomous_agent_core.py --cron` per cycle.
4. Scout the market (optional, free): `python builder/market_scout.py "short stories anthology"` → target pages, buyer search terms, ink recommendation.
5. Build to that target: `python builder/book_builder.py --from-drafts --title "..." --target-pages auto` — or let the orchestrator draft until the target is met: `python orchestrator/autonomous_agent_core.py --until-pages 220`.
6. Upload day: open the generated `kdp_answers.json` next to the KDP wizard and copy each answer across.

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
