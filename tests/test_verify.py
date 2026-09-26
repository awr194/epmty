import pytest

from analyzer import CzechAssumptions, CzechReport, _clamp, _clean_url, mock_report, verify_items
from cz_enrichment import Incumbent
from exporter import to_markdown, to_pdf
from analyzer import AnalysisResult

A = CzechAssumptions()


@pytest.mark.parametrize("url, expected", [
    ("https://choiceqr.com", "https://choiceqr.com"), ("https://speedlo.cz/cs", "https://speedlo.cz/cs"),
    ("https://facebook.com/groups/letna", None), ("https://www.google.com/search?q=x", None),
    ("n/a", None), ("", None), (None, None), ("www.x.cz", None), ("https://example.com", None)])
def test_clean_url(url, expected):
    assert _clean_url(url) == expected


def test_verify_items_cover_unverified_facts(make_model):
    m = make_model(sam_estimate=5_000, sam_source="ČSÚ RES as of 2026-09-15, CZ-NACE 62.01",
                   local_incumbents=[Incumbent(name="SupportBox", strength=3, source="gemini 2026-09-26"),
                                     Incumbent(name="Checked", verified=True)],
                   legal_complexity=3, required_integrations=["Pohoda", "Shoptet"], url="https://x.com",
                   original_available_in_cz="unknown")
    items = verify_items(m, A, 990)
    topics = [v.topic for v in items]
    assert topics.count("tax") == 2 and "price" in topics and "legal" in topics and "integration" in topics
    market = next(v for v in items if v.topic == "market")
    assert market.as_of == "2026-09-15"
    comps = [v.claim for v in items if v.topic == "competitor"]
    assert any("SupportBox" in c for c in comps) and not any("Checked" in c for c in comps)
    assert any("already sells in Czechia" in c for c in comps)  # original not confirmed
    assert all(v.where_to_check and "http" not in v.where_to_check for v in items)


def test_heuristic_sam_has_unknown_date(make_model):
    items = verify_items(make_model(sam_estimate=10_000, sam_source="heuristic estimate (unverified)"), A, 500)
    assert next(v for v in items if v.topic == "market").as_of == "unknown"


def test_mock_report_includes_verify_and_russian(make_model):
    r = mock_report(make_model(), A, lang="ru")
    assert r.verify_before_launch and "DPH" in r.verify_before_launch[1].claim


def test_old_stored_report_still_loads(make_model):
    data = mock_report(make_model(), A).model_dump()
    data.pop("verify_before_launch")
    for c in data["competitors"]:
        c["url"] = ""
    assert CzechReport.model_validate(data).verify_before_launch == []


def test_clamp_removes_bad_competitor_urls(make_model):
    from analyzer import LocalCompetitor
    r = mock_report(make_model(), A)
    r.competitors = [LocalCompetitor(name="FB group", kind="Substitute", url="https://facebook.com/x", threat="High",
                                     gap="-"),
                     LocalCompetitor(name="Choice", kind="Local", url="https://choiceqr.com", threat="High", gap="-")]
    assert [c.url for c in _clamp(r).competitors] == [None, "https://choiceqr.com"]


@pytest.mark.parametrize("lang, heading", [("en", "Verify before launch"), ("ru", "Проверить перед запуском")])
def test_exports_include_verify(make_model, lang, heading):
    m = make_model()
    res = AnalysisResult(mock_report(m, A, lang=lang), "mock")
    assert f"## {heading}" in to_markdown(m, res, lang)
    assert to_pdf(m, res, lang)[:4] == b"%PDF"
