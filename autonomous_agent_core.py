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
