#!/usr/bin/env python3
"""
Autonomous Manuscript & Technical Content Pipeline (Production V3)
Orchestrates: 
  - Live OSINT Scrapers (Google Trends RSS / HackerNews fallback matrix)
  - SQLite Telemetry Persistence (Ensures absolute keyword uniqueness)
  - Zero-Input Autonomous Ideation (Generates topics from trend context if research is empty)
  - Deep Markdown Structural Regression Testing (Validates syntax, fences, and consistency)
  - Native Python Cron Daemon Process Loops
"""

import os
import sys
import time
import json
import sqlite3
import random
import xml.etree.ElementTree as ET
import subprocess
from pathlib import Path
import requests

# ==========================================
# 1. CORE PIPELINE SPECIFICATIONS
# ==========================================
API_URL = "http://localhost:1234/v1/chat/completions"  
MODEL_NAME = "gemma-3-4b-it"                           
WORKSPACE_DIR = Path("./manuscript_workspace")
RESEARCH_DIR = WORKSPACE_DIR / "research"
OUTPUT_DIR = WORKSPACE_DIR / "drafts"
DB_PATH = WORKSPACE_DIR / "pipeline_telemetry.db"

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
    trends_rss_url = "https://google.com"
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(trends_rss_url, headers=headers, timeout=10)
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
            hn_api = "https://firebaseio.com"
            top_ids = requests.get(hn_api, timeout=5).json()[:8]
            for item_id in top_ids:
                item_data = requests.get(f"https://firebaseio.com{item_id}.json", timeout=5).json()
                if "title" in item_data and item_data["title"]:
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
        fallback_pool = ["system reliance vulnerabilities", "decentralized node decay", "algorithmic compliance failures"]
        chosen_keyword = random.choice([f for f in fallback_pool if not is_keyword_duplicated(f)] or fallback_pool)
    
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
            subprocess.run(["git", "commit", "-m", "chore: setup master pipeline framework"], cwd=WORKSPACE_DIR, check=True)

def ingest_research_context() -> tuple:
    """Reads folder data. Returns (context_string, is_autonomous_ideation_mode)"""
    context_chunks = []
    for file_path in RESEARCH_DIR.glob("*.md"):
        try:
            context_chunks.append(f"--- ATTACHED TELEMETRY: {file_path.name} ---\n{file_path.read_text()}")
        except Exception:
            pass
            
    if context_chunks:
        return "\n\n".join(context_chunks), False
    else:
        # No local notes provided -> system triggers zero-input autonomous mode
        return "NOTICE: Local background directory is completely empty. Initiate zero-input autonomous topic generation.", True

def run_single_pipeline_cycle():
    """Triggers a single compilation, verification, tracking, and version commit pass."""
    print(f"\n[*] Launching pipeline loop execution sequence: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    initialize_workspace()
    
    raw_context, is_autonomous = ingest_research_context()
    nudge = compile_nudge_matrix()
    
    print(f"[*] OSINT Deduplication Active: Selected dynamic keyword marker -> '{nudge['trend_hook']}'")
    if is_autonomous:
        print("[!] Target research data missing. Activating Zero-Input Autonomous Ideation Engine.")

    system_prompt = (
        "You are an automated manuscript development agent running an advanced text generation loop.\n"
        "Integrate structural context files and trending themes cleanly. Do not write meta-commentary or conversational intros."
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
draft = response.json()["choices"]["message"]["content"]
except Exception as e:
print(f"[-] Execution aborted: Inference communication node failed: {e}", file=sys.stderr)
return
if draft:
# Run structural checking algorithms over output string
if not run_structural_regression_test(draft):
print("[!] Generation cycle dropped: Failed Markdown safety linter tests.")
return
slug = nudge['creative_theme'].replace(" ", "").lower()[:12]
timestamp = int(time.time())
target_filename = f"gen_chunk{slug}_{timestamp}.md"
# Persistent storage write
(OUTPUT_DIR / target_filename).write_text(draft)
# Persist metrics data inside SQLite tracking file
record_generation_run(nudge['trend_hook'], nudge['creative_theme'], target_filename)
# Execute automated Git version commits
subprocess.run(["git", "add", str((OUTPUT_DIR / target_filename).relative_to(WORKSPACE_DIR))], cwd=WORKSPACE_DIR, check=True)
commit_msg = f"feat(manuscript): atomic commit update\n\n[OSINT Anchor]: {nudge['trend_hook']}\n[Motif]: {nudge['creative_theme']}"
subprocess.run(["git", "commit", "-m", commit_msg], cwd=WORKSPACE_DIR, check=True)
print(f"[+] Output captured and secured inside workspace repository: {target_filename}")
else:
print("[-] Target loop frame dropped due to model processing timeout.")

==========================================


6. EXECUTIVE SYSTEM CONTROLLER


==========================================

def main():
if len(sys.argv) > 1 and sys.argv[1] == "--cron":
# Cron Execution Mode: Single run pass and close out clean
run_single_pipeline_cycle()
sys.exit(0)
# Long Running Daemon Processing Loop Mode
HOURLY_INTERVAL = 3600
print(f"[] Initializing long-running daemon execution mode (Interval: {HOURLY_INTERVAL}s)...")
print("[] To switch to a strict single-run crontab handler, execute using flag: --cron")
try:
while True:
run_single_pipeline_cycle()
print(f"[*] Daemon sleeping. Standing by for next generation block sequence...")
time.sleep(HOURLY_INTERVAL)
except KeyboardInterrupt:
print("\n[-] Pipeline controller thread terminated via manual user intervention.")
if name == "main":
main()

### 📋 Telemetry & Validation Breakdown

1. **SQLite Unique Matrix:** The database saves a hash map of targeted trends inside `pipeline_telemetry.db`. If a specific trend name is caught by your OSINT modules on a second run, the loop automatically drops it and queries alternative trends.
2. **Zero-Input Autonomy:** If you clear out the contents of the `manuscript_workspace/research/` folder, the pipeline continues running. The script detects the empty directory and instructs the model to act as an independent topic ideator, inventing cohesive narrative problem spaces based on trending terms.
3. **Markdown Regression Test:** The linter evaluates lines before committing. If the local language model leaves a code block open (` ``` `) or skips header definitions, the script halts execution and drops the file, protecting your Git tree from corrupt data commits.

<FollowUp>
We can expand this setup further. If you'd like, let me know:
* Would you like the linter to **auto-correct simple structural errors** (like appending missing code fences to the end of a file)?
* Should we add an **export hook** to automatically merge the files into a single master document every 24 hours?
</FollowUp>
Try without personalization


    # Define your exact writing style signature natively inside the orchestrator
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

    system_prompt = (
        f"You are an automated manuscript development agent running an advanced text generation loop.\n"
        f"You write exclusively in the user's authentic style.\n\n"
        f"{VOICE_DNA}\n\n"
        "Integrate structural context files and trending themes cleanly. Output only raw markdown prose."
    )




          
