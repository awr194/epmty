import pytest

from cz_enrichment import apply_cz_defaults
from market.original_cz import brand_label, classify, detect_signals
from scoring.czech import czech_adjusted_score
from tests.test_czech_score import NO_SUPPORT, _factors, _metrics


def _codes(ev):
    return {e["signal"] for e in ev}


def test_hreflang_and_lang_picker_are_strong():
    html = '<html lang="en"><link rel="alternate" hreflang="cs" href="https://x.com/cs/"><a>Čeština</a>'
    ev = detect_signals("https://x.com", html)
    assert _codes(ev) == {"hreflang_cs", "lang_picker_cs"}
    assert classify(ev) == "yes"


def test_redirect_to_cz_domain():
    ev = detect_signals("https://www.twinkl.com", "<html lang='cs-CZ'>", final_url="https://www.twinkl.cz/")
    assert {"redirect_cz", "html_lang_cs"} <= _codes(ev)


def test_link_to_own_cz_domain_only():
    own = detect_signals("https://www.acme.com", '<a href="https://acme.cz/">CZ</a>')
    other = detect_signals("https://www.acme.com", '<a href="https://seznam.cz/">partner</a>')
    assert _codes(own) == {"link_cz_domain"}
    assert other == []


def test_czk_price_alone_is_only_likely():
    ev = detect_signals("https://x.com", "<p>od 1 290 Kč měsíčně</p>")
    assert _codes(ev) == {"price_czk"} and classify(ev) == "likely"


@pytest.mark.parametrize("html", [
    "<html lang='en'><select><option>Czech Republic</option></select>",  # country list: ignored
    "<html lang='csb'>",                                                 # not Czech
    "",
])
def test_no_signal_is_unknown_never_no(html):
    ev = detect_signals("https://x.com", html)
    assert ev == [] and classify(ev) == "unknown"


def test_brand_label():
    assert brand_label("https://www.getjobber.com/pricing") == "getjobber"
    assert brand_label("https://shop.example.co.uk") == "example"


def test_overlay_beats_site_check(monkeypatch):
    monkeypatch.setattr("cz_enrichment.load_original_cz",
                        lambda: {"M": {"status": "yes", "evidence": [{"signal": "hreflang_cs", "value": "x"}],
                                       "checked_at": "2026-09-26"}})
    checked = apply_cz_defaults({"name": "M"}, overlay={})
    assert checked["original_available_in_cz"] == "yes" and checked["original_cz_source"] == "site check 2026-09-26"
    manual = apply_cz_defaults({"name": "M"}, overlay={"M": {"original_available_in_cz": "no",
                                                             "original_cz_source": "support email 2026-09"}})
    assert manual["original_available_in_cz"] == "no" and manual["original_cz_evidence"] == []


def test_not_checked_stays_unknown(make_model):
    assert make_model().original_available_in_cz == "unknown"


def test_original_in_cz_penalty_and_likely_recommendation(make_model):
    yes = make_model(original_available_in_cz="yes", original_cz_evidence=[{"signal": "hreflang_cs",
                                                                            "value": 'hreflang="cs"'}])
    likely = make_model(original_available_in_cz="likely", original_cz_evidence=[{"signal": "price_czk",
                                                                                  "value": "290 Kč"}])
    r_yes = czech_adjusted_score(60, yes, _metrics(), NO_SUPPORT)
    r_likely = czech_adjusted_score(60, likely, _metrics(), NO_SUPPORT)
    assert _factors(r_yes)["Original already in Czechia"] == -6
    assert r_likely.score == 60 and any("290 Kč" in rec for rec in r_likely.recommendations)


def test_og_locale_and_link_header():
    ev = detect_signals("https://x.com", '<meta property="og:locale:alternate" content="cs_CZ">')
    assert _codes(ev) == {"og_locale_cs"} and classify(ev) == "yes"
    ev = detect_signals("https://x.com", "", link_header='<https://x.com/cs/>; rel="alternate"; hreflang="cs"')
    assert _codes(ev) == {"hreflang_cs"}
    assert _codes(detect_signals("https://x.com", '<link rel="alternate" hreflang="cs_CZ" href="/cs">')) == {
        "hreflang_cs"}


def test_check_script_offline(monkeypatch):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "check_original_cz", Path(__file__).resolve().parents[1] / "scripts" / "check_original_cz.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Resp:
        def __init__(self, url, text, status=200, headers=None):
            self.url, self.text, self.status_code, self.headers = url, text, status, headers or {}

    def fake_get(url, **kw):
        if url.endswith("/robots.txt"):
            return Resp(url, "User-agent: *\nDisallow: /private")
        if "down" in url:
            return Resp(url, "", 503)
        if "soft404.com" in url:  # answers 200 on every path, English page
            return Resp(url, "<html lang='en'>")
        if "withcs.com/cs" in url:
            return Resp(url, "<html lang='cs'>")
        if "redirects.com/cs" in url:  # /cs/ bounces to the English home page
            return Resp("https://redirects.com/", "<html lang='cs'>")
        if "withcs.com" in url or "redirects.com" in url:
            return Resp(url, "<html lang='en'>")
        return Resp("https://acme.cz/", "<html lang='cs'>")

    monkeypatch.setattr(mod.requests, "get", fake_get)
    monkeypatch.setattr(mod, "PAUSE_S", 0)
    ok = mod.check("https://acme.com", {})
    assert ok["status"] == "yes" and ok["http_status"] == 200 and {"redirect_cz", "html_lang_cs"} <= _codes(
        ok["evidence"])
    assert mod.check("https://acme.com/private", {})["error"] == "robots_disallow"
    assert mod.check("https://down.com", {})["error"] == "http_503"
    assert mod.check("", {})["status"] == "unknown"
    probed = mod.check("https://withcs.com", {})
    assert probed["status"] == "yes" and probed["evidence"][0]["signal"] == "cs_path"
    assert mod.check("https://soft404.com", {})["status"] == "unknown"
    assert mod.check("https://redirects.com", {})["status"] == "unknown"


def test_price_regex_is_linear_on_hostile_pages():
    import time
    for html in ("1 " * 200_000, "1,2,3.4 " * 200_000, "1" + " " * 1_000_000 + "x", "7" * 1_000_000):
        t = time.perf_counter()
        detect_signals("https://x.com", html)
        assert time.perf_counter() - t < 2.0


@pytest.mark.parametrize("text, value", [
    ("od 1 290 Kč měsíčně", "1 290 Kč"), ("1 290,50 CZK", "1 290,50 CZK"), ("CZK 499", "CZK 499")])
def test_price_formats(text, value):
    assert detect_signals("https://x.com", text) == [{"signal": "price_czk", "value": value}]


def test_price_is_case_sensitive():
    assert detect_signals("https://x.com", "var a='czk58';b='4CZk'") == []


@pytest.mark.parametrize("final, expected", [
    ("https://cz.huel.com/", True), ("https://www.fresha.com/cs", True), ("https://base.com/cs-CZ/home/", True),
    ("https://www.creditsafe.com/cs/en.html", False),  # an English page under /cs/
    ("https://www.domestika.org/en", False), ("https://x.com/cosmetics", False)])
def test_locale_url(final, expected):
    from market.original_cz import locale_url_cs
    assert locale_url_cs(final) is expected


def test_reclassify_offline():
    from market.original_cz import reclassify
    junk = {"url": "https://k.com", "final_url": "https://k.com/", "status": "likely",
            "evidence": [{"signal": "price_czk", "value": "czk58"}]}
    huel = {"url": "https://huel.com", "final_url": "https://cz.huel.com/", "status": "likely",
            "evidence": [{"signal": "price_czk", "value": "1 370 Kč"}]}
    blocked = {"url": "https://e.com", "status": "unknown", "evidence": [], "error": "http_403"}
    assert reclassify(junk)["status"] == "unknown"
    assert reclassify(huel)["status"] == "yes" and {e["signal"] for e in reclassify(huel)["evidence"]} == {
        "price_czk", "locale_url_cs"}
    assert reclassify(blocked)["status"] == "unknown"


# --- sitemaps, Google Translate, SSL / 429 / Wayback (2026-09-28) ---

def _load_script():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "check_original_cz", Path(__file__).resolve().parents[1] / "scripts" / "check_original_cz.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Resp:
    def __init__(self, url, text="", status=200, headers=None, json_data=None):
        self.url, self.text, self.status_code, self.headers = url, text, status, headers or {}
        self.content, self._json = text.encode(), json_data

    def json(self):
        return self._json


def test_google_translate_lowercase_cestina_is_not_a_picker():
    widget = '<select class="goog-te-combo"><option value="cs">čeština</option></select>'
    assert detect_signals("https://x.com", widget) == []


def test_sitemap_hreflang_and_cs_path_are_strong():
    from market.original_cz import sitemap_czech_urls, sitemap_evidence
    xml = ('<urlset><url><loc>https://x.com/en/pricing</loc>'
           '<xhtml:link rel="alternate" hreflang="cs-CZ" href="https://x.com/cs/cenik"/></url>'
           '<url><loc>https://x.com/cs-cz/blog</loc></url><url><loc>https://other.com/cs/</loc></url></urlset>')
    strong, cz_only = sitemap_czech_urls(xml, "https://www.x.com")
    assert strong == ["https://x.com/cs/cenik", "https://x.com/cs-cz/blog"] and cz_only == []
    ev = sitemap_evidence(strong, cz_only)
    assert ev == [{"signal": "sitemap_cs", "value": "https://x.com/cs/cenik"}] and classify(ev) == "yes"


@pytest.mark.parametrize("xml", [
    # BetterMe: only the privacy policy is translated
    '<urlset><url><loc>https://betterme.world/cs/privacy-policy</loc></url></urlset>',
    # a /cz/ page, which can be an English country page
    '<urlset><url><loc>https://x.com/cz/</loc></url></urlset>'])
def test_sitemap_legal_only_or_cz_path_is_weak(xml):
    from market.original_cz import sitemap_czech_urls, sitemap_evidence
    site = "https://betterme.world" if "betterme" in xml else "https://x.com"
    ev = sitemap_evidence(*sitemap_czech_urls(xml, site))
    assert [e["signal"] for e in ev] == ["sitemap_cs_weak"] and classify(ev) == "likely"


def test_sitemap_country_data_path_is_ignored():
    from market.original_cz import sitemap_czech_urls
    xml = "<urlset><url><loc>https://www.airdna.co/vacation-rental-data/app/cz/default/prague/overview</loc></url>"
    assert sitemap_czech_urls(xml, "https://www.airdna.co") == ([], [])


def test_sitemap_index_czech_children_first():
    from market.original_cz import sitemap_children
    xml = ("<sitemapindex><sitemap><loc>https://x.com/sitemap-en.xml</loc></sitemap>"
           "<sitemap><loc>https://x.com/sitemap-cs.xml</loc></sitemap></sitemapindex>")
    assert sitemap_children(xml) == ["https://x.com/sitemap-cs.xml", "https://x.com/sitemap-en.xml"]
    assert sitemap_children("<urlset></urlset>") == []


def test_script_reads_sitemap_from_robots(monkeypatch):
    mod = _load_script()
    pages = {
        "https://s.com/robots.txt": "User-agent: *\nDisallow: /private\nSitemap: https://s.com/sm-index.xml",
        "https://s.com/sm-index.xml": "<sitemapindex><sitemap><loc>https://s.com/sm-cs.xml</loc></sitemap>"
                                      "</sitemapindex>",
        "https://s.com/sm-cs.xml": "<urlset><url><loc>https://s.com/cs/</loc></url></urlset>",
        "https://s.com": "<html lang='en'>",
    }
    monkeypatch.setattr(mod.requests, "get", lambda url, **kw: _Resp(url, pages.get(url, ""), 200 if url in pages
                                                                        else 404))
    monkeypatch.setattr(mod, "PAUSE_S", 0)
    res = mod.check("https://s.com", {})
    assert res["status"] == "yes" and res["evidence"] == [{"signal": "sitemap_cs", "value": "https://s.com/cs/"}]


def test_www_variant():
    mod = _load_script()
    assert mod._www_variant("https://www.a.de/x") == "https://a.de/x"
    assert mod._www_variant("https://a.co.il") == "https://www.a.co.il"


def test_ssl_error_retries_other_name_once(monkeypatch):
    mod = _load_script()
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        if url.endswith("robots.txt"):
            return _Resp(url, "")
        if url.startswith("https://www."):
            raise mod.requests.exceptions.SSLError("hostname mismatch")
        return _Resp(url, "<html lang='cs'>")

    monkeypatch.setattr(mod.requests, "get", fake_get)
    res = mod.check("https://www.shop.de", {})
    assert res["status"] == "yes" and res["tried_url"] == "https://shop.de"


def test_429_is_retried_after_retry_after(monkeypatch):
    mod = _load_script()
    seen, slept = [], []

    def fake_get(url, **kw):
        if url.endswith("robots.txt"):
            return _Resp(url, "")
        seen.append(url)
        return _Resp(url, "<html lang='cs'>") if len(seen) > 1 else _Resp(url, "", 429, {"Retry-After": "7"})

    monkeypatch.setattr(mod.requests, "get", fake_get)
    monkeypatch.setattr(mod.time, "sleep", slept.append)
    assert mod.check("https://busy.com", {})["status"] == "yes" and 7 in slept


def test_403_falls_back_to_dated_wayback_copy(monkeypatch):
    mod = _load_script()

    def fake_get(url, params=None, **kw):
        if url.endswith("robots.txt"):
            return _Resp(url, "")
        if url == mod.WAYBACK_AVAILABLE:
            return _Resp(url, json_data={"archived_snapshots": {"closest": {
                "available": True, "status": "200", "timestamp": "20260901120000"}}})
        if url.startswith("https://web.archive.org/web/20260901120000id_/"):
            return _Resp(url, '<link rel="alternate" hreflang="cs" href="https://guard.com/cs/">')
        return _Resp(url, "", 403)

    monkeypatch.setattr(mod.requests, "get", fake_get)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    res = mod.check("https://guard.com", {})
    assert res["status"] == "yes" and res["via"] == "wayback" and res["archived_at"] == "2026-09-01"
    assert res["live_error"] == "http_403" and "error" not in res
    from market.original_cz import reclassify
    assert reclassify(res)["status"] == "yes"
    assert mod.check("https://guard.com", {}, wayback=False)["error"] == "http_403"


def test_wayback_source_label(monkeypatch):
    monkeypatch.setattr("cz_enrichment.load_original_cz",
                        lambda: {"W": {"status": "yes", "evidence": [], "via": "wayback", "archived_at": "2026-09-01"}})
    assert "archive copy 2026-09-01" in apply_cz_defaults({"name": "W"}, overlay={})["original_cz_source"]
