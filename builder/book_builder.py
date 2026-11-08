#!/usr/bin/env python3
"""
Book Builder — middle stage of the pipeline, between the orchestrator and
the KDP packager.

  manuscript_workspace/drafts/*.md  (written by orchestrator/autonomous_agent_core.py)
          |
          v
  compile_manuscript()   -> one ordered Markdown master document
          |
          v
  render_interior_pdf()  -> 8.5" x 11" print interior PDF (real text, fpdf2)
          |
          v
  page count derived from the PDF itself -> spine width is always correct
          |
          v
  kdp_packager.package_book(..., art_backend="xai")  -> Grok Imagine cover,
  wraparound print PDF, ebook front, pre-answered kdp_answers.json

Two entry modes:
  --from-drafts              compile everything in manuscript_workspace/drafts/
  --manuscript my_book.md    you already wrote/assembled the book; we typeset
                             and package it. (Whole-book mode without the
                             orchestrator. For cover-only, use kdp_packager
                             directly with --cover-only.)

Usage:
  python book_builder.py --from-drafts --title "The Tartarian Ledger" \
      --subtitle "Macabre Fables of Lost Empires" --author "Midnight Sapphire"

Dependencies: pip install fpdf2 pillow requests
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

from fpdf import FPDF

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "packaging"))
from kdp_packager import package_book, MIN_PAGES  # noqa: E402

WORKSPACE_DIR = Path("./manuscript_workspace")
DRAFTS_DIR = WORKSPACE_DIR / "drafts"
BUILD_DIR = WORKSPACE_DIR / "build"

# Interior typesetting spec (8.5 x 11 trim, KDP-safe margins)
PAGE_W_MM = 215.9
PAGE_H_MM = 279.4
MARGIN_MM = 19.05          # 0.75 in outer/top/bottom
GUTTER_MM = 25.4           # 1.0 in binding side
BODY_SIZE = 11
LINE_H_MM = 6.2


def compile_manuscript(source: str, manuscript_path: str = "") -> str:
    """Returns the master Markdown text, either from the drafts folder or a
    user-supplied manuscript file. Drafts are ordered by filename timestamp."""
    if source == "manuscript":
        p = Path(manuscript_path)
        if not p.exists():
            raise FileNotFoundError(f"Manuscript not found: {p}")
        return p.read_text()

    drafts = sorted(DRAFTS_DIR.glob("*.md"))
    if not drafts:
        raise RuntimeError(
            f"No drafts found in {DRAFTS_DIR}. Run the orchestrator first, "
            "or use --manuscript your_book.md.")
    parts = []
    for d in drafts:
        text = d.read_text().strip()
        if text:
            parts.append(text)
    return "\n\n---\n\n".join(parts)


def _md_to_blocks(md: str) -> list:
    """Minimal Markdown block splitter: headings, paragraphs, rules.
    Inline code fences are passed through as preformatted blocks."""
    blocks = []
    for chunk in re.split(r"\n\s*\n", md):
        chunk = chunk.strip("\n")
        if not chunk.strip():
            continue
        stripped = chunk.strip()
        if stripped.startswith("```"):
            blocks.append(("code", stripped.strip("`").strip()))
        elif stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            blocks.append((f"h{min(level, 3)}", stripped.lstrip("#").strip()))
        elif stripped in ("---", "***", "___"):
            blocks.append(("rule", ""))
        else:
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
            clean = re.sub(r"\*(.+?)\*", r"\1", clean)
            clean = re.sub(r"`(.+?)`", r"\1", clean)
            blocks.append(("p", " ".join(clean.split())))
    return blocks


def render_interior_pdf(md_text: str, title: str, author: str,
                        out_pdf: Path) -> int:
    """Typesets the master document as a print interior PDF.
    Returns the final page count (the value that drives spine width)."""
    pdf = FPDF(unit="mm", format=(PAGE_W_MM, PAGE_H_MM))
    pdf.set_auto_page_break(auto=True, margin=MARGIN_MM)
    pdf.set_margins(GUTTER_MM, MARGIN_MM, MARGIN_MM)
    usable_w = PAGE_W_MM - GUTTER_MM - MARGIN_MM

    # Title page
    pdf.add_page()
    pdf.set_y(PAGE_H_MM * 0.35)
    pdf.set_font("times", "B", 28)
    pdf.multi_cell(usable_w, 12, title, align="C")
    pdf.ln(6)
    pdf.set_font("times", "I", 14)
    pdf.multi_cell(usable_w, 8, author, align="C")

    for kind, text in _md_to_blocks(md_text):
        if kind == "rule":
            pdf.add_page()
            continue
        if pdf.page_no() == 1 and pdf.get_y() < MARGIN_MM + 5:
            pass  # still on title page; first body block forces a new page below
        if kind == "code":
            pdf.set_font("courier", "", 9)
            pdf.multi_cell(usable_w, 5, text)
            pdf.ln(2)
            continue
        if kind.startswith("h"):
            size = {"h1": 20, "h2": 16, "h3": 13}[kind]
            pdf.add_page()
            pdf.set_font("times", "B", size)
            pdf.multi_cell(usable_w, 9, text)
            pdf.ln(3)
            continue
        if pdf.get_y() <= MARGIN_MM + 1:
            pdf.add_page()
        pdf.set_font("times", "", BODY_SIZE)
        pdf.multi_cell(usable_w, LINE_H_MM, text)
        pdf.ln(2)

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_pdf))
    return pdf.page_no()


def build_book(title: str, subtitle: str, author: str,
               source: str = "drafts", manuscript_path: str = "",
               theme: str = "macabre fables, ancient scripts",
               blurb: str = "", art_backend: str = "xai") -> dict:
    """Whole-book mode: manuscript -> interior PDF -> page count -> full
    KDP package with Grok Imagine cover art."""
    print(f"[*] Compiling manuscript from: {source}")
    md = compile_manuscript(source, manuscript_path)

    slug = "".join(c if c.isalnum() else "_" for c in title.lower())[:40]
    master_md = BUILD_DIR / f"{slug}_manuscript.md"
    interior_pdf = BUILD_DIR / f"{slug}_interior.pdf"
    master_md.parent.mkdir(parents=True, exist_ok=True)
    master_md.write_text(md)

    page_count = render_interior_pdf(md, title, author, interior_pdf)
    print(f"[+] Interior typeset: {interior_pdf} ({page_count} pages)")
    if page_count < MIN_PAGES:
        raise RuntimeError(
            f"Interior is {page_count} pages; KDP paperbacks need >= {MIN_PAGES}. "
            "Run more pipeline cycles first.")

    blurb = blurb or (
        f"{title}: a {theme} collection forged by an autonomous manuscript pipeline."
    )
    result = package_book(
        title=title, subtitle=subtitle, author=author, page_count=page_count,
        theme=theme, blurb=blurb, manuscript_pdf=str(interior_pdf),
        art_backend=art_backend, cover_only=False,
    )
    result["interior_pdf"] = str(interior_pdf)
    result["manuscript_md"] = str(master_md)
    print("\n[+] WHOLE-BOOK BUILD COMPLETE")
    print(json.dumps(result, indent=2))
    return result


def main():
    p = argparse.ArgumentParser(description="Compile drafts -> interior PDF -> KDP package")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-drafts", action="store_true",
                     help="Compile manuscript_workspace/drafts/*.md")
    src.add_argument("--manuscript", default="",
                     help="Path to an existing Markdown/Text manuscript")
    p.add_argument("--title", required=True)
    p.add_argument("--subtitle", default="")
    p.add_argument("--author", default="Midnight Sapphire")
    p.add_argument("--theme", default="macabre fables, ancient scripts")
    p.add_argument("--blurb", default="")
    p.add_argument("--art-backend", default="xai",
                   choices=["xai", "openrouter", "procedural"])
    args = p.parse_args()

    build_book(
        title=args.title, subtitle=args.subtitle, author=args.author,
        source="drafts" if args.from_drafts else "manuscript",
        manuscript_path=args.manuscript, theme=args.theme, blurb=args.blurb,
        art_backend=args.art_backend,
    )


if __name__ == "__main__":
    main()
