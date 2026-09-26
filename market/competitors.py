"""Local competitors imported from stored LLM reports (step 10.2).

scripts/import_llm_competitors.py reads data/llm_reports/*.json and writes data/llm_competitors.json;
cz_enrichment.py adds those entries to each model's local_incumbents (unverified, with their source).
scripts/verify_competitors.py checks their URLs, because an LLM can invent a plausible address.

Rules:
  - threat High / Medium / Low (any language) -> strength 3 / 2 / 1; unknown -> 2;
  - substitutes (Facebook groups, spreadsheets...) are not incumbents and are skipped;
  - the model itself is never its own incumbent (same host or same normalised name);
  - duplicates (same host, or same normalised name) are merged; the newest run wins.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

RESULTS_PATH = Path(__file__).resolve().parents[1] / "data" / "llm_competitors.json"

_THREAT = {
    3: ("high", "высокая", "высокий", "vysoká", "vysoke"),
    2: ("medium", "средняя", "средний", "střední"),
    1: ("low", "низкая", "низкий", "nízká"),
}
_SUBSTITUTE_WORDS = ("заменител", "substitut", "náhrad")
# Platforms whose URL says nothing about the competitor (a Facebook group, a search page).
GENERIC_HOSTS = {"facebook.com", "instagram.com", "linkedin.com", "youtube.com", "google.com", "google.cz",
                 "seznam.cz", "t.me", "x.com", "twitter.com"}
_CYRILLIC_PARENS = re.compile(r"\s*\([^)]*[А-Яа-яЁё][^)]*\)")


def threat_to_strength(threat: str) -> int:
    t = (threat or "").strip().lower()
    for strength, words in _THREAT.items():
        if any(t.startswith(w) for w in words):
            return strength
    return 2


def host(url: str) -> str:
    h = (urlparse(url).hostname or "") if url else ""
    return h[4:] if h.startswith("www.") else h


def norm_name(name: str) -> str:
    """'Choice (choice.qr)' -> 'choice'; 'OneMenu.cz' -> 'onemenu'."""
    base = re.sub(r"\(.*?\)", "", name).lower()
    base = re.sub(r"\.(cz|com|sk|eu|io)\b", "", base)
    return re.sub(r"[^0-9a-zà-ž]+", "", base)


def clean_name(name: str) -> str:
    """Drop Russian/other-language explanations in parentheses: 'Dotykačka (модуль ...)' -> 'Dotykačka'."""
    return _CYRILLIC_PARENS.sub("", name).strip()


def same_company(a: dict, b: dict) -> bool:
    ha, hb = host(a.get("url", "")), host(b.get("url", ""))
    if ha and hb and ha == hb and ha not in GENERIC_HOSTS:
        return True
    na, nb = norm_name(a["name"]), norm_name(b["name"])
    return bool(na) and (na == nb or (len(na) >= 5 and len(nb) >= 5 and (na.startswith(nb) or nb.startswith(na))))


def is_substitute(kind: str) -> bool:
    k = (kind or "").lower()
    return any(w in k for w in _SUBSTITUTE_WORDS)


def extract(model_name: str, model_url: str, runs: list[dict]) -> list[dict]:
    """Incumbent dicts from all runs of one model (oldest first), deduplicated, newest mention wins."""
    me = {"name": model_name, "url": model_url}
    merged: list[dict] = []
    for run in runs:
        date = run.get("timestamp", "")[:10]
        for c in run.get("report", {}).get("competitors", []):
            if is_substitute(c.get("kind", "")):
                continue
            url = c.get("url") or ""
            if host(url) in GENERIC_HOSTS:
                url = ""
            item = {"name": clean_name(c["name"]), "strength": threat_to_strength(c.get("threat", "")),
                    "url": url, "note": "", "kind": c.get("kind", ""), "verified": False,
                    "source": f"{run.get('engine', 'llm')} {date}".strip(), "url_status": "", "checked_at": ""}
            if same_company(item, me):
                continue
            for i, old in enumerate(merged):
                if same_company(item, old):
                    item["mentions"] = old.get("mentions", 1) + 1
                    item["url"] = item["url"] or old["url"]
                    merged[i] = item
                    break
            else:
                item["mentions"] = 1
                merged.append(item)
    return merged


@lru_cache(maxsize=1)
def load_results(path: str = str(RESULTS_PATH)) -> dict[str, list[dict]]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("models", {})


def add_new(existing: list[dict], imported: list[dict]) -> list[dict]:
    """Existing (hand / seeded) incumbents first; imported ones only when not already there."""
    out = list(existing)
    for item in imported:
        if not any(same_company(item, e) for e in out):
            out.append(item)
    return out
