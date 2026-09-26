from analyzer import AnalysisResult, CzechAssumptions, mock_report
from report_store import latest, save


def test_llm_runs_are_stored_and_latest_is_returned(tmp_path, make_model):
    m = make_model()
    report = mock_report(m, CzechAssumptions())
    save(m.id, m.name, AnalysisResult(report, "gemini-2.5-flash"), store_dir=tmp_path)
    report.confidence = "high"
    save(m.id, m.name, AnalysisResult(report, "claude-opus-5"), store_dir=tmp_path)
    run = latest(m.id, store_dir=tmp_path)
    assert run["engine"] == "claude-opus-5" and run["report"].confidence == "high"


def test_offline_reports_are_not_stored(tmp_path, make_model):
    m = make_model()
    assert save(m.id, m.name, AnalysisResult(mock_report(m, CzechAssumptions()), "mock"), store_dir=tmp_path) is None
    assert latest(m.id, store_dir=tmp_path) is None
