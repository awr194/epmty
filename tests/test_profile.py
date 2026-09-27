from scoring.profile import FounderProfile


def test_rejections(make_model):
    p = FounderProfile()
    assert p.rejection(make_model(complexity=3), 990) is None
    assert p.rejection(make_model(complexity=4), 990)[0] == "build"
    assert p.rejection(make_model(model_type="d2c_physical"), 990)[0] == "type"
    assert p.rejection(make_model(regulatory=4, legal_complexity=None), 990)[0] == "legal"
    assert p.rejection(make_model(needs_rethink_for_cz=True), 990)[0] == "rethink"
    assert p.rejection(make_model(), 99)[0] == "customers"  # 45 000 / 99 = 455 > 300


def test_goal_and_weights():
    p = FounderProfile()
    assert p.target_mrr_czk == 45_000 and p.customers_for_goal(990) == 46
    assert p.weights().solo_founder is False  # native Czech: no language penalty
    assert FounderProfile(native_czech=False).weights().solo_founder is True


def test_shortlist_script_runs(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "shortlist", Path(__file__).resolve().parents[1] / "scripts" / "shortlist.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rows, rejected = mod.build()
    assert rows and all(r["customers"] <= 300 for r in rows)
    assert [r["score"] for r in rows] == sorted((r["score"] for r in rows), reverse=True)
    md = mod.to_markdown(rows, rejected, len(rows) + sum(rejected.values()), mod.OWNER_PROFILE, 5)
    assert md.count("\n| ") >= 6 and "45 000 CZK MRR" in md
