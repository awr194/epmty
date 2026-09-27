import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("run_llm_batch", ROOT / "scripts" / "run_llm_batch.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sample_is_stratified_and_deterministic():
    mod = _mod()
    from analyzer import CzechAssumptions
    from data_loader import load_curated
    models = load_curated()
    scores = mod.rule_scores(models, CzechAssumptions())
    s1, s2 = mod.stratified_sample(models, scores), mod.stratified_sample(models, scores)
    assert s1 == s2 and len(set(s1)) == len(s1)
    by = {m.name: m for m in models}
    assert {by[n].category for n in s1} == {m.category for m in models}
    assert {by[n].model_type for n in s1} == {m.model_type for m in models}
    assert all(n in s1 for n in mod.ALWAYS)


def test_batch_resumes_skips_failures_and_stops_on_quota(tmp_path, monkeypatch):
    mod = _mod()
    import report_store
    from analyzer import AnalysisResult, CzechAssumptions, mock_report
    monkeypatch.setattr(report_store, "STORE_DIR", tmp_path / "reports")
    monkeypatch.setattr(mod, "SAMPLE_PATH", tmp_path / "sample.json")
    monkeypatch.setattr(mod, "SUMMARY_PATH", tmp_path / "summary.md")
    monkeypatch.setattr(mod, "ERROR_LOG", tmp_path / "errors.log")
    (tmp_path / "sample.json").write_text(json.dumps({"models": ["Slice", "Nicereply", "6AM City"]}))
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    calls = []

    def fake_analyze(m, a, engine, gemini_model, czech_context, lang):
        calls.append(m.name)
        if m.name == "Nicereply":  # a failing call: analyze falls back to the heuristic
            return AnalysisResult(mock_report(m, a), "mock", ["Gemini analysis failed (boom)"])
        if m.name == "6AM City":
            return AnalysisResult(mock_report(m, a), "mock", ["Gemini rate limit / free-tier quota hit"])
        return AnalysisResult(mock_report(m, a), gemini_model)

    monkeypatch.setattr(mod, "analyze", fake_analyze)
    monkeypatch.setattr(mod, "RETRY_WAITS", (0, 0))
    monkeypatch.setattr(sys, "argv", ["x", "--model", "g-test", "--runs", "2", "--pause", "0"])
    mod.main()
    assert calls == ["Slice", "Slice", "Nicereply", "6AM City", "6AM City", "6AM City"]  # quota: 2 retries
    slice_id = next(m.id for m in __import__("data_loader").load_curated() if m.name == "Slice")
    assert len(mod.runs_with(slice_id, "g-test")) == 2
    calls.clear()
    mod.main()  # resume: Slice already has 2 runs
    assert calls[0] == "Nicereply"
    assert "| Slice |" in (tmp_path / "summary_g-test.md").read_text()
    log = (tmp_path / "errors.log").read_text()
    assert "Nicereply\tGemini analysis failed (boom)" in log and "6AM City" in log


def test_retry_recovers_from_a_per_minute_limit():
    mod = _mod()
    from analyzer import AnalysisResult, CzechAssumptions, mock_report
    from data_loader import load_curated
    m = load_curated()[0]
    ok = AnalysisResult(mock_report(m, CzechAssumptions()), "g-test")
    limited = AnalysisResult(ok.report, "mock", ["Gemini rate limit / free-tier quota hit - try again later"])
    answers = iter([limited, ok])
    waits = []
    res, n, verdict = mod.call_with_retry(lambda: next(answers), sleep=waits.append)
    assert verdict == "ok" and n == 2 and waits == [65]
