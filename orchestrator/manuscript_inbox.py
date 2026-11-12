"""Finish Markdown manuscripts locally, then invoke the existing KDP builder."""

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

from orchestrator.autonomous_agent_core import call_llm


BUILDER = Path(__file__).resolve().parents[1] / "builder" / "book_builder.py"
TITLE = re.compile(r"^# (.+)$", re.MULTILINE)
TARGET = re.compile(r"^<!-- target-chapters: ([1-9][0-9]*) -->[ \t]*$", re.MULTILINE)
CHAPTER = re.compile(r"^## Chapter ([1-9][0-9]*)\b.*$", re.MULTILINE)


def write_atomic(path, text):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def complete_book(source, text, output, author):
    title = TITLE.search(text)
    target = TARGET.search(text)
    chapters = [int(number) for number in CHAPTER.findall(text)]
    if not title or not target or not chapters:
        raise ValueError("Include a # Title, a target-chapters comment, and at least ## Chapter 1.")
    title = title[1].strip()
    count = int(target[1])
    if chapters != list(range(1, len(chapters) + 1)) or len(chapters) > count:
        raise ValueError("Chapter headings must be consecutive from 1 through the requested target.")

    digest = hashlib.sha256(f"{author}\0{text}".encode("utf-8")).hexdigest()
    job = output / f"{source.stem[:50]}-{digest[:16]}"
    job.mkdir(parents=True, exist_ok=True)
    completed = job / "complete.json"
    if completed.is_file():
        return

    draft = job / "finished.md"
    if draft.exists():
        manuscript = draft.read_text(encoding="utf-8")
    else:
        manuscript = text
        write_atomic(draft, manuscript)
    next_number = len(CHAPTER.findall(manuscript)) + 1

    for number in range(next_number, count + 1):
        payload = {
            "messages": [
                {"role": "system", "content": (
                    "Continue the provided manuscript in its established voice. "
                    "Return one substantial Markdown chapter of roughly 800 to 1200 words, with a single numbered "
                    "'## Chapter N: Title' heading and blank lines between paragraphs. "
                    "Preserve names, facts, and continuity. Do not rewrite earlier chapters."
                )},
                {"role": "user", "content": (
                    f"Write Chapter {number} of {count} for {title}. "
                    + ("Resolve the main arc in this chapter.\n\n" if number == count else "Advance the existing arc.\n\n")
                    + "Opening and latest manuscript context:\n"
                    + (manuscript if len(manuscript) <= 16000 else manuscript[:4000] + "\n\n[... ]\n\n" + manuscript[-12000:])
                )},
            ],
            "max_tokens": 4096,
        }
        result = (call_llm(payload, provider="local") or "").strip()
        heading = CHAPTER.match(result)
        if (not heading or int(heading[1]) != number or len(CHAPTER.findall(result)) != 1
                or not result[heading.end():].strip()):
            raise RuntimeError(f"Local model did not return a complete Chapter {number}.")
        manuscript += "\n\n" + result + "\n"
        write_atomic(draft, manuscript)

    subprocess.run(
        [sys.executable, str(BUILDER), "--manuscript", str(draft),
         "--title", title, "--author", author, "--art-backend", "procedural"],
        cwd=job, check=True,
    )
    write_atomic(completed, json.dumps({"chapters": count, "manuscript": draft.name}, indent=2) + "\n")
    print(f"[+] Finished {source.name}: {job}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("local-books"))
    parser.add_argument("--author", default="Midnight Sapphire")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()
    if args.interval < 1:
        parser.error("--interval must be at least one second")
    root = args.root.resolve()
    inbox = root / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    failures = {}
    with closing(sqlite3.connect(root / "worker.lock.sqlite")) as lock:
        lock.execute("BEGIN IMMEDIATE")
        print(f"[*] Manuscript inbox: {inbox}", flush=True)
        while True:
            for source in sorted(inbox.glob("*.md")):
                if source.is_symlink() or not source.is_file():
                    continue
                text = None
                try:
                    text = source.read_text(encoding="utf-8-sig")
                    fingerprint = hashlib.sha256(text.encode("utf-8")).digest()
                    if failures.get(source) != fingerprint:
                        failures.pop(source, None)
                        complete_book(source, text, root / "output", args.author)
                except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
                    fingerprint = fingerprint if text is not None else None
                    if source not in failures or failures[source] != fingerprint:
                        failures[source] = fingerprint
                        print(f"[!] {source.name}: {error}", file=sys.stderr, flush=True)
            if not args.watch:
                return int(bool(failures))
            time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
