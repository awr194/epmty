"""Check each original's website for signs that it already serves Czechia (step 10.1).

Fetches the model's own URL (respecting robots.txt, one request per second), records the
evidence found by market.original_cz.detect_signals() and writes:

  data/original_cz.json            - status + evidence per model name (read by cz_enrichment.py)
  reports/original_cz_unknown.md   - models with no evidence (to check by hand)

Already-checked models are skipped unless --refresh is given, so an interrupted run resumes.

  python scripts/check_original_cz.py                 # all models not checked yet
  python scripts/check_original_cz.py --limit 20      # first 20 unchecked
  python scripts/check_original_cz.py --only Spond --only Jobber --refresh
  python scripts/check_original_cz.py --recheck-unknown   # after a detector update (~30-40 min)
  python scripts/check_original_cz.py --reclassify        # re-apply rules to saved results, no network
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_loader import load_curated  # noqa: E402
from market.original_cz import RESULTS_PATH, brand_label, classify, czech_page, detect_signals, reclassify  # noqa: E402

REPORT_PATH = ROOT / "reports" / "original_cz_unknown.md"
USER_AGENT = "CzechBizRadar/1.0 (research; checks whether a product is offered in Czechia)"
TIMEOUT = 12
PAUSE_S = 1.0
CS_PATHS = ("/cs/", "/cs-cz/", "/cz/")
MAX_HTML = 1_000_000  # characters; enough for the <head> and the footer language picker


def _robots_allows(url: str, cache: dict[str, robotparser.RobotFileParser | None]) -> bool:
    parts = urlparse(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in cache:
        rp = robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            cache[base] = rp
        except requests.RequestException:
            cache[base] = None  # robots.txt unreachable: treat as allowed, like browsers do
    rp = cache[base]
    return rp is None or rp.can_fetch(USER_AGENT, url)


def check(url: str, robots_cache: dict) -> dict:
    """One model's result: status, evidence, HTTP details. Never raises."""
    out = {"url": url, "checked_at": date.today().isoformat()}
    if not url:
        return out | {"status": "unknown", "evidence": [], "error": "no_url"}
    if not _robots_allows(url, robots_cache):
        return out | {"status": "unknown", "evidence": [], "error": "robots_disallow"}
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "cs,en;q=0.5"},
                         timeout=TIMEOUT, allow_redirects=True)
    except requests.RequestException as e:
        return out | {"status": "unknown", "evidence": [], "error": type(e).__name__}
    out |= {"final_url": r.url, "http_status": r.status_code}
    if r.status_code >= 400:
        return out | {"status": "unknown", "evidence": [], "error": f"http_{r.status_code}"}
    evidence = detect_signals(url, r.text[:MAX_HTML], r.url, r.headers.get("Link", ""))
    if classify(evidence) != "yes":
        evidence += probe_cs_paths(r.url, robots_cache)
    return out | {"status": classify(evidence), "evidence": evidence}


def probe_cs_paths(base_url: str, robots_cache: dict) -> list[dict]:
    """Try /cs/, /cs-cz/, /cz/ on the same site. Counts only when the page stays on that path and is
    itself marked Czech (lang="cs" / og:locale cs_CZ): many sites answer 200 to any path."""
    parts = urlparse(base_url)
    root = f"{parts.scheme}://{parts.netloc}"
    for path in CS_PATHS:
        probe = root + path
        if not _robots_allows(probe, robots_cache):
            continue
        time.sleep(PAUSE_S)
        try:
            r = requests.get(probe, headers={"User-Agent": USER_AGENT, "Accept-Language": "cs"}, timeout=TIMEOUT, allow_redirects=True)
        except requests.RequestException:
            continue
        stays = urlparse(r.url).path.lower().rstrip("/").startswith(path.rstrip("/"))
        marker = czech_page(r.text[:MAX_HTML]) if r.status_code == 200 and stays else None
        if marker:
            return [{"signal": "cs_path", "value": f"{r.url} ({marker})"}]
    return []


def write_report(results: dict[str, dict], names: list[str]) -> None:
    unknown = [n for n in names if results.get(n, {}).get("status", "unknown") == "unknown"]
    blocked = sorted(n for n in unknown if results.get(n, {}).get("error"))
    silent = sorted(n for n in unknown if not results.get(n, {}).get("error"))
    lines = ["# Originals without evidence of Czech availability", "",
             "No Czech signal on the original's own site (or the site could not be read).",
             "This is NOT proof of absence - check by hand and record the result in",
             "`data/cz_enrichment.json` as `original_available_in_cz` (`yes` / `no`) with a source.", "",
             f"Total: **{len(unknown)}** of {len(names)} "
             f"(site not readable: {len(blocked)}, read but no signal: {len(silent)})", "",
             "## Site not readable (blocked, rate-limited, no URL) - check these by hand first", "",
             "| Model | URL | Reason |", "|---|---|---|"]
    lines += [f"| {n} | {results.get(n, {}).get('url', '')} | {results.get(n, {}).get('error', 'not checked')} |"
              for n in blocked]
    lines += ["", "## Read, no Czech signal (home page, Link header, /cs/ /cs-cz/ /cz/ checked)", "",
              "| Model | URL |", "|---|---|"]
    lines += [f"| {n} | {results.get(n, {}).get('url', '')} |" for n in silent]
    moved = sorted(n for n in names if (r := results.get(n)) and r.get("final_url") and r.get("url")
                   and brand_label(r["final_url"]) != brand_label(r["url"]))
    lines += ["", "## Redirected to another domain (rebrand, acquisition or a dead domain) - check the URL", "",
              "| Model | URL | Now goes to |", "|---|---|---|"]
    lines += [f"| {n} | {results[n]['url']} | {results[n]['final_url']} |" for n in moved]
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="check at most N models")
    ap.add_argument("--only", action="append", default=[], help="model name (repeatable)")
    ap.add_argument("--refresh", action="store_true", help="re-check models already in the results file")
    ap.add_argument("--recheck-unknown", action="store_true",
                    help="re-check only models whose status is 'unknown' (e.g. after the detector improved)")
    ap.add_argument("--reclassify", action="store_true",
                    help="no network: re-apply the current rules to the saved results and rewrite the report")
    args = ap.parse_args()

    models = load_curated()
    existing = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))["models"] if RESULTS_PATH.exists() else {}
    todo = [m for m in models if (not args.only or m.name in args.only) and (args.refresh or m.name not in existing
             or (args.recheck_unknown and existing[m.name].get("status") == "unknown"))]
    if args.limit:
        todo = todo[:args.limit]
    if args.reclassify:
        before = {n: r["status"] for n, r in existing.items()}
        existing = {n: reclassify(r) for n, r in existing.items()}
        for n, r in existing.items():
            if r["status"] != before[n]:
                print(f"{n}: {before[n]} -> {r['status']}")
        todo = []

    def save() -> None:
        RESULTS_PATH.write_text(json.dumps({"models": dict(sorted(existing.items()))}, ensure_ascii=False,
                                           indent=1) + "\n", encoding="utf-8")

    robots_cache: dict = {}
    try:
        for i, m in enumerate(todo, 1):
            print(f"[{i}/{len(todo)}] {m.name} ... ", end="", flush=True)
            res = check(m.url, robots_cache)
            existing[m.name] = res
            print(f"{res['status']} {res.get('error', '')}")
            if i % 20 == 0:  # save progress
                save()
            time.sleep(PAUSE_S)
    except KeyboardInterrupt:
        print("\nInterrupted - progress saved; run again to continue.")
    finally:
        save()

    write_report(existing, [m.name for m in models])
    counts = {s: sum(1 for r in existing.values() if r["status"] == s) for s in ("yes", "likely", "unknown")}
    print(f"\nChecked {len(existing)}: {counts}. Unknown list: {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
