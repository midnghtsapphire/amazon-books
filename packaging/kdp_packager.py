#!/usr/bin/env python3
"""
KDP Packager — final stage for the autonomous manuscript pipeline.

Turns a finished manuscript into a complete Amazon KDP upload package:

  1. Full wraparound PRINT COVER (back + spine + front) at exact KDP
     dimensions, 300 DPI, with bleed, safe zones and the barcode zone
     reserved. Exported as print-ready PDF + PNG preview.
  2. Front-cover-only EBOOK image (JPG, 300 DPI).
  3. kdp_answers.json — every question in the KDP upload wizard,
     pre-answered with your standing preferences, so upload day is a
     copy/paste exercise instead of a form-filling session.

Two operating modes:
  - FULL BOOK:   called by builder/book_builder.py after the orchestrator
                 compiles drafts into an interior PDF (page count is derived
                 automatically, so the spine is always right).
  - COVER-ONLY:  you already have a finished book and only need a new
                 cover. Pass --cover-only with your final interior page
                 count; the manifest marks the manuscript as user-supplied.

Cover art backends (first configured wins, procedural is the always-on floor):
  - xai (DEFAULT): Grok Imagine via the xAI API. Set XAI_API_KEY.
                   Model: grok-imagine-image-2.0, portrait 3:4, 2K.
  - openrouter:    legacy path. Set OPENROUTER_API_KEY.
  - procedural:    deterministic midnight-sapphire gradient, zero network.

Standing preferences baked in (your defaults):
  - Trim size:   8.5" x 11"  (largest paperback trim KDP offers)
  - Ink & paper: Premium Color ink, white paper
  - Cover finish: GLOSSY
  - Bleed (interior): No bleed (text manuscripts)
  - Rights: you own the copyright
  - AI disclosure: YES (text + cover art are AI-generated)

Usage (cover-only):
  python kdp_packager.py --cover-only --title "The Tartarian Ledger" \
      --subtitle "Macabre Fables of Lost Empires" \
      --author "Midnight Sapphire" --pages 200 \
      --theme "ancient clay tablets, Linear B script, gold inscriptions, midnight blue"

Usage (from autonomous_agent_core.py / book_builder.py):
  from kdp_packager import package_book
  package_book(title="...", subtitle="...", author="Midnight Sapphire",
               page_count=200, theme=nudge["creative_theme"],
               blurb=draft[:600], art_backend="xai")

Dependencies: pip install pillow requests
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ======================================================================
# 1. KDP PRINT SPECIFICATIONS (verified against KDP guidelines)
# ======================================================================

DPI = 300                       # KDP print minimum/effective resolution
TRIM_W_IN = 8.5                 # Largest KDP paperback trim
TRIM_H_IN = 11.0
BLEED_IN = 0.125                # KDP cover bleed on every outer edge
SAFE_IN = 0.25                  # Keep text/logos this far inside trim
BARCODE_W_IN = 2.0              # Reserved barcode zone, back cover
BARCODE_H_IN = 1.2

# KDP spine = page_count x paper thickness (inches per page)
PAPER_THICKNESS_IN = {
    "white": 0.002252,
    "cream": 0.0025,
    "premium_color_white": 0.002252,   # premium color prints on white stock
}

# KDP printing cost model (Amazon.com, USD) — verify current rates in the
# KDP Royalty Calculator before publish day; Amazon revises periodically.
PRINT_COST_MODEL = {
    "black_white":       {"fixed": 1.00, "per_page": 0.012},
    "standard_color":    {"fixed": 1.00, "per_page": 0.027},
    "premium_color":     {"fixed": 1.00, "per_page": 0.065},
}

MIN_PAGES = 24                  # KDP paperback minimum page count
SPINE_TEXT_MIN_PAGES = 79       # KDP only prints spine text at 80+ pages

XAI_IMAGES_URL = "https://api.x.ai/v1/images/generations"
XAI_IMAGE_MODEL = "grok-imagine-image-2.0"

WORKSPACE_DIR = Path("./manuscript_workspace")
PACKAGE_DIR = WORKSPACE_DIR / "kdp_packages"

# ======================================================================
# 2. DIMENSION MATH
# ======================================================================

def spine_width_in(page_count: int, paper: str = "premium_color_white") -> float:
    """KDP spine width formula: pages x paper thickness."""
    return round(page_count * PAPER_THICKNESS_IN[paper], 4)


def wrap_dimensions(page_count: int, paper: str = "premium_color_white") -> dict:
    """
    Full paperback wraparound cover geometry.
    Width  = bleed + back cover + spine + front cover + bleed
    Height = bleed + trim height + bleed
    """
    spine = spine_width_in(page_count, paper)
    w_in = round(BLEED_IN + TRIM_W_IN + spine + TRIM_W_IN + BLEED_IN, 4)
    h_in = round(TRIM_H_IN + 2 * BLEED_IN, 4)
    return {
        "width_in": w_in,
        "height_in": h_in,
        "spine_in": spine,
        "width_px": round(w_in * DPI),
        "height_px": round(h_in * DPI),
        # x-offsets (pixels) for layout math
        "back_x0": round(BLEED_IN * DPI),
        "spine_x0": round((BLEED_IN + TRIM_W_IN) * DPI),
        "front_x0": round((BLEED_IN + TRIM_W_IN + spine) * DPI),
        "trim_x1": round((BLEED_IN + TRIM_W_IN + spine + TRIM_W_IN) * DPI),
    }


def estimate_printing_cost(page_count: int, ink: str = "premium_color") -> float:
    model = PRINT_COST_MODEL[ink]
    return round(model["fixed"] + model["per_page"] * page_count, 2)


def minimum_list_price(page_count: int, ink: str = "premium_color") -> float:
    """KDP paperback royalty is 60% of list minus printing cost."""
    return round(estimate_printing_cost(page_count, ink) / 0.60 + 0.01, 2)


# ======================================================================
# 3. COVER ART GENERATION
# ======================================================================

def build_art_prompt(theme: str, title: str) -> str:
    """Builds a deterministic cover-art prompt from the pipeline's theme."""
    return (
        f"Professional book cover artwork, no text, no lettering, no words. "
        f"Theme: {theme}. For a book titled '{title}'. "
        f"Macabre, elegant, atmospheric dark-fantasy illustration. "
        f"Deep midnight-sapphire blue palette with antique gold accents, "
        f"dramatic chiaroscuro lighting, mist, cinematic composition, "
        f"painterly detail, portrait orientation."
    )


def generate_cover_art_xai(prompt: str, out_path: Path) -> bool:
    """
    Grok Imagine backend (default). Calls the xAI image API with
    grok-imagine-image-2.0 at portrait 3:4 / 2K. Set XAI_API_KEY in your
    environment. Returns False on any failure so the composer can fall back.
    """
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        print("[!] XAI_API_KEY not set — Grok Imagine backend unavailable.")
        return False
    try:
        resp = requests.post(
            XAI_IMAGES_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": XAI_IMAGE_MODEL, "prompt": prompt, "n": 1,
                  "aspect_ratio": "3:4", "resolution": "2k"},
            timeout=300,
        )
        resp.raise_for_status()
        url = resp.json()["data"][0]["url"]
        out_path.write_bytes(requests.get(url, timeout=120).content)
        print(f"[+] Grok Imagine cover art generated: {out_path}")
        return True
    except Exception as e:
        print(f"[!] Grok Imagine generation failed ({e}).")
        return False


def generate_cover_art_openrouter(prompt: str, out_path: Path) -> bool:
    """Legacy OpenRouter backend. Set OPENROUTER_API_KEY in your environment."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("[!] OPENROUTER_API_KEY not set.")
        return False
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "openai/dall-e-3", "prompt": prompt,
                  "n": 1, "size": "1024x1792"},
            timeout=300,
        )
        resp.raise_for_status()
        url = resp.json()["data"][0]["url"]
        out_path.write_bytes(requests.get(url, timeout=120).content)
        print(f"[+] Cover art generated via OpenRouter: {out_path}")
        return True
    except Exception as e:
        print(f"[!] OpenRouter art generation failed ({e}).")
        return False


def generate_cover_art(prompt: str, out_path: Path, backend: str = "xai") -> bool:
    """Dispatch to the configured art backend. Caller handles fallback."""
    if backend == "xai":
        return generate_cover_art_xai(prompt, out_path)
    if backend == "openrouter":
        return generate_cover_art_openrouter(prompt, out_path)
    return False  # "procedural" is handled by the fallback path


def procedural_fallback_art(out_path: Path, width: int, height: int,
                            seed_theme: str = "midnight"):
    """Deterministic offline cover background: midnight-sapphire gradient
    with gold grain — always available, zero network dependency."""
    import hashlib
    import random as _r
    seed = int(hashlib.sha256(seed_theme.encode()).hexdigest()[:8], 16)
    rng = _r.Random(seed)

    img = Image.new("RGB", (width, height))
    px = img.load()
    top = (8, 10, 36)       # near-black sapphire
    bottom = (24, 32, 96)   # midnight blue
    for y in range(height):
        t = y / height
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(width):
            px[x, y] = (r, g, b)
    draw = ImageDraw.Draw(img)
    # gold fleck constellation
    for _ in range(220):
        x, y = rng.randint(0, width - 1), rng.randint(0, height - 1)
        rad = rng.randint(1, 3)
        gold = (200 + rng.randint(0, 55), 160 + rng.randint(0, 60), 60)
        draw.ellipse([x - rad, y - rad, x + rad, y + rad], fill=gold)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.save(out_path)
    print(f"[+] Procedural fallback art written: {out_path}")


# ======================================================================
# 4. WRAPAROUND COVER COMPOSER (Pillow)
# ======================================================================

def _load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Tries common fonts; falls back to PIL default. Point FONT_PATH env
    var at a .ttf you like (e.g. Cinzel, EB Garamond) for a custom look."""
    candidates = [
        os.environ.get("FONT_PATH", ""),
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "C:/Windows/Fonts/georgiab.ttf" if bold else "C:/Windows/Fonts/georgia.ttf",
        "/Library/Fonts/Georgia Bold.ttf" if bold else "/Library/Fonts/Georgia.ttf",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, cx: int, y: int,
                   font, fill, max_width: int) -> int:
    """Word-wraps and draws centered text; returns the new y cursor."""
    words, lines, line = text.split(), [], ""
    for w in words:
        test = (line + " " + w).strip()
        if draw.textlength(test, font=font) <= max_width:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    for ln in lines:
        tw = draw.textlength(ln, font=font)
        draw.text((cx - tw / 2, y), ln, font=font, fill=fill)
        y += int(font.size * 1.25)
    return y


def compose_print_cover(front_art: Path, title: str, subtitle: str,
                        author: str, blurb: str, page_count: int,
                        out_dir: Path) -> dict:
    """Builds the full KDP wraparound cover at exact print dimensions."""
    spec = wrap_dimensions(page_count)
    W, H = spec["width_px"], spec["height_px"]

    # --- base: front art stretched across the whole wrap ---------------
    art = Image.open(front_art).convert("RGB").resize((W, H), Image.LANCZOS)
    cover = art.copy()
    draw = ImageDraw.Draw(cover)

    # Darken the back + spine so blurb text stays readable
    back_region = Image.new("RGB", (spec["spine_x0"], H), (6, 8, 28))
    cover.paste(Image.blend(art.crop((0, 0, spec["spine_x0"], H)),
                            back_region, 0.72), (0, 0))
    draw = ImageDraw.Draw(cover)

    gold = (212, 175, 55)
    ivory = (240, 236, 224)
    safe_x = spec["front_x0"] + round(SAFE_IN * DPI)
    front_cx = spec["front_x0"] + round(TRIM_W_IN * DPI / 2)
    front_max_w = round((TRIM_W_IN - 2 * SAFE_IN) * DPI)

    # --- FRONT: title / subtitle / author -------------------------------
    y = round(1.1 * DPI)
    title_font = _load_font(round(0.62 * DPI), bold=True)
    sub_font = _load_font(round(0.30 * DPI), bold=False)
    author_font = _load_font(round(0.36 * DPI), bold=True)
    y = _draw_centered(draw, title.upper(), front_cx, y, title_font, ivory, front_max_w)
    y += round(0.15 * DPI)
    _draw_centered(draw, subtitle, front_cx, y, sub_font, gold, front_max_w)
    _draw_centered(draw, author.upper(), front_cx,
                   H - round(1.0 * DPI), author_font, ivory, front_max_w)

    # --- SPINE (only printed by KDP at 80+ pages) -----------------------
    if page_count >= 80:
        spine_cx = spec["spine_x0"] + round(spec["spine_in"] * DPI / 2)
        spine_font = _load_font(round(0.24 * DPI), bold=True)
        spine_img = Image.new("RGB", (H - round(1.0 * DPI), round(0.4 * DPI)), (0, 0, 0))
        sdraw = ImageDraw.Draw(spine_img)
        sdraw.text((round(0.2 * DPI), 0), f"{title}   —   {author}",
                   font=spine_font, fill=ivory)
        spine_img = spine_img.rotate(90, expand=True)
        cover.paste(spine_img, (spine_cx - spine_img.width // 2,
                                round(0.5 * DPI)))
        draw = ImageDraw.Draw(cover)

    # --- BACK: blurb + reserved barcode zone ----------------------------
    back_cx = spec["back_x0"] + round(TRIM_W_IN * DPI / 2)
    blurb_font = _load_font(round(0.26 * DPI), bold=False)
    _draw_centered(draw, blurb[:600], back_cx, round(1.0 * DPI),
                   blurb_font, ivory, front_max_w)
    bc_w, bc_h = round(BARCODE_W_IN * DPI), round(BARCODE_H_IN * DPI)
    bc_x = spec["spine_x0"] - round(SAFE_IN * DPI) - bc_w
    bc_y = H - round(SAFE_IN * DPI) - bc_h
    draw.rectangle([bc_x, bc_y, bc_x + bc_w, bc_y + bc_h],
                   outline=gold, width=3)
    bc_font = _load_font(round(0.14 * DPI), bold=False)
    draw.text((bc_x + 8, bc_y + 8), "BARCODE ZONE (KDP places ISBN here)",
              font=bc_font, fill=gold)

    # --- exports ---------------------------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / "cover_wrap_print.png"
    pdf_path = out_dir / "cover_wrap_print.pdf"
    cover.save(png_path, dpi=(DPI, DPI))
    cover.save(pdf_path, "PDF", resolution=DPI)   # print-ready upload file

    # ebook front cover (front panel only, JPG)
    front_panel = cover.crop((spec["front_x0"], round(BLEED_IN * DPI),
                              spec["trim_x1"], H - round(BLEED_IN * DPI)))
    ebook_path = out_dir / "cover_ebook_front.jpg"
    front_panel.save(ebook_path, quality=95, dpi=(DPI, DPI))

    print(f"[+] Print cover: {pdf_path} ({spec['width_in']}\" x {spec['height_in']}\", "
          f"spine {spec['spine_in']}\")")
    print(f"[+] Ebook cover: {ebook_path}")
    return {"pdf": str(pdf_path), "png": str(png_path),
            "ebook": str(ebook_path), "spec": spec}


# ======================================================================
# 5. KDP UPLOAD WIZARD — PRE-ANSWERED MANIFEST
# ======================================================================

def build_kdp_answers(title: str, subtitle: str, author: str,
                      description: str, keywords: list, page_count: int,
                      cover_files: dict, manuscript_pdf: str,
                      cover_only: bool = False) -> dict:
    """
    Every question in the KDP paperback wizard, pre-answered with your
    standing preferences. Upload day = open this file, copy, paste.
    """
    spec = cover_files["spec"]
    if cover_only and not manuscript_pdf:
        manuscript_pdf = "(existing interior — upload your own PDF)"
    return {
        "_meta": {
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "cover_only" if cover_only else "full_book",
            "note": "Walk the KDP wizard top to bottom; every answer is here.",
        },
        "1_details_page": {
            "language": "English",
            "book_title": title,
            "subtitle": subtitle,
            "series": "(leave blank — not part of a series)",
            "edition_number": "1",
            "author": author,
            "contributors": "(none)",
            "description": description[:4000],
            "publishing_rights":
                "I own the copyright and I hold necessary publishing rights",
            "primary_audience_adult_content": "No",
            "primary_audience_reading_age": "18+",
            "primary_marketplace": "Amazon.com",
            "categories": [
                "Fiction > Short Stories & Anthologies > Short Stories",
                "Fiction > Fairy Tales, Folk Tales, Legends & Mythology",
                "(pick a 3rd placement category after publish via KDP support)",
            ],
            "keywords_7_slots": (keywords + [""] * 7)[:7],
            "preorder": "I am ready to release my book now",
        },
        "2_content_page": {
            "isbn": "Assign me a free KDP ISBN",
            "imprint": "(leave blank)",
            "publication_date": "(leave blank — defaults to publish date)",
            "interior_and_paper_type": "Premium color ink & white paper",
            "trim_size": "8.5 x 11 in (21.59 x 27.94 cm)",
            "bleed_settings": "No bleed",
            "cover_finish": "Glossy",
            "manuscript_file": manuscript_pdf,
            "cover_upload": cover_files["pdf"],
            "cover_dimensions_check": {
                "required_full_wrap_inches":
                    f"{spec['width_in']} x {spec['height_in']}",
                "spine_width_inches": spec["spine_in"],
                "page_count_basis": page_count,
                "resolution": f"{DPI} DPI",
            },
            "ai_generated_content_disclosure": {
                "question":
                    "Did you use AI tools in creating texts, images, "
                    "and/or translations in your book?",
                "answer": "Yes",
                "text_dropdown":
                    "Entire work, with extensive editing",
                "images_dropdown":
                    "Some AI-generated images, with minimal or no editing",
                "translations_dropdown": "None",
                "why": "Pipeline drafts text and cover art with AI; KDP "
                       "requires disclosure even after heavy editing. It is "
                       "not shown to buyers and does not affect royalties.",
            },
            "book_preview": "Launch Previewer, approve, then Save and Continue",
        },
        "3_pricing_page": {
            "territories": "All territories (worldwide rights)",
            "primary_marketplace": "Amazon.com",
            "royalty_plan": "60% (paperback standard)",
            "estimated_printing_cost_usd": estimate_printing_cost(page_count),
            "minimum_list_price_usd": minimum_list_price(page_count),
            "suggested_list_price_usd":
                max(24.99, round(minimum_list_price(page_count) + 8.00, 2)),
            "other_marketplaces": "Auto-fill from Amazon.com price",
            "terms": "Agree & publish",
        },
        "optional_hardcover_variant": {
            "note": "Hardcover max trim is 8.25 x 11 in — NOT 8.5 x 11.",
            "trim_size": "8.25 x 11 in",
            "cover_finish": "Case laminate (always glossy-style)",
            "interior_and_paper_type": "Premium color ink & white paper",
        },
        "ebook_variant": {
            "cover_file": cover_files["ebook"],
            "royalty": "70% plan (price 2.99-9.99) or 35%",
            "kdp_select": "Your choice — 90-day Amazon exclusivity if enrolled",
            "ai_disclosure": "Same answers as paperback section",
        },
    }


# ======================================================================
# 6. MASTER ENTRY POINT + CLI
# ======================================================================

def package_book(title: str, subtitle: str, author: str, page_count: int,
                 theme: str, blurb: str, description: str = "",
                 keywords: list = None, manuscript_pdf: str = "",
                 art_backend: str = "xai", cover_only: bool = False) -> dict:
    """
    One call = complete KDP upload package.
    Returns paths to every artifact produced.
    """
    if page_count < MIN_PAGES:
        raise ValueError(f"KDP paperbacks need >= {MIN_PAGES} pages.")
    keywords = keywords or [w.strip() for w in theme.split(",")][:7]
    description = description or blurb[:4000]

    slug = "".join(c if c.isalnum() else "_" for c in title.lower())[:40]
    out_dir = PACKAGE_DIR / f"{slug}_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Cover art (front panel basis) — Grok Imagine default, procedural floor
    art_path = out_dir / "cover_art_raw.png"
    prompt = build_art_prompt(theme, title)
    if not generate_cover_art(prompt, art_path, backend=art_backend):
        if art_backend != "procedural":
            print("[*] Falling back to procedural art.")
        procedural_fallback_art(art_path, 2550, 3300, seed_theme=theme)

    # 2. Wraparound print cover + ebook front
    cover_files = compose_print_cover(art_path, title, subtitle, author,
                                      blurb, page_count, out_dir)

    # 3. Pre-answered upload manifest
    answers = build_kdp_answers(title, subtitle, author, description,
                                keywords, page_count, cover_files,
                                manuscript_pdf or
                                ("(existing interior — upload your own PDF)" if cover_only
                                 else "(export your manuscript to PDF first)"),
                                cover_only=cover_only)
    answers_path = out_dir / "kdp_answers.json"
    answers_path.write_text(json.dumps(answers, indent=2))
    print(f"[+] Upload answers manifest: {answers_path}")

    return {"package_dir": str(out_dir), "answers": str(answers_path),
            **cover_files}


def main():
    p = argparse.ArgumentParser(description="KDP cover + answers packager")
    p.add_argument("--title", required=True)
    p.add_argument("--subtitle", default="")
    p.add_argument("--author", default="Midnight Sapphire")
    p.add_argument("--pages", type=int, required=True,
                   help="Final interior page count (drives spine width)")
    p.add_argument("--theme", default="macabre fables, ancient scripts")
    p.add_argument("--blurb", default="", help="Back-cover blurb text")
    p.add_argument("--manuscript", default="", help="Path to interior PDF")
    p.add_argument("--cover-only", action="store_true",
                   help="You already have a finished book; build cover + answers only")
    p.add_argument("--art-backend", default="xai",
                   choices=["xai", "openrouter", "procedural"],
                   help="Cover art backend (default: xai / Grok Imagine, needs XAI_API_KEY)")
    args = p.parse_args()

    blurb = args.blurb or (
        f"{args.title}: a {args.theme} collection forged by an "
        "autonomous manuscript pipeline."
    )
    result = package_book(
        title=args.title, subtitle=args.subtitle, author=args.author,
        page_count=args.pages, theme=args.theme, blurb=blurb,
        manuscript_pdf=args.manuscript, art_backend=args.art_backend,
        cover_only=args.cover_only,
    )
    print("\n[+] PACKAGE COMPLETE")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
