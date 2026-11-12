#!/usr/bin/env python3
"""Generate candidate front-cover art with the amazon-books Grok Imagine backend (kdp_packager.generate_cover_art_xai).
Never prints the key. Writes NEW files only (skips existing)."""
import os
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
# Repo root when this file lives at tools/print-v1/; also accept the older box layout.
for candidate in (HERE.parents[1], Path("/workspace/amazon-books-readonly")):
    packaging = candidate / "packaging"
    if packaging.is_dir():
        sys.path.insert(0, str(packaging))
        break

import kdp_packager as kp

OUT = Path(os.environ.get("GROK_ART_OUT", str(HERE / "art-v2")))
OUT.mkdir(parents=True, exist_ok=True)

NOTEXT = " Absolutely no text, no letters, no words, no numbers, no logos, no watermark, no signature anywhere in the image. Portrait 3:4 book-cover artwork with calm uncluttered negative space in the top third and bottom fifth for title and author typography."
P = {
 "fg_a": "Clean modern business and startup illustration: a single glowing golden lightbulb resting on a stack of blank sticky notes and a notebook, with a small green seedling sprouting beside it, on a deep midnight navy background with subtle gold geometric line accents. Flat minimal vector style with soft gradients, premium editorial look, high contrast, centered composition." + NOTEXT,
 "fg_b": "Clean modern startup concept art: an abstract minimalist path of small gold stepping stones rising from a dark navy foreground toward a bright glowing gold circle on the horizon, with a thin magnifying glass outline and a few tiny scattered sparks, deep midnight blue gradient sky, flat geometric vector style, elegant and professional, centered composition." + NOTEXT,
 "fg_c": "Modern minimalist business illustration in deep navy and warm gold: a hand-drawn style sketch of a simple storefront or product box being tested, with checkmark-like abstract shapes, a magnifying lens over a small glowing coin, clean geometric shapes, subtle grid paper texture, polished flat vector style, professional startup mood." + NOTEXT,
 "figs_a": "Painterly still life of a Bronze Age Aegean kitchen: ripe purple figs, one cut open showing pink seeds, a shallow clay bowl of dark golden honey, a small kylix wine cup with dark red wine, a clay oil lamp, olives and a few barley ears, resting on a rough pale limestone slab against a warm cream and terracotta plaster wall, soft natural window light, realistic detailed oil-painting look, earthy warm palette." + NOTEXT,
 "figs_b": "Top-down editorial food photograph style: dried and fresh figs, honey dripping from a wooden dipper into a rustic terracotta bowl, olive branch, barley stalks, a simple clay cup of wine, on a weathered stone surface with warm cream tones, soft diffused daylight, muted earthy palette of cream, terracotta, fig purple and olive green, calm and elegant." + NOTEXT,
 "figs_c": "Elegant still life of figs, honey and wine in ancient Aegean ceramic vessels on a pale sandstone ledge, with a softly blurred sunlit Mediterranean courtyard wall behind, warm golden hour light, painterly realism, cream and clay background colours that stay light and soft." + NOTEXT,
}


def _redact(text: str) -> str:
    """Return text with any API key value removed. Never print the key."""
    key = os.environ.get("XAI_API_KEY") or ""
    if key and key in text:
        return text.replace(key, "[redacted]")
    return text


def generate_cover_art_xai(prompt: str, out_path: Path) -> bool:
    """Call the same xAI endpoint as kdp_packager.generate_cover_art_xai.

    On HTTP or API rejection, print the status and response body (never the
    key) so a bad key is visible in CI logs, then return False.
    """
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        print("[!] XAI_API_KEY not set — Grok Imagine backend unavailable.")
        return False
    try:
        resp = requests.post(
            kp.XAI_IMAGES_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": kp.XAI_IMAGE_MODEL, "prompt": prompt, "n": 1,
                  "aspect_ratio": "3:4", "resolution": "2k"},
            timeout=300,
        )
    except Exception as e:
        print(f"[!] Grok Imagine request failed: {_redact(str(e))}")
        return False
    if not resp.ok:
        body = (resp.text or "").strip() or (resp.reason or "(empty body)")
        print(f"[!] xAI API error: HTTP {resp.status_code} {resp.reason}")
        print(_redact(body))
        return False
    try:
        url = resp.json()["data"][0]["url"]
        out_path.write_bytes(requests.get(url, timeout=120).content)
        print(f"[+] Grok Imagine cover art generated: {out_path}")
        return True
    except Exception as e:
        print(f"[!] Grok Imagine generation failed ({_redact(str(e))}).")
        return False


failed = 0
for k in sys.argv[1:] or P:
    f = OUT / f"{k}_grok_imagine_raw.png"
    if f.exists():
        print("exists", f)
        continue
    ok = generate_cover_art_xai(P[k], f)
    print(k, "ok" if ok else "FAILED")
    if not ok:
        failed += 1
if failed:
    sys.exit(1)
