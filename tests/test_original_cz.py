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


def test_check_script_offline(monkeypatch):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "check_original_cz", Path(__file__).resolve().parents[1] / "scripts" / "check_original_cz.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Resp:
        def __init__(self, url, text, status=200):
            self.url, self.text, self.status_code = url, text, status

    def fake_get(url, **kw):
        if url.endswith("/robots.txt"):
            return Resp(url, "User-agent: *\nDisallow: /private")
        if "down" in url:
            return Resp(url, "", 503)
        return Resp("https://acme.cz/", "<html lang='cs'>")

    monkeypatch.setattr(mod.requests, "get", fake_get)
    ok = mod.check("https://acme.com", {})
    assert ok["status"] == "yes" and ok["http_status"] == 200 and {"redirect_cz", "html_lang_cs"} <= _codes(
        ok["evidence"])
    assert mod.check("https://acme.com/private", {})["error"] == "robots_disallow"
    assert mod.check("https://down.com", {})["error"] == "http_503"
    assert mod.check("", {})["status"] == "unknown"
