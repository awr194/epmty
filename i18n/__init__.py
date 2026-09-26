"""Internationalisation: Russian (default) and English.

  * t(key, **kw)   - interface strings (i18n/ui.py)
  * tr(text)       - model data (descriptions, segments, notes) via data/i18n/ru.json, keyed by the
                     English original; untranslated text falls back to the original
  * label helpers  - categories, model types, countries, MRR statuses, inferred-field names

Internal values (category keys, model types, column keys) stay English everywhere; only what is
shown to the user is translated.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from i18n.labels import CATEGORY_RU, COUNTRY_RU, FIELD_RU, MODEL_TYPE_RU, MRR_STATUS_RU
from i18n.ui import UI

DEFAULT_LANG = "ru"
LANGS = {"ru": "Русский", "en": "English"}
DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "i18n" / "ru.json"


def current_lang() -> str:
    """Language chosen in the Streamlit session; DEFAULT_LANG outside Streamlit."""
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is None:
            return DEFAULT_LANG
        return st.session_state.get("lang", DEFAULT_LANG)
    except Exception:
        return DEFAULT_LANG


def t(key: str, lang: str | None = None, **kw) -> str:
    entry = UI[key]
    text = entry.get(lang or current_lang()) or entry["en"]
    return text.format(**kw) if kw else text


@lru_cache(maxsize=1)
def _data_ru() -> dict[str, str]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.exists() else {}


def tr(text: str | None, lang: str | None = None) -> str:
    """Translate a piece of model data; unknown text is returned unchanged."""
    if not text or (lang or current_lang()) != "ru":
        return text or ""
    return _data_ru().get(text, text)


def tr_list(items: list[str], lang: str | None = None) -> list[str]:
    return [tr(x, lang) for x in items]


def _label(mapping: dict[str, str], key: str | None, lang: str | None) -> str:
    if key is None:
        return ""
    return mapping.get(key, key) if (lang or current_lang()) == "ru" else key


def cat_label(c: str, lang: str | None = None) -> str:
    return _label(CATEGORY_RU, c, lang)


def type_label(mt: str | None, lang: str | None = None) -> str:
    return _label(MODEL_TYPE_RU, mt, lang)


def country_label(c: str, lang: str | None = None) -> str:
    return _label(COUNTRY_RU, c, lang)


def mrr_status_label(status: str, lang: str | None = None) -> str:
    from scoring.metrics import MRR_STATUS_LABELS
    return MRR_STATUS_RU[status] if (lang or current_lang()) == "ru" else MRR_STATUS_LABELS[status]


def field_label(f: str, lang: str | None = None) -> str:
    return _label(FIELD_RU, f, lang)


_SAM_SOURCE_RU = [
    ("heuristic estimate (unverified)", "эвристическая оценка (не проверена)"),
    ("ČSÚ RES as of", "ČSÚ RES по состоянию на"),
    ("refreshed", "обновлено"),
    ("segment 'total'", "сегмент «все субъекты»"),
    ("segment 'with_employees'", "сегмент «с сотрудниками»"),
    ("segment 'legal_entities'", "сегмент «юрлица»"),
    ("segment 'natural_persons'", "сегмент «ИП/OSVČ»"),
]


def tr_sam_source(text: str, lang: str | None = None) -> str:
    """SAM sources are partly generated (dates, NACE codes), so translate by phrase."""
    if (lang or current_lang()) != "ru" or not text:
        return text
    if text in _data_ru():
        return _data_ru()[text]
    for en, ru in _SAM_SOURCE_RU:
        text = text.replace(en, ru)
    return re.sub(r"\bno NACE cache\b", "нет кэша NACE", text)
