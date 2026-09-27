import pytest

from analyzer import CzechAssumptions
from cz_enrichment import Incumbent, Seasonality
from scoring.config import CzechScoreWeights
from scoring.czech import czech_adjusted_score
from scoring.metrics import DerivedMetrics, derived_metrics

A = CzechAssumptions()
NO_SUPPORT = CzechScoreWeights(solo_founder=False)


def _metrics(customers=None, sam_share=None, comparable=True):
    return DerivedMetrics(price_czk=500, mrr_heuristic_czk=50_000, mrr_czk_m12=50_000 if comparable else None,
                          mrr_status="comparable" if comparable else "marketplace_no_gmv",
                          customers_needed=customers, sam_share_12m=sam_share)


def _factors(result):
    return {a.factor: a.points for a in result.breakdown}


# ------------------------------------------------------------------ edge cases from the spec

def test_clean_model_keeps_base_score(make_model):
    m = make_model(czech_support_required=False)
    r = czech_adjusted_score(60, m, _metrics(100, 0.01))
    assert r.score == 60 and r.breakdown == [] and r.delta == 0


def test_no_sam_skips_market_share_penalty_and_says_so(make_model):
    m = make_model(czech_support_required=False)
    r = czech_adjusted_score(60, m, _metrics(customers=100, sam_share=None))
    assert "Share of market needed" not in _factors(r)
    assert any("No SAM estimate" in rec for rec in r.recommendations)


def test_no_competitors_means_no_incumbent_penalty(make_model):
    r = czech_adjusted_score(60, make_model(local_incumbents=[]), _metrics(), NO_SUPPORT)
    assert "Local incumbents" not in _factors(r)


def test_marketplace_without_gmv_is_scored_but_flagged(make_model):
    m = make_model(model_type="marketplace", czech_support_required=False)
    d = derived_metrics(m, A)
    r = czech_adjusted_score(55, m, d)
    assert r.score == 55  # no share penalty possible without customers_needed
    assert any("not comparable" in rec for rec in r.recommendations)


# ------------------------------------------------------------------ individual factors

def test_incumbent_penalty_scales_with_strength_and_is_capped(make_model):
    w = CzechScoreWeights(incumbent_points_per_strength=4, incumbent_cap=25, solo_founder=False)
    weak = make_model(local_incumbents=[Incumbent(name="A", strength=1)])
    strong = make_model(local_incumbents=[Incumbent(name="A", strength=3), Incumbent(name="B", strength=3)])
    many = make_model(local_incumbents=[Incumbent(name=str(i), strength=3) for i in range(5)])
    assert _factors(czech_adjusted_score(60, weak, _metrics(), w))["Local incumbents"] == -4
    assert _factors(czech_adjusted_score(60, strong, _metrics(), w))["Local incumbents"] == -24
    assert _factors(czech_adjusted_score(60, many, _metrics(), w))["Local incumbents"] == -25


OFFICIAL_SAM = "ČSÚ RES as of 2026-09-15, CZ-NACE 62.01"


@pytest.mark.parametrize("share, expected", [
    (0.019, 0.0),     # below the soft threshold
    (0.02, 0.0),      # at the soft threshold: no penalty
    (0.024, -3.4),    # just above it: the step (3) plus a small linear part (8 x 0.4/8)
    (0.06, -7.0),     # step + halfway between soft and hard
    (0.10, -11.0),    # at the hard threshold: step + full soft penalty
    (0.15, -21.0),    # steep beyond hard
    (0.50, -31.0),    # capped at step + soft + hard penalty
])
def test_sam_share_penalty_curve(make_model, share, expected):
    m = make_model(czech_support_required=False, sam_source=OFFICIAL_SAM)
    r = czech_adjusted_score(60, m, _metrics(1_000, share))
    assert _factors(r).get("Share of market needed", 0.0) == pytest.approx(expected)


def test_crossing_the_threshold_is_a_visible_jump(make_model):
    m = make_model(czech_support_required=False, sam_source=OFFICIAL_SAM)
    at = czech_adjusted_score(60, m, _metrics(1_000, 0.020)).score
    above = czech_adjusted_score(60, m, _metrics(1_000, 0.0201)).score
    assert at - above >= 3


def test_heuristic_sam_scales_share_penalty(make_model):
    w = CzechScoreWeights(heuristic_sam_confidence=0.5, solo_founder=False)
    official = make_model(sam_source=OFFICIAL_SAM)
    heuristic = make_model(sam_source="heuristic estimate (unverified)")
    r_off = czech_adjusted_score(60, official, _metrics(1_000, 0.10), w)
    r_heur = czech_adjusted_score(60, heuristic, _metrics(1_000, 0.10), w)
    assert _factors(r_off)["Share of market needed"] == pytest.approx(-11.0)
    assert _factors(r_heur)["Share of market needed"] == pytest.approx(-5.5)
    assert "heuristic SAM" in r_heur.breakdown[0].detail
    ru = czech_adjusted_score(60, heuristic, _metrics(1_000, 0.10), w, lang="ru")
    assert "×0,5" in ru.breakdown[0].detail


def test_legal_complexity_falls_back_to_regulatory(make_model):
    explicit = make_model(legal_complexity=4, regulatory=1)
    fallback = make_model(legal_complexity=None, regulatory=3)
    assert _factors(czech_adjusted_score(60, explicit, _metrics(), NO_SUPPORT))["Legal complexity"] == -9
    assert _factors(czech_adjusted_score(60, fallback, _metrics(), NO_SUPPORT))["Legal complexity"] == -6


def test_only_complex_integrations_count(make_model):
    m = make_model(required_integrations=["Pohoda", "QR platba", "ABRA", "Shoptet"])
    assert _factors(czech_adjusted_score(60, m, _metrics(), NO_SUPPORT))["Complex integrations"] == -6


def test_czech_support_penalty_only_for_solo_founder(make_model):
    m = make_model(czech_support_required=True, audience="B2C")
    assert "Czech-language support" in _factors(czech_adjusted_score(60, m, _metrics()))
    assert "Czech-language support" not in _factors(czech_adjusted_score(60, m, _metrics(), NO_SUPPORT))


@pytest.mark.parametrize("audience, category, expected", [
    ("B2C", "Dev & Productivity Tools", -3.0),        # consumers: full
    ("B2B", "Hospitality & Gastro", -3.0),            # local SMB owners: full
    ("B2B", "Dev & Productivity Tools", -1.0),        # technical B2B: reduced
])
def test_czech_support_penalty_depends_on_segment(make_model, audience, category, expected):
    m = make_model(czech_support_required=True, audience=audience, category=category)
    assert _factors(czech_adjusted_score(60, m, _metrics()))["Czech-language support"] == expected


def test_other_b2b_support_penalty_can_be_switched_off(make_model):
    m = make_model(czech_support_required=True, audience="B2B")
    w = CzechScoreWeights(czech_support_penalty_other_b2b=0.0)
    assert "Czech-language support" not in _factors(czech_adjusted_score(60, m, _metrics(), w))


def test_seasonality_recommends_launch_month_without_penalty(make_model):
    m = make_model(czech_support_required=False, seasonality=Seasonality(peak_months=[5, 6, 7, 8, 9]))
    r = czech_adjusted_score(60, m, _metrics())
    assert r.score == 60
    assert any("launch by March" in rec for rec in r.recommendations)


def test_seasonality_across_new_year(make_model):
    m = make_model(czech_support_required=False, seasonality=Seasonality(peak_months=[11, 12, 1]))
    r = czech_adjusted_score(60, m, _metrics())
    assert any("launch by September" in rec for rec in r.recommendations)


def test_score_is_clamped_to_zero(make_model):
    m = make_model(legal_complexity=5, local_incumbents=[Incumbent(name=str(i), strength=3) for i in range(5)],
                   required_integrations=["Pohoda", "ABRA", "Money S3", "Bank iD"], czech_support_required=True)
    r = czech_adjusted_score(20, m, _metrics(1_000, 0.5))
    assert r.score == 0


def test_breakdown_sums_to_the_delta_when_not_clamped(make_model):
    m = make_model(legal_complexity=3, local_incumbents=[Incumbent(name="A", strength=2)], czech_support_required=True)
    r = czech_adjusted_score(80, m, _metrics(1_000, 0.06))
    assert r.score == round(80 + sum(a.points for a in r.breakdown))


@pytest.mark.parametrize("model_type, penalised", [
    ("d2c_physical", True), ("offline_retail", True), ("service", True), ("saas", False), ("marketplace", False)])
def test_non_software_revenue_penalty(make_model, model_type, penalised):
    m = make_model(model_type=model_type, czech_support_required=False)
    f = _factors(czech_adjusted_score(60, m, _metrics()))
    assert (f.get("Non-software revenue") == -10) if penalised else ("Non-software revenue" not in f)


def test_calibrated_incumbent_defaults(make_model):
    many = make_model(czech_support_required=False,
                      local_incumbents=[Incumbent(name=str(i), strength=3) for i in range(5)])
    assert _factors(czech_adjusted_score(60, many, _metrics()))["Local incumbents"] == -10
