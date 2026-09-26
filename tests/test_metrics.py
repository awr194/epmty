from analyzer import CzechAssumptions
from scoring.metrics import (COMPARABLE, MARKETPLACE_GMV, MARKETPLACE_NO_GMV, NOT_RECURRING, derived_metrics)

A = CzechAssumptions()


def test_saas_customers_needed_is_mrr_over_price(make_model):
    d = derived_metrics(make_model(), A)
    assert d.mrr_status == COMPARABLE
    assert d.customers_needed == round(d.mrr_czk_m12 / d.price_czk)


def test_sam_share_uses_sam_estimate(make_model):
    d = derived_metrics(make_model(sam_estimate=1_000), A)
    assert d.sam_share_12m == d.customers_needed / 1_000


def test_no_sam_means_no_share(make_model):
    d = derived_metrics(make_model(sam_estimate=None), A)
    assert d.sam_share_12m is None
    assert d.customers_needed is not None


def test_marketplace_without_gmv_is_not_comparable(make_model):
    d = derived_metrics(make_model(model_type="marketplace"), A)
    assert d.mrr_status == MARKETPLACE_NO_GMV
    assert d.mrr_czk_m12 is None and d.customers_needed is None and d.sam_share_12m is None
    assert d.mrr_heuristic_czk > 0  # the base figure stays available for reference


def test_marketplace_mrr_is_take_rate_times_gmv(make_model):
    d = derived_metrics(make_model(model_type="marketplace", take_rate=0.15, gmv_estimate=400_000), A)
    assert d.mrr_status == MARKETPLACE_GMV
    assert d.mrr_czk_m12 == 60_000


def test_physical_and_retail_are_not_recurring(make_model):
    for t in ("d2c_physical", "offline_retail"):
        d = derived_metrics(make_model(model_type=t), A)
        assert d.mrr_status == NOT_RECURRING and d.mrr_czk_m12 is None


def test_missing_model_type_defaults_to_saas(make_model):
    assert derived_metrics(make_model(model_type=None), A).mrr_status == COMPARABLE
