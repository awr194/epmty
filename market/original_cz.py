"""Is the original product already available in Czechia? Evidence from its own website (step 10.1).

Only facts found on the original's site count; nothing is guessed:

  strong  - the site redirects to a .cz domain, declares hreflang="cs", links to its own .cz domain,
            serves <html lang="cs"> or offers "Čeština" in its language picker; its sitemap lists Czech
            content pages (hreflang="cs", /cs/, /cs-cz/);
  weak    - prices in Kč / CZK (a currency picker can list CZK without real local sales); a sitemap with
            Czech legal pages only, or only /cz/ paths.

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
          "cs_path", "locale_url_cs", "sitemap_cs")
_CS_PATH_SEGMENTS = {"cs", "cz", "cs-cz", "cs_cz"}
# sitemap_cs_weak: the sitemap lists Czech pages, but only legal ones (privacy, terms) or only /cz/ paths
# (/cz/ is also used for country pages in English, e.g. data for Czech cities).
WEAK = ("price_czk", "sitemap_cs_weak")

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
# Case-sensitive: a language picker names Czech in Czech, capitalised. The Google Translate widget, shown to
# visitors with a Czech browser, lists "čeština" in lower case and says nothing about the site itself.
_LANG_PICKER = re.compile(r"Čeština")

# Sitemaps: <loc>https://x.com/cs/page</loc> and <xhtml:link rel="alternate" hreflang="cs" href="..."/>
_SM_LOC = re.compile(r"<loc>\s*([^<\s]{1,2000})\s*</loc>", re.I)
_SM_ALT = re.compile(r"<(?:xhtml:)?link\b[^>]{0,800}>", re.I)
_SM_ALT_LANG = re.compile(r"""hreflang\s*=\s*["']?(cs(?:[-_]cz)?)["'\s/>]""", re.I)
_SM_ALT_HREF = re.compile(r"""href\s*=\s*["']?([^"'\s>]{1,2000})""", re.I)
_LEGAL_PAGE = re.compile(r"privacy|terms|cookie|legal|impressum|imprint|gdpr|polic|datenschutz|agb|"
                         r"podminky|ochrana|obchodni|withdraw", re.I)


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


def sitemap_children(xml: str) -> list[str]:
    """Child sitemaps of a <sitemapindex>, Czech-looking ones first (sitemap-cs.xml, /cs/sitemap.xml)."""
    if not re.search(r"<sitemapindex\b", xml[:5000], re.I):
        return []
    kids = _SM_LOC.findall(xml)
    czech = [k for k in kids if re.search(r"[/_.-](cs|cz|cs[-_]cz)([/_.-]|$)", urlparse(k).path, re.I)]
    return czech + [k for k in kids if k not in czech]


def sitemap_czech_urls(xml: str, site_url: str) -> tuple[list[str], list[str]]:
    """Czech pages a sitemap declares for this brand: (by hreflang="cs" or a /cs/, /cs-cz/, cz. locale,
    by a /cz/ path only). Other brands' URLs are ignored."""
    brand = brand_label(site_url)
    strong: list[str] = []
    cz_only: list[str] = []
    for tag in _SM_ALT.finditer(xml):
        t = tag.group(0)
        if _SM_ALT_LANG.search(t) and (h := _SM_ALT_HREF.search(t)) and brand_label(h.group(1)) == brand:
            strong.append(h.group(1))
    for loc in _SM_LOC.findall(xml):
        if brand_label(loc) != brand:
            continue
        first = next((s for s in urlparse(loc).path.lower().split("/") if s), "")
        if (first in _CS_PATH_SEGMENTS - {"cz"} or _host(loc).startswith("cz.")) and locale_url_cs(loc):
            strong.append(loc)
        elif first == "cz" and locale_url_cs(loc):
            cz_only.append(loc)
    return strong, cz_only


def sitemap_evidence(strong: list[str], cz_only: list[str]) -> list[dict]:
    """One evidence item from the Czech URLs found in a site's sitemaps (see sitemap_czech_urls)."""
    content = [u for u in strong if not _LEGAL_PAGE.search(urlparse(u).path)]
    if content:
        return [{"signal": "sitemap_cs", "value": content[0]}]
    if strong or cz_only:
        return [{"signal": "sitemap_cs_weak", "value": (strong or cz_only)[0]}]
    return []


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
