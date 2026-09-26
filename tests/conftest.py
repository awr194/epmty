import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_loader import BusinessModel  # noqa: E402


@pytest.fixture
def make_model():
    """Build a minimal BusinessModel; keyword arguments override defaults."""
    def _make(**kw) -> BusinessModel:
        base = dict(id="t", name="Test model", url="", category="Dev & Productivity Tools", niche="n",
                    revenue_model="Subscription SaaS", problem="p", price_usd=20, cz_sam=10_000,
                    demand=3, competition=3, complexity=3, regulatory=1, moat=3, model_type="saas")
        base.update(kw)
        return BusinessModel(**base)
    return _make
