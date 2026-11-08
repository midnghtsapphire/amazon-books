# orchestrator/

Autonomous drafting engine — stage 1 of 3.

| File | Purpose |
| --- | --- |
| `autonomous_agent_core.py` | OSINT trend harvesting (Google Trends RSS → HackerNews fallback), SQLite keyword dedup, Voice DNA style lock (from `../prompts/few-shot-voice-examples.md`), Markdown structural regression linter, git-autocommitted drafts, daemon + `--cron` modes |

Modes: `python autonomous_agent_core.py` (hourly daemon) · `--cron` (single pass) · `--package-book` (hand off to `builder/` after each successful cycle) · `--until-pages N` (keep drafting until the manuscript reaches N estimated pages — feed it `builder/market_scout.py`'s target — then auto-package and stop).

Output: `manuscript_workspace/drafts/*.md` + `pipeline_telemetry.db`. Governance lint runs in CI on every push (`.github/workflows/validate-drafts.yml`).
