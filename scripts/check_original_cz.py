"""Check each original's website for signs that it already serves Czechia (step 10.1).

Fetches the model's own URL (respecting robots.txt, one request per second), records the
evidence found by market.original_cz.detect_signals() and writes:

  data/original_cz.json            - status + evidence per model name (read by cz_enrichment.py)
  reports/original_cz_unknown.md   - models with no evidence (to check by hand)

Already-checked models are skipped unless --refresh is given, so an interrupted run resumes.

  python scripts/check_original_cz.py                 # all models not checked yet
  python scripts/check_original_cz.py --limit 20      # first 20 unchecked
  python scripts/check_original_cz.py --only Spond --only Jobber --refresh
  python scripts/check_original_cz.py --recheck-unknown   # after a detector update (1-1.5 h; Ctrl+C and
                                                           # run again: today's results are kept)
  python scripts/check_original_cz.py --reclassify        # re-apply rules to saved results, no network
  python scripts/check_original_cz.py --archive           # only 401/403 sites via Wayback (a few minutes)

Politeness: robots.txt is respected (a disallowed site is never read, not even from an archive), one
request per second, one retry after 429 / 5xx honouring Retry-After. A site that answers 401/403 is not
worked around; instead its latest public Wayback Machine copy is checked and dated (archived_at).
An SSL error is retried once on the www / bare-domain variant, with certificate checks left on.
"""

from __future__ import annotations

import argparse
import gzip
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
from market.original_cz import (RESULTS_PATH, brand_label, classify, czech_page, detect_signals,  # noqa: E402
                                reclassify, sitemap_children, sitemap_czech_urls, sitemap_evidence)

REPORT_PATH = ROOT / "reports" / "original_cz_unknown.md"
USER_AGENT = "CzechBizRadar/1.0 (research; checks whether a product is offered in Czechia)"
TIMEOUT = 12
PAUSE_S = 1.0
CS_PATHS = ("/cs/", "/cs-cz/", "/cz/")
MAX_HTML = 1_000_000  # characters; enough for the <head> and the footer language picker
MAX_SITEMAPS = 5       # sitemap files per site (robots.txt entries + children of a sitemap index)
MAX_SITEMAP = 5_000_000
RETRY_STATUSES = {429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 525}
RETRY_MAX_WAIT_S = 60
WAYBACK_AVAILABLE = "https://archive.org/wayback/available"
WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"
WAYBACK_PAUSE_S = 5.0     # archive.org answers 429 quickly; stay well below its limit
WAYBACK_BACKOFF_S = 60


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


def _www_variant(url: str) -> str:
    """https://www.x.com/a <-> https://x.com/a (some certificates cover only one of the two names)."""
    p = urlparse(url)
    host = p.netloc[4:] if p.netloc.startswith("www.") else "www." + p.netloc
    return p._replace(netloc=host).geturl()


def _get(url: str, lang: str = "cs,en;q=0.5") -> requests.Response:
    """GET with one polite retry on 429 / 5xx (Retry-After honoured, capped)."""
    headers = {"User-Agent": USER_AGENT, "Accept-Language": lang}
    r = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
    if r.status_code in RETRY_STATUSES:
        ra = str(r.headers.get("Retry-After", ""))
        time.sleep(min(int(ra), RETRY_MAX_WAIT_S) if ra.isdigit() else 15 * PAUSE_S)
        r = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
    return r


def check(url: str, robots_cache: dict, wayback: bool = True) -> dict:
    """One model's result: status, evidence, HTTP details. Never raises."""
    out = {"url": url, "checked_at": date.today().isoformat()}
    if not url:
        return out | {"status": "unknown", "evidence": [], "error": "no_url"}
    if not _robots_allows(url, robots_cache):
        return out | {"status": "unknown", "evidence": [], "error": "robots_disallow"}
    try:
        try:
            r = _get(url)
        except requests.exceptions.SSLError:
            # certificate valid only for the other name: try it (verification stays on)
            alt = _www_variant(url)
            if not _robots_allows(alt, robots_cache):
                raise
            r = _get(alt)
            out["tried_url"] = alt
    except requests.RequestException as e:
        return out | {"status": "unknown", "evidence": [], "error": type(e).__name__}
    out |= {"final_url": r.url, "http_status": r.status_code}
    if r.status_code >= 400:
        blocked = out | {"status": "unknown", "evidence": [], "error": f"http_{r.status_code}"}
        if wayback and r.status_code in (401, 403):
            # the live site refuses automated requests: we do not get around that, but a public
            # archive copy is a fact with a date
            arch = check_wayback(url)
            if "via" in arch:
                return {k: v for k, v in blocked.items() if k != "error"} | {"live_error": blocked["error"]} | arch
            return blocked | arch  # keeps the reason, e.g. wayback_http_429: a later run tries again
        return blocked
    evidence = detect_signals(url, r.text[:MAX_HTML], r.url, r.headers.get("Link", ""))
    if classify(evidence) != "yes":
        evidence += probe_cs_paths(r.url, robots_cache)
    if classify(evidence) != "yes":
        evidence += probe_sitemaps(r.url, robots_cache)
    return out | {"status": classify(evidence), "evidence": evidence}


def _wayback_json(url: str, params: dict):
    """GET a Wayback API as JSON; one retry after 429 (the archive rate-limits hard). Raises on failure."""
    for attempt in (1, 2):
        time.sleep(WAYBACK_PAUSE_S)
        r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT * 2)
        if r.status_code == 429 and attempt == 1:
            ra = str(r.headers.get("Retry-After", ""))
            time.sleep(min(int(ra), RETRY_MAX_WAIT_S) if ra.isdigit() else WAYBACK_BACKOFF_S)
            continue
        if r.status_code != 200:
            raise WaybackError(f"wayback_http_{r.status_code}")
        return r.json()


class WaybackError(Exception):
    pass


# Fuse: archive.org blocks an IP for a long while after a burst. After this many 429s in a row the rest of
# the run skips the archive (the sites keep wayback_error=..._429 and are retried by a later run).
WAYBACK_MAX_429 = 2
_wayback_429_streak = 0


def latest_snapshot(url: str) -> str | None:
    """Timestamp (YYYYMMDDhhmmss) of the latest archived copy that was a 200 page, or None if there is none.
    Tries the 'available' API, then the CDX index (the first is often empty or slow)."""
    snap = (_wayback_json(WAYBACK_AVAILABLE, {"url": url}).get("archived_snapshots", {}).get("closest") or {})
    if snap.get("available") and str(snap.get("status", "200")) == "200":
        return snap["timestamp"]
    rows = _wayback_json(WAYBACK_CDX, {"url": url, "output": "json", "fl": "timestamp",
                                       "filter": "statuscode:200", "limit": "-1"})
    return rows[-1][0] if len(rows) > 1 else None


def check_wayback(url: str) -> dict:
    """Latest Wayback Machine copy of the page, checked with the same rules. The evidence is dated by the
    snapshot (archived_at), not by today. Without a usable copy: {"wayback_error": reason}."""
    global _wayback_429_streak
    if _wayback_429_streak >= WAYBACK_MAX_429:
        return {"wayback_error": "wayback_skipped_after_429"}
    try:
        ts = latest_snapshot(url)
        _wayback_429_streak = 0
        if not ts:
            return {"wayback_error": "no_snapshot"}
        time.sleep(WAYBACK_PAUSE_S)
        r = requests.get(f"https://web.archive.org/web/{ts}id_/{url}", headers={"User-Agent": USER_AGENT},
                         timeout=TIMEOUT * 2)
        if r.status_code != 200:
            return {"wayback_error": f"wayback_http_{r.status_code}"}
    except WaybackError as e:
        _wayback_429_streak = _wayback_429_streak + 1 if str(e).endswith("429") else 0
        return {"wayback_error": str(e)}
    except (requests.RequestException, ValueError, KeyError, IndexError) as e:
        return {"wayback_error": type(e).__name__}
    evidence = detect_signals(url, r.text[:MAX_HTML])
    return {"status": classify(evidence), "evidence": evidence, "via": "wayback",
            "archived_at": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}", "snapshot": f"https://web.archive.org/web/{ts}/{url}"}


def probe_sitemaps(base_url: str, robots_cache: dict) -> list[dict]:
    """Read the site's sitemaps (listed in robots.txt, else /sitemap.xml) and look for Czech pages:
    hreflang="cs" alternates, /cs/ or /cs-cz/ URLs. Legal pages alone or /cz/ paths alone are weak."""
    parts = urlparse(base_url)
    root = f"{parts.scheme}://{parts.netloc}"
    _robots_allows(root + "/", robots_cache)  # fills the cache after a redirect to another host
    rp = robots_cache.get(root)
    listed = (rp.site_maps() if rp else None) or [root + "/sitemap.xml"]
    queue = [u for u in listed if brand_label(u) == brand_label(base_url)][:MAX_SITEMAPS]
    strong: list[str] = []
    cz_only: list[str] = []
    fetched = 0
    while queue and fetched < MAX_SITEMAPS:
        sm = queue.pop(0)
        if not _robots_allows(sm, robots_cache):
            continue
        fetched += 1
        time.sleep(PAUSE_S)
        try:
            r = requests.get(sm, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        except requests.RequestException:
            continue
        if r.status_code != 200:
            continue
        xml = r.text
        if sm.endswith(".gz") and r.content[:2] == b"\x1f\x8b":
            try:
                xml = gzip.decompress(r.content).decode("utf-8", "replace")
            except (OSError, EOFError):
                continue
        xml = xml[:MAX_SITEMAP]
        kids = sitemap_children(xml)
        if kids:
            queue = [k for k in kids if brand_label(k) == brand_label(base_url)][:MAX_SITEMAPS] + queue
            continue
        s, c = sitemap_czech_urls(xml, base_url)
        strong += s
        cz_only += c
        if strong and sitemap_evidence(strong, [])[0]["signal"] == "sitemap_cs":
            break
    return sitemap_evidence(strong, cz_only)


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
            r = requests.get(probe, headers={"User-Agent": USER_AGENT, "Accept-Language": "cs"}, timeout=TIMEOUT,
                             allow_redirects=True)
        except requests.RequestException:
            continue
        stays = urlparse(r.url).path.lower().rstrip("/").startswith(path.rstrip("/"))
        marker = czech_page(r.text[:MAX_HTML]) if r.status_code == 200 and stays else None
        if marker:
            return [{"signal": "cs_path", "value": f"{r.url} ({marker})"}]
    return []


def write_report(results: dict[str, dict], names: list[str]) -> None:
    unknown = [n for n in names if results.get(n, {}).get("status", "unknown") == "unknown"]
    no_url = sorted(n for n in unknown if results.get(n, {}).get("error") == "no_url")
    blocked = sorted(n for n in unknown if results.get(n, {}).get("error") not in (None, "no_url"))
    silent = sorted(n for n in unknown if not results.get(n, {}).get("error"))
    lines = ["# Originals without evidence of Czech availability", "",
             "No Czech signal on the original's own site (or the site could not be read).",
             "This is NOT proof of absence - check by hand and record the result in",
             "`data/cz_enrichment.json` as `original_available_in_cz` (`yes` / `no`) with a source.", "",
             f"Total: **{len(unknown)}** of {len(names)} "
             f"(site not readable: {len(blocked)}, no product URL: {len(no_url)}, read but no signal: {len(silent)})", "",
             "## Site not readable (blocked, rate-limited, no URL) - check these by hand first", "",
             "| Model | URL | Reason |", "|---|---|---|"]
    lines += [f"| {n} | {results.get(n, {}).get('url', '')} | {results.get(n, {}).get('error', 'not checked')}"
              + (f", archive: {results[n]['wayback_error']}" if results.get(n, {}).get("wayback_error") else "")
              + " |" for n in blocked]
    lines += ["", "## Not applicable: no product URL (an archetype, or the company has no site)", ""] + [f"- {n}" for n in no_url]
    lines += ["", "## Read, no Czech signal (home page, Link header, /cs/ /cs-cz/ /cz/, sitemaps checked;",
              "for sites that block bots - the latest Wayback Machine copy of the home page)", "",
              "| Model | URL |", "|---|---|"]
    lines += [f"| {n} | {results.get(n, {}).get('url', '')}"
              + (f" (archive copy {results[n]['archived_at']})" if results.get(n, {}).get("via") == "wayback" else "")
              + " |" for n in silent]
    moved = sorted(n for n in names if (r := results.get(n)) and r.get("final_url") and r.get("url")
                   and brand_label(r["final_url"]) != brand_label(r["url"]))
    lines += ["", "## Redirected to another domain (rebrand, acquisition or a dead domain) - check the URL", "",
              "| Model | URL | Now goes to |", "|---|---|---|"]
    lines += [f"| {n} | {results[n]['url']} | {results[n]['final_url']} |" for n in moved]
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def needs_recheck(r: dict, today: str) -> bool:
    """--recheck-unknown: an 'unknown' result is checked again unless it was checked today (so an
    interrupted run resumes)."""
    return r.get("status") == "unknown" and r.get("checked_at") != today


def needs_archive(r: dict) -> bool:
    """--archive: a 401/403 site whose Wayback copy has not been read (never tried, or archive.org said 429)."""
    return (r.get("status") == "unknown" and r.get("error") in ("http_401", "http_403")
            and "429" in str(r.get("wayback_error", "429")))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="check at most N models")
    ap.add_argument("--only", action="append", default=[], help="model name (repeatable)")
    ap.add_argument("--refresh", action="store_true", help="re-check models already in the results file")
    ap.add_argument("--recheck-unknown", action="store_true",
                    help="re-check only models whose status is 'unknown' (e.g. after the detector improved)")
    ap.add_argument("--archive", action="store_true",
                    help="only the sites that answered 401/403 and whose archive copy is not read yet (few requests)")
    ap.add_argument("--no-wayback", action="store_true",
                    help="do not fall back to the Wayback Machine copy when the site answers 401/403")
    ap.add_argument("--reclassify", action="store_true",
                    help="no network: re-apply the current rules to the saved results and rewrite the report")
    args = ap.parse_args()

    models = load_curated()
    existing = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))["models"] if RESULTS_PATH.exists() else {}
    today = date.today().isoformat()
    todo = [m for m in models if (not args.only or m.name in args.only) and (args.refresh or m.name not in existing
             or (args.recheck_unknown and needs_recheck(existing[m.name], today))
             or (args.archive and needs_archive(existing[m.name])))]
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
            res = check(m.url, robots_cache, wayback=not args.no_wayback)
            existing[m.name] = res
            note = (f" (wayback {res['archived_at']})" if res.get("via")
                    else f" ({res['wayback_error']})" if res.get("wayback_error") else "")
            print(f"{res['status']} {res.get('error', '')}{note}")
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
