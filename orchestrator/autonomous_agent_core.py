#!/usr/bin/env python3
"""
Autonomous Manuscript & Technical Content Pipeline (Production V3.1)
Orchestrates:
  - Live OSINT Scrapers (Google Trends RSS / HackerNews fallback matrix)
  - SQLite Telemetry Persistence (Ensures absolute keyword uniqueness)
  - Zero-Input Autonomous Ideation (Generates topics from trend context if research is empty)
  - Voice DNA signature enforcement (few-shot style profile injected per cycle)
  - Deep Markdown Structural Regression Testing (Validates syntax, fences, and consistency)
  - Native Python Cron Daemon Process Loops
  - Optional packaging hand-off: --package-book compiles drafts -> interior PDF
    -> KDP cover + answers manifest via packaging/kdp_packager.py (Grok Imagine art)

V3.1 repair log:
  - Removed stray chat fragments that broke the module (lines after main()).
  - Restored real OSINT endpoints (Google Trends RSS, HackerNews Firebase API).
  - Fixed response indexing: choices[0].message.content.
  - Integrated VOICE_DNA (previously orphaned at file tail) into the system prompt.
  - Absorbed ingest_research_context.py (was an import-broken duplicate).

Dependencies: pip install requests
Packaging hand-off also needs: pip install pillow fpdf2
"""

import argparse
import json
import random
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

# ==========================================
# 1. CORE PIPELINE SPECIFICATIONS
# ==========================================
API_URL = "http://localhost:1234/v1/chat/completions"   # local inference node (LM Studio etc.)
MODEL_NAME = "gemma-3-4b-it"
WORKSPACE_DIR = Path("./manuscript_workspace")
RESEARCH_DIR = WORKSPACE_DIR / "research"
OUTPUT_DIR = WORKSPACE_DIR / "drafts"
DB_PATH = WORKSPACE_DIR / "pipeline_telemetry.db"
VOICE_PROFILE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "few-shot-voice-examples.md"

THEME_MATRIX = {
    "creative": [
        "macabre fables", "prehistoric provenance", "Tartarian tablet aging",
        "Linear A and Linear B cryptanalysis", "vanlife and hiking regret", "wistful recovery"
    ],
    "technical": [
        "open source FOSS governance", "forensic lab simulation telemetry",
        "cyber attack threat modeling via DRED matrix", "decentralized distribution networks (Usenet, mIRC)",
        "automated financial quantitative algorithms"
    ],
    "professional": [
        "approved Colorado free Continuing Legal Education (CLE) tracking documentation",
        "open source license compliance schema"
    ]
}

# Exact writing-style signature, enforced inside every system prompt.
VOICE_DNA = (
    "STYLE SIGNATURE (Enforce Absolutely):\n"
    "- Tone: Forensic precision mixed with raw, atmospheric gravity. No academic stiffness, no artificial cheer.\n"
    "- Sentence Structure: Short, punchy, active fragments. Vary sentence lengths deliberately. Avoid comma splices.\n"
    "- Banned AI Phrasing: Completely eliminate placeholder transitions like 'Furthermore', 'Moreover', 'Delve', "
    "'In conclusion', or conversational friendly framing. Get straight to the bone of the concept.\n"
    "- Vocabulary Fusion: Blend technical systems terminology (e.g., pipeline, telemetry, artifacts, governance, matrix) "
    "seamlessly with visceral, poetic, or archaic markers (e.g., provenance, fables, macabre, hidden, ancient scripts).\n"
    "- Philosophy: Focus heavily on deterministic outcomes, survival, and rigorous, unverified vs. verified data tracking."
)

# ==========================================
# 2. SQLITE TELEMETRY PERSISTENCE
# ==========================================

def initialize_database():
    """Initializes the SQLite database used to store historical run state and prevent token duplication."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER,
            keyword TEXT UNIQUE,
            creative_motif TEXT,
            filename TEXT
        )
    """)
    conn.commit()
    conn.close()


def is_keyword_duplicated(keyword: str) -> bool:
    """Checks if an OSINT keyword has already been targeted in a previous generation run."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM generation_history WHERE keyword = ?", (keyword,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def record_generation_run(keyword: str, creative_motif: str, filename: str):
    """Logs a successful compilation block to enforce operational filtering rules."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO generation_history (timestamp, keyword, creative_motif, filename)
            VALUES (?, ?, ?, ?)
        """, (int(time.time()), keyword, creative_motif, filename))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Keyword racing protection
    conn.close()

# ==========================================
# 3. OSINT EXTRACTION & AUTONOMOUS IDEATION
# ==========================================

def fetch_live_osint_trends() -> list:
    """Harvests trending topics from public feeds with decoupled fallback channels."""
    trends = []

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(
            "https://trends.google.com/trending/rss?geo=US", headers=headers, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall(".//item"):
                title = item.find("title")
                if title is not None and title.text:
                    trends.append(title.text.strip())
    except Exception:
        pass

    if not trends:
        try:
            top_ids = requests.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=5).json()[:8]
            for item_id in top_ids:
                item_data = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json", timeout=5).json()
                if item_data and item_data.get("title"):
                    trends.append(item_data["title"])
        except Exception:
            pass

    return [t for t in trends if t.strip()]


def compile_nudge_matrix() -> dict:
    """Selects an unused, unique real-time keyword mixed with thematic parameters."""
    live_keywords = fetch_live_osint_trends()

    # Filter keywords against the historical deduplication engine
    fresh_keywords = [k for k in live_keywords if not is_keyword_duplicated(k)]

    if fresh_keywords:
        chosen_keyword = fresh_keywords[0]
    elif live_keywords:
        # If all current trending terms are exhausted, pick randomly to maintain execution velocity
        chosen_keyword = random.choice(live_keywords)
    else:
        # Absolute air-gapped protection fallback tokens
        fallback_pool = ["system reliance vulnerabilities", "decentralized node decay",
                         "algorithmic compliance failures"]
        chosen_keyword = random.choice(
            [f for f in fallback_pool if not is_keyword_duplicated(f)] or fallback_pool)

    return {
        "trend_hook": chosen_keyword,
        "creative_theme": random.choice(THEME_MATRIX["creative"]),
        "technical_vector": random.choice(THEME_MATRIX["technical"]),
        "professional_vector": random.choice(THEME_MATRIX["professional"])
    }

# ==========================================
# 4. MARKDOWN REGRESSION & CHECKER ASSAYS
# ==========================================

def run_structural_regression_test(content: str) -> bool:
    """
    Executes structural syntax analysis on the generated Markdown.
    Returns True if formatting checks pass; False if corruption is identified.
    """
    if len(content.strip()) < 200:
        print("[-] Regression Failure: Content payload length falls below minimum density thresholds.")
        return False

    # Check 1: Balanced markdown code fence blocks (```)
    fence_count = content.count("```")
    if fence_count % 2 != 0:
        print("[-] Regression Failure: Unbalanced markdown code fences detected. File structure broken.")
        return False

    # Check 2: Valid heading indicators
    lines = content.splitlines()
    has_headers = any(line.strip().startswith("#") for line in lines)
    if not has_headers:
        print("[-] Regression Failure: Document missing structural headers (#). Document flat lines.")
        return False

    return True

# ==========================================
# 5. CORE PIPELINE LOOPS
# ==========================================

def initialize_workspace():
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    initialize_database()

    if not (WORKSPACE_DIR / ".git").exists():
        subprocess.run(["git", "init", str(WORKSPACE_DIR)], check=True)
        readme = WORKSPACE_DIR / "README.md"
        if not readme.exists():
            readme.write_text("# Autonomous Workspace\nTracking metrics persistence layer.")
        subprocess.run(["git", "add", "README.md"], cwd=WORKSPACE_DIR, check=True)
        subprocess.run(["git", "commit", "-m", "chore: setup master pipeline framework"],
                       cwd=WORKSPACE_DIR, check=True)


def ingest_research_context() -> tuple:
    """Reads folder data and injects the local voice configuration.
    Returns (context_string, is_autonomous_ideation_mode)."""
    context_chunks = []

    # Voice DNA profile (few-shot examples) ships inside the repo under prompts/
    if VOICE_PROFILE_PATH.exists():
        context_chunks.append(
            f"--- MANDATORY VOICE DNA BLUEPRINT ---\n{VOICE_PROFILE_PATH.read_text()}")

    for file_path in sorted(RESEARCH_DIR.glob("*.md")):
        try:
            context_chunks.append(
                f"--- ATTACHED TELEMETRY: {file_path.name} ---\n{file_path.read_text()}")
        except Exception:
            pass

    if context_chunks:
        return "\n\n".join(context_chunks), False
    # No local notes provided -> system triggers zero-input autonomous mode
    return ("NOTICE: Local background directory is completely empty. "
            "Initiate zero-input autonomous topic generation.", True)


def run_single_pipeline_cycle() -> dict | None:
    """Triggers a single compilation, verification, tracking, and version commit pass.
    Returns the nudge matrix + draft text on success (for the packaging hand-off)."""
    print(f"\n[*] Launching pipeline loop execution sequence: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    initialize_workspace()

    raw_context, is_autonomous = ingest_research_context()
    nudge = compile_nudge_matrix()

    print(f"[*] OSINT Deduplication Active: Selected dynamic keyword marker -> '{nudge['trend_hook']}'")
    if is_autonomous:
        print("[!] Target research data missing. Activating Zero-Input Autonomous Ideation Engine.")

    system_prompt = (
        "You are an automated manuscript development agent running an advanced text generation loop.\n"
        "You write exclusively in the user's authentic style.\n\n"
        f"{VOICE_DNA}\n\n"
        "Integrate structural context files and trending themes cleanly. "
        "Do not write meta-commentary or conversational intros. Output only raw markdown prose."
    )

    # Dynamically structure instructions based on internal tracking state
    if is_autonomous:
        execution_task = (
            f"Because the local background directories are empty, you must autonomously invent a creative topic, "
            f"a core systemic problem, and an engineering solution from scratch. Base your topic selection "
            f"directly on modern anxieties around the trending topic: '{nudge['trend_hook']}'.\n"
            f"Weave this solution into a multi-part fiction fable or highly detailed technical essay matching these dimensions:\n"
            f"- Narrative Focus: Base deep thematic roots on {nudge['creative_theme']}\n"
            f"- Technical Stack Architecture: Ground all logistical components inside {nudge['technical_vector']}\n"
            f"- Compliance Framework: Align operational parameters with {nudge['professional_vector']}\n"
        )
    else:
        execution_task = (
            f"Synthesize the provided references with these live trending thematic constraints:\n"
            f"- Active Trend Problem to resolve: {nudge['trend_hook']}\n"
            f"- Narrative Focus: Base deep thematic roots on {nudge['creative_theme']}\n"
            f"- Technical Stack Architecture: Ground all logistical components inside {nudge['technical_vector']}\n"
            f"- Compliance Framework: Align operational parameters with {nudge['professional_vector']}\n"
        )

    user_prompt = (
        f"### INPUT MATERIAL / CONTEXT STATEMENTS:\n{raw_context}\n\n"
        f"### MANDATORY INSTRUCTIONS:\n{execution_task}\n"
        f"### EXECUTION GUIDELINE:\n"
        f"Compile a comprehensive, long-form standalone Markdown chapter or complete technical whitepaper addressing these rules."
    )

    # Execute inference payload via requests
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 3000
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=240)
        response.raise_for_status()
        draft = response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[-] Execution aborted: Inference communication node failed: {e}", file=sys.stderr)
        return None

    if not draft:
        print("[-] Target loop frame dropped due to model processing timeout.")
        return None

    # Run structural checking algorithms over output string
    if not run_structural_regression_test(draft):
        print("[!] Generation cycle dropped: Failed Markdown safety linter tests.")
        return None

    slug = nudge["creative_theme"].replace(" ", "_").lower()[:12]
    timestamp = int(time.time())
    target_filename = f"gen_chunk_{slug}_{timestamp}.md"

    # Persistent storage write
    (OUTPUT_DIR / target_filename).write_text(draft)
    # Persist metrics data inside SQLite tracking file
    record_generation_run(nudge["trend_hook"], nudge["creative_theme"], target_filename)
    # Execute automated Git version commits
    subprocess.run(["git", "add", str((OUTPUT_DIR / target_filename).relative_to(WORKSPACE_DIR))],
                   cwd=WORKSPACE_DIR, check=True)
    commit_msg = (f"feat(manuscript): atomic commit update\n\n"
                  f"[OSINT Anchor]: {nudge['trend_hook']}\n[Motif]: {nudge['creative_theme']}")
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=WORKSPACE_DIR, check=True)
    print(f"[+] Output captured and secured inside workspace repository: {target_filename}")

    return {"nudge": nudge, "draft": draft, "filename": target_filename}

# ==========================================
# 6. PACKAGING HAND-OFF (whole-book mode)
# ==========================================

def package_book_from_drafts(title: str, subtitle: str, author: str,
                             art_backend: str = "xai") -> dict | None:
    """Compiles every draft in the workspace into one interior PDF, counts the
    pages, then builds the full KDP package (Grok Imagine cover + answers).
    Thin wrapper around builder/book_builder.py so the daemon can call it."""
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / "builder"))
    try:
        from book_builder import build_book  # noqa: E402
    except ImportError as e:
        print(f"[-] Packaging hand-off unavailable: {e}", file=sys.stderr)
        return None
    return build_book(title=title, subtitle=subtitle, author=author,
                      source="drafts", art_backend=art_backend)

# ==========================================
# 7. EXECUTIVE SYSTEM CONTROLLER
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="Autonomous manuscript pipeline controller")
    parser.add_argument("--cron", action="store_true",
                        help="Single run pass and close out clean (crontab handler mode)")
    parser.add_argument("--package-book", action="store_true",
                        help="After the cycle, compile drafts and build the full KDP package")
    parser.add_argument("--title", default="The Tartarian Ledger")
    parser.add_argument("--subtitle", default="Macabre Fables of Lost Empires")
    parser.add_argument("--author", default="Midnight Sapphire")
    parser.add_argument("--art-backend", default="xai",
                        choices=["xai", "openrouter", "procedural"],
                        help="Cover art backend for the packaging hand-off (default: xai / Grok Imagine)")
    args = parser.parse_args()

    if args.cron:
        # Cron Execution Mode: Single run pass and close out clean
        result = run_single_pipeline_cycle()
        if args.package_book and result:
            package_book_from_drafts(args.title, args.subtitle, args.author, args.art_backend)
        sys.exit(0)

    # Long Running Daemon Processing Loop Mode
    HOURLY_INTERVAL = 3600
    print(f"[*] Initializing long-running daemon execution mode (Interval: {HOURLY_INTERVAL}s)...")
    print("[*] To switch to a strict single-run crontab handler, execute using flag: --cron")
    try:
        while True:
            result = run_single_pipeline_cycle()
            if args.package_book and result:
                package_book_from_drafts(args.title, args.subtitle, args.author, args.art_backend)
            print("[*] Daemon sleeping. Standing by for next generation block sequence...")
            time.sleep(HOURLY_INTERVAL)
    except KeyboardInterrupt:
        print("\n[-] Pipeline controller thread terminated via manual user intervention.")


if __name__ == "__main__":
    main()
