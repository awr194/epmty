import subprocess
import sys
from pathlib import Path

from analyzer import CzechAssumptions, analyze
from i18n import t, tr, tr_sam_source
from i18n.labels import CATEGORY_RU, COUNTRY_RU
from i18n.ui import UI

ROOT = Path(__file__).resolve().parents[1]


def test_every_ui_string_has_both_languages():
    missing = [k for k, v in UI.items() if not v.get("ru") or not v.get("en")]
    assert missing == []


def test_ui_placeholders_match_between_languages():
    import string
    fields = lambda s: {f for _, f, _, _ in string.Formatter().parse(s) if f}  # noqa: E731
    mismatched = [k for k, v in UI.items() if fields(v["ru"]) != fields(v["en"])]
    assert mismatched == []


def test_all_model_data_is_translated():
    """Fails when new models/strings are added: run scripts/i18n_extract.py and translate todo_ru.json."""
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "i18n_extract.py"), "--check"],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout


def test_every_category_and_country_has_a_russian_label():
    from data_loader import CATEGORIES, load_curated
    assert set(CATEGORIES) <= set(CATEGORY_RU)
    assert {m.country for m in load_curated()} <= set(COUNTRY_RU)


def test_tr_handles_generated_note_suffixes():
    assert tr("Czech CRM - strength to verify", "ru") == "Чешская CRM — силу проверить"
    assert tr("Something unknown", "ru") == "Something unknown"
    assert tr("Czech CRM", "en") == "Czech CRM"


def test_t_formats_placeholders():
    assert t("showing", "ru", a=1, b=24, n=500) == "Показаны 1–24 из 500"
    assert t("showing", "en", a=1, b=24, n=500) == "Showing 1-24 of 500 models"


def test_sam_source_translation():
    assert tr_sam_source("heuristic estimate (unverified)", "ru") == "эвристическая оценка (не проверена)"


def test_offline_report_in_russian_contains_no_english_template_text(make_model):
    r = analyze(make_model(), CzechAssumptions(), engine="mock", lang="ru").report
    assert r.verdict.startswith(("Сильный", "Перспективно", "Рискованно", "Слабо"))
    assert r.gtm_plan[0].title == "Проверить спрос и собрать MVP для Чехии"
    assert all("Czech" not in step.title for step in r.gtm_plan)
