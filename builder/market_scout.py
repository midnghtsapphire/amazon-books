#!/usr/bin/env python3
"""
Market Scout — free-channel SEO/demand intelligence for length and topic
decisions. No paid tools, no API keys.

What it answers:
  1. "How long are the books buyers actually pick in my category?"
     -> Google Books API (free, keyless): pageCount + ratingsCount across a
        category. ratingsCount is the demand proxy (people who finished and
        rated it); pageCount is the length they bought. Weighted median =
        the market's preferred length, not a guru's guess.
  2. "What are buyers typing into Amazon right now?"
     -> Amazon search autocomplete (free endpoint): real storefront query
        expansions for seed terms. These double as KDP keyword-slot fodder.
  3. "Can I afford that length?"
     -> KDP print-cost model: long books in premium color get expensive fast;
        beyond ~150 pages of text, black & white interior keeps the minimum
        list price in buyer territory.

SEM note: true paid-search volume data (Google Ads Keyword Planner etc.)
is paywalled or account-gated. The free proxies above cover the same
question — what buyers search and what they buy — at zero cost.

Fallback: if the network is unreachable (air-gapped drafting box), every
function degrades to the static GENRE_LENGTH_MATRIX below, so the pipeline
never stalls on a scout failure.

Usage:
  python market_scout.py "short stories anthology"
  python market_scout.py "dark fantasy" --json
"""

import argparse
import json
import statistics
import sys

import requests

GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
AMAZON_SUGGEST_URL = "https://completion.amazon.com/api/2017/suggestions"

# Publisher-norm length bands (pages at ~350 words/page, 8.5x11 typesetting).
# Used as the offline floor and as sanity clamps for live data.
GENRE_LENGTH_MATRIX = {
    "short stories":      {"low": 120, "sweet": 200, "high": 300},
    "anthology":          {"low": 150, "sweet": 220, "high": 320},
    "novella":            {"low": 80,  "sweet": 120, "high": 160},
    "dark fantasy":       {"low": 250, "sweet": 320, "high": 420},
    "fairy tales":        {"low": 140, "sweet": 210, "high": 300},
    "mythology":          {"low": 200, "sweet": 280, "high": 380},
    "technical":          {"low": 150, "sweet": 240, "high": 350},
    "default":            {"low": 180, "sweet": 260, "high": 360},
}

WORDS_PER_PAGE = 350        # calibrated against book_builder typesetting
KDP_MAX_PAGES = 828
PREMIUM_COLOR_COMFORT_LIMIT = 150   # beyond this, print cost bites — see below


def _matrix_for(category: str) -> dict:
    c = category.lower()
    for key, band in GENRE_LENGTH_MATRIX.items():
        if key in c:
            return band
    return GENRE_LENGTH_MATRIX["default"]


def fetch_category_lengths(category: str, samples: int = 40) -> dict | None:
    """Google Books: weighted length stats for a category. ratingsCount weights
    each title — length preference of *buyers*, not of publishers alone."""
    try:
        resp = requests.get(
            GOOGLE_BOOKS_URL,
            params={"q": f"subject:{category.replace(' ', '+')}",
                    "maxResults": min(samples, 40), "orderBy": "relevance",
                    "printType": "books", "langRestrict": "en"},
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"[!] Google Books unreachable ({e}) — offline matrix only.",
              file=sys.stderr)
        return None

    points = []  # (page_count, weight)
    for item in resp.json().get("items", []):
        info = item.get("volumeInfo", {})
        pages = info.get("pageCount")
        if not pages or pages < 24:
            continue
        weight = max(1, info.get("ratingsCount", 0))
        points.append((pages, weight))

    if len(points) < 5:
        return None

    pages = [p for p, _ in points]
    # weighted median: the page count where half the *ratings mass* sits
    ordered = sorted(points)
    total_w = sum(w for _, w in ordered)
    acc, weighted_median = 0, ordered[-1][0]
    for p, w in ordered:
        acc += w
        if acc >= total_w / 2:
            weighted_median = p
            break

    return {
        "sample_size": len(points),
        "median_pages": int(statistics.median(pages)),
        "weighted_median_pages": int(weighted_median),
        "p25": int(statistics.quantiles(pages, n=4)[0]),
        "p75": int(statistics.quantiles(pages, n=4)[2]),
    }


def fetch_buyer_queries(seed: str, limit: int = 10) -> list:
    """Amazon storefront autocomplete: what book buyers actually type."""
    try:
        resp = requests.get(
            AMAZON_SUGGEST_URL,
            params={"mid": "ATVPDKIKX0DER", "alias": "stripbooks",
                    "prefix": seed},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=10,
        )
        resp.raise_for_status()
        return [s["value"] for s in resp.json().get("suggestions", [])][:limit]
    except Exception:
        return []


def recommend_ink(target_pages: int) -> dict:
    """Length vs print-cost guardrail. Premium color at 300+ pages prices the
    book out of its own market — long text books belong in black & white."""
    premium_min = kdp_cost.estimate(target_pages, "premium_color")
    bw_min = kdp_cost.estimate(target_pages, "black_white")
    if target_pages > PREMIUM_COLOR_COMFORT_LIMIT:
        return {
            "recommended_ink": "black_white",
            "reason": (f"At {target_pages} pages, premium color forces a "
                       f"~${premium_min:.2f} minimum list price vs "
                       f"~${bw_min:.2f} in black & white. Buyers of long "
                       f"text books expect B&W pricing."),
            "premium_color_min_price": premium_min,
            "black_white_min_price": bw_min,
        }
    return {
        "recommended_ink": "premium_color",
        "reason": "Short enough that premium color stays price-competitive.",
        "premium_color_min_price": premium_min,
        "black_white_min_price": bw_min,
    }


def recommend_length(category: str) -> dict:
    """One call = target page band + evidence + ink guardrail + demand keywords."""
    matrix = _matrix_for(category)
    live = fetch_category_lengths(category)

    if live:
        # Market data wins when it exists; matrix clamps statistical noise.
        target = max(matrix["low"],
                     min(live["weighted_median_pages"], matrix["high"]))
        band = {"low": live["p25"], "target": target, "high": live["p75"],
                "evidence": f"{live['sample_size']} live titles, ratings-weighted"}
    else:
        target = matrix["sweet"]
        band = {"low": matrix["low"], "target": target, "high": matrix["high"],
                "evidence": "offline genre matrix (network unavailable)"}

    target = min(target, KDP_MAX_PAGES)
    return {
        "category": category,
        "target_pages": target,
        "target_words": target * WORDS_PER_PAGE,
        "band": band,
        "ink": recommend_ink(target),
        "buyer_queries": fetch_buyer_queries(category),
    }


# local cost helper (mirrors packaging/kdp_packager.py constants so this
# module stays runnable standalone from builder/)
class kdp_cost:  # noqa: N801
    _MODEL = {
        "black_white":    {"fixed": 1.00, "per_page": 0.012},
        "standard_color": {"fixed": 1.00, "per_page": 0.027},
        "premium_color":  {"fixed": 1.00, "per_page": 0.065},
    }

    @staticmethod
    def estimate(pages: int, ink: str) -> float:
        m = kdp_cost._MODEL[ink]
        cost = m["fixed"] + m["per_page"] * pages
        return round(cost / 0.60 + 0.01, 2)   # minimum list price


def main():
    p = argparse.ArgumentParser(description="Free-channel market length & demand scout")
    p.add_argument("category", help='e.g. "short stories anthology", "dark fantasy"')
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args()

    rec = recommend_length(args.category)
    if args.json:
        print(json.dumps(rec, indent=2))
        return

    print(f"\n=== MARKET SCOUT: {rec['category']} ===")
    print(f"Target length : {rec['target_pages']} pages "
          f"(~{rec['target_words']:,} words)")
    print(f"Buyer band    : {rec['band']['low']}–{rec['band']['high']} pages "
          f"[{rec['band']['evidence']}]")
    print(f"Interior ink  : {rec['ink']['recommended_ink']} — {rec['ink']['reason']}")
    if rec["buyer_queries"]:
        print("Buyers search :")
        for q in rec["buyer_queries"]:
            print(f"  - {q}")


if __name__ == "__main__":
    main()
