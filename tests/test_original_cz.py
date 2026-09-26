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
