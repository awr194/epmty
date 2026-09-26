"""Is the original product already available in Czechia? Evidence from its own website (step 10.1).

Only facts found on the original's site count; nothing is guessed:

  strong  - the site redirects to a .cz domain, declares hreflang="cs", links to its own .cz domain,
            serves <html lang="cs"> or offers "Čeština" in its language picker;
  weak    - prices in Kč / CZK (a currency picker can list CZK without real local sales).

"Czech Republic" in the page text is ignored: country drop-downs list every country.

Status: "yes" (any strong signal), "likely" (weak signals only), "unknown" (no signal or the site
could not be read). There is deliberately no "no": a missing signal on one page proves nothing.

Results live in data/original_cz.json (written by scripts/check_original_cz.py); an entry in the
overlay data/cz_enrichment.json (`original_available_in_cz`) overrides the check.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

RESULTS_PATH = Path(__file__).resolve().parents[1] / "data" / "original_cz.json"

STATUSES = ("yes", "likely", "unknown")

# Signal codes -> strength. Texts for the UI live in i18n/ui.py under "cz_sig_<code>".
STRONG = ("redirect_cz", "hreflang_cs", "link_cz_domain", "html_lang_cs", "lang_picker_cs", "og_locale_cs",
          "cs_path", "locale_url_cs")
_CS_PATH_SEGMENTS = {"cs", "cz", "cs-cz", "cs_cz"}
WEAK = ("price_czk",)

_HREFLANG = re.compile(r"""<link[^>]+hreflang\s*=\s*["']?(cs(?:[-_]cz)?)["'\s>]""", re.I)
# HTTP header form: Link: <https://x.com/cs/>; rel="alternate"; hreflang="cs"
_HREFLANG_HEADER = re.compile(r"""hreflang\s*=\s*["']?(cs(?:[-_]cz)?)\b""", re.I)
_OG_LOCALE = re.compile(r"""<meta[^>]+og:locale(?::alternate)?["'][^>]*content\s*=\s*["']?(cs[-_]CZ)""", re.I)
_HTML_LANG = re.compile(r"""<html[^>]*\blang\s*=\s*["']?(cs(?:-cz)?)\b""", re.I)
_HREF = re.compile(r"""href\s*=\s*["']?(https?://[^"'\s>]+)""", re.I)
# Bounded repetition, anchored on a non-digit boundary: an unbounded [\d\s.,]* backtracks
# quadratically on long runs of numbers and spaces (minified scripts) and hangs the check.
# The character classes contain a space and a no-break space (U+00A0).
_PRICE_CZK = re.compile(r"(?<![\d.,])(\d{1,3}(?:[  .,]?\d{3}){0,3}(?:[.,]\d{1,2})?[  ]?(?:Kč|CZK)\b"
                        r"|\bCZK[  ]?\d[\d.,]{0,12})")  # case-sensitive: "czk58" in a script is not a price
_LANG_PICKER = re.compile(r"Čeština", re.I)


def _host(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host[4:] if host.startswith("www.") else host


def brand_label(url: str) -> str:
    """'https://www.getjobber.com/x' -> 'getjobber' (the label left of the public suffix)."""
    parts = _host(url).split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net") and len(parts[-1]) == 2:  # example.co.uk
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else parts[0]


def locale_url_cs(url: str) -> bool:
    """The site sent us to its Czech edition: cz.example.com or example.com/cs/..., /cs-cz/, /cz/."""
    segments = [re.sub(r"\.html?$", "", x) for x in urlparse(url).path.lower().strip("/").split("/") if x]
    # /cs/en.html is an English page: another language code later in the path cancels the match
    other_lang = any(re.fullmatch(r"[a-z]{2}(?:[-_][a-z]{2})?", x) and x not in _CS_PATH_SEGMENTS
                     for x in segments[1:])
    return _host(url).startswith("cz.") or (bool(segments) and segments[0] in _CS_PATH_SEGMENTS and not other_lang)


def reclassify(result: dict) -> dict:
    """Re-apply the current rules to a stored result without fetching anything: drop price evidence
    the current pattern rejects, add the Czech-edition URL signal, recompute the status."""
    ev = [e for e in result.get("evidence", []) if e["signal"] != "locale_url_cs"
          and (e["signal"] != "price_czk" or _PRICE_CZK.fullmatch(e["value"]))]
    final, url = result.get("final_url", ""), result.get("url", "")
    if final and final != url and locale_url_cs(final):
        ev.append({"signal": "locale_url_cs", "value": final})
    return result | {"evidence": ev, "status": "unknown" if result.get("error") else classify(ev)}


def czech_page(html: str) -> str | None:
    """The page itself is in Czech (<html lang="cs"> or og:locale cs_CZ): the matched marker, else None."""
    m = _HTML_LANG.search(html) or _OG_LOCALE.search(html)
    return m.group(1) if m else None


def detect_signals(url: str, html: str, final_url: str | None = None, link_header: str = "") -> list[dict]:
    """Evidence items {"signal": code, "value": what was found} from one fetched page."""
    found: list[dict] = []
    final = final_url or url
    if _host(final).endswith(".cz") and not _host(url).endswith(".cz"):
        found.append({"signal": "redirect_cz", "value": final})
    elif final != url and locale_url_cs(final):
        found.append({"signal": "locale_url_cs", "value": final})
    m = _HREFLANG.search(html) or _HREFLANG_HEADER.search(link_header)
    if m:
        found.append({"signal": "hreflang_cs", "value": f'hreflang="{m.group(1)}"'})
    m = _OG_LOCALE.search(html)
    if m:
        found.append({"signal": "og_locale_cs", "value": f"og:locale {m.group(1)}"})
    brand = brand_label(url)
    for href in _HREF.findall(html):
        h = _host(href)
        if h.endswith(".cz") and brand_label(href) == brand and brand:
            found.append({"signal": "link_cz_domain", "value": href})
            break
    m = _HTML_LANG.search(html)
    if m:
        found.append({"signal": "html_lang_cs", "value": f'lang="{m.group(1)}"'})
    if _LANG_PICKER.search(html):
        found.append({"signal": "lang_picker_cs", "value": "Čeština"})
    m = _PRICE_CZK.search(html)
    if m:
        found.append({"signal": "price_czk", "value": " ".join(m.group(1).split())})
    return found


def classify(evidence: list[dict]) -> str:
    codes = {e["signal"] for e in evidence}
    if codes & set(STRONG):
        return "yes"
    if codes & set(WEAK):
        return "likely"
    return "unknown"


@lru_cache(maxsize=1)
def load_results(path: str = str(RESULTS_PATH)) -> dict[str, dict]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("models", {})
