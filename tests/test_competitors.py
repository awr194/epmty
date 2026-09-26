import importlib.util
import json
from pathlib import Path

import pytest

from cz_enrichment import Incumbent, apply_cz_defaults
from market.competitors import add_new, clean_name, extract, norm_name, same_company, threat_to_strength

ROOT = Path(__file__).resolve().parents[1]


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(ts, comps, engine="gemini-3.5-flash"):
    return {"timestamp": ts, "engine": engine, "report": {"competitors": comps}}


def _c(name, threat="High", url="", kind="Локальный игрок"):
    return {"name": name, "threat": threat, "url": url, "kind": kind, "gap": "..."}


@pytest.mark.parametrize("threat, strength", [
    ("High", 3), ("Высокая", 3), ("Medium", 2), ("Средняя", 2), ("Low", 1), ("Низкая", 1), ("", 2), ("?", 2)])
def test_threat_normalisation(threat, strength):
    assert threat_to_strength(threat) == strength


def test_names():
    assert norm_name("Choice (choice.qr)") == "choice"
    assert norm_name("OneMenu.cz") == "onemenu"
    assert clean_name("Dotykačka (модуль онлайн-заказа)") == "Dotykačka"
    assert clean_name("OneMenu.cz (Tidypay/Storyous)") == "OneMenu.cz (Tidypay/Storyous)"


def test_same_company_by_host_or_name():
    assert same_company({"name": "Choice (choice.qr)", "url": "https://choiceqr.com"},
                        {"name": "Choice QR", "url": "https://www.choiceqr.com/"})
    assert same_company({"name": "Choice QR", "url": ""}, {"name": "Choice", "url": ""})  # name prefix
    assert not same_company({"name": "Qerko", "url": ""}, {"name": "Qer", "url": ""})  # prefix too short
    assert not same_company({"name": "A group", "url": "https://facebook.com"},
                            {"name": "B group", "url": "https://facebook.com"})  # generic host


def test_extract_dedupes_newest_wins_and_skips_self_and_substitutes():
    runs = [
        _run("2026-09-26T16:41", [_c("Choice (choice.qr)", "High", "https://choiceqr.com"),
                                  _c("Dotykačka (модуль Web)", "Medium", "https://www.dotykacka.cz")]),
        _run("2026-09-26T16:43", [_c("Choice QR", "Средняя", "https://choiceqr.com"),
                                  _c("Slice", "High", "https://slicelife.com"),  # the model itself
                                  _c("FB groups", "Высокая", "https://facebook.com", kind="Заменитель")]),
    ]
    out = extract("Slice", "https://slicelife.com", runs)
    assert [(i["name"], i["strength"], i["mentions"]) for i in out] == [("Choice QR", 2, 2), ("Dotykačka", 2, 1)]
    assert all(not i["verified"] and i["source"] == "gemini-3.5-flash 2026-09-26" for i in out)


def test_generic_url_is_dropped_not_the_competitor():
    out = extract("X", "", [_run("2026-09-26", [_c("Letná parta", url="https://facebook.com/groups/1")])])
    assert out[0]["url"] == ""


def test_add_new_keeps_existing_first():
    existing = [{"name": "Reservio", "strength": 2, "url": "https://www.reservio.cz"}]
    imported = [{"name": "Reservio", "strength": 3, "url": "https://reservio.cz"}, {"name": "Bookio", "url": ""}]
    assert [i["name"] for i in add_new(existing, imported)] == ["Reservio", "Bookio"]
    assert add_new(existing, imported)[0]["strength"] == 2


def test_enrichment_adds_llm_competitors(monkeypatch):
    monkeypatch.setattr("cz_enrichment.load_llm_competitors",
                        lambda: {"M": [{"name": "SupportBox", "strength": 3, "url": "https://supportbox.cz",
                                        "source": "gemini 2026-09-26"}]})
    row = apply_cz_defaults({"name": "M"}, overlay={})
    inc = [Incumbent(**i) for i in row["local_incumbents"]]
    assert inc[0].name == "SupportBox" and not inc[0].verified and inc[0].url_usable


def test_broken_url_is_not_usable():
    assert not Incumbent(name="X", url="https://x.cz", url_status="http_404").url_usable
    assert Incumbent(name="X", url="https://x.cz", url_status="ok").url_usable


def test_import_keeps_previous_url_checks(tmp_path):
    mod = _script("import_llm_competitors")
    (tmp_path / "m.json").write_text(json.dumps({"model": "Nicereply", "runs": [
        _run("2026-09-26", [_c("SupportBox", "High", "https://www.supportbox.cz"),
                            _c("Nicereply", "High", "https://www.nicereply.com")])]}), encoding="utf-8")
    prev = {"Nicereply": [{"name": "SupportBox", "url": "https://www.supportbox.cz", "url_status": "ok",
                           "checked_at": "2026-09-20"}]}
    out = mod.build(tmp_path, {"Nicereply": "https://www.nicereply.com"}, prev)
    assert [i["name"] for i in out["Nicereply"]] == ["SupportBox"]
    assert out["Nicereply"][0]["url_status"] == "ok" and out["Nicereply"][0]["checked_at"] == "2026-09-20"


def test_verify_marks_status(monkeypatch):
    mod = _script("verify_competitors")

    class R:
        def __init__(self, code):
            self.status_code = code

        def close(self):
            pass

    monkeypatch.setattr(mod.requests, "head", lambda url, **kw: R(404 if "bad" in url else 405))
    monkeypatch.setattr(mod.requests, "get", lambda url, **kw: R(200))
    data = {"M": [{"name": "A", "url": "https://good.cz"}, {"name": "B", "url": "https://bad.cz"},
                  {"name": "C", "url": ""}]}
    assert mod.verify(data, pause=0) == 2
    assert [i.get("url_status") for i in data["M"]] == ["ok", "http_404", None]
