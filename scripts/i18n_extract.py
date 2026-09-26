"""Collect model-data strings that still need a Russian translation.

    python scripts/i18n_extract.py            # -> data/i18n/todo_ru.json (untranslated strings by field)
    python scripts/i18n_extract.py --check    # exit 1 if anything is untranslated (used by tests)

Translations live in data/i18n/ru.json as {"English original": "Russian"}. Proper names (companies,
products) are not extracted; descriptive competitor names ("Local photographers") are.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_loader import _CATEGORY_DEFAULT_SEGMENTS, load_curated  # noqa: E402
from i18n import _STANDALONE_RU, split_note_suffix  # noqa: E402

RU_PATH = ROOT / "data" / "i18n" / "ru.json"
TODO_PATH = ROOT / "data" / "i18n" / "todo_ru.json"

# Strings produced outside the curated records (live feeds, forms).
EXTRA = ["Auto-classified from a live feed - run a Deep-Dive for a proper assessment.", "Live launch signal",
         "Unknown (early-stage launch)", "Newly launched product", "See product page."]


def _descriptive(name: str) -> bool:
    """True for generic competitor descriptions, False for proper names."""
    words = re.findall(r"[A-Za-z][a-z]{3,}", name)
    return any(w[0].islower() for w in words)


# Descriptive (non-brand) model names that are not caught by the "archetype" rule.
DESCRIPTIVE_MODEL_NAMES = {
    "AI Multilingual Menu & Allergen Labels", "Meal-Prep Subscription (krabičková dieta)",
    "Web Accessibility Checker (EAA compliance)", "Driving School Management & Theory App",
    "Mobile Car Detailing Booking", "Craft Beer Subscription Box", "Czech for Foreigners: Exam-prep Marketplace",
    "Marketplace fulfilment operator (Wildberries/Ozon sellers)", "Kukhnya na Rayone (Кухня на районе)",
}


def _descriptive_model_name(name: str) -> bool:
    return "archetype" in name.lower() or name in DESCRIPTIVE_MODEL_NAMES


def collect() -> dict[str, set[str]]:
    fields: dict[str, set[str]] = {k: set() for k in (
        "niche", "problem", "revenue_model", "revenue_note", "cz_notes", "segments", "competitor_notes",
        "competitor_names", "model_names", "other")}
    for m in load_curated():
        if _descriptive_model_name(m.name):
            fields["model_names"].add(m.name)
        fields["niche"].add(m.niche)
        fields["problem"].add(m.problem)
        fields["revenue_model"].add(m.revenue_model)
        fields["revenue_note"].add(m.revenue_note)
        if m.cz_notes:
            fields["cz_notes"].add(m.cz_notes)
        fields["segments"].update(m.cz_segments)
        for c in [*m.cz_competitors, *m.local_incumbents]:
            if c.note:
                base, _ = split_note_suffix(c.note)  # generated suffixes are translated by rule
                if base not in _STANDALONE_RU:
                    fields["competitor_notes"].add(base)
            if _descriptive(c.name):
                fields["competitor_names"].add(c.name)
    for segs in _CATEGORY_DEFAULT_SEGMENTS.values():
        fields["segments"].update(segs)
    # Segments proposed by the reviewed data patch, so they are translated before it is applied.
    patch = ROOT / "patches" / "data_fixes.json"
    if patch.exists():
        for fix in json.loads(patch.read_text(encoding="utf-8"))["fixes"]:
            if fix["field"] == "cz_segments":
                fields["segments"].update(fix["new"])
    fields["other"].update(EXTRA)
    return fields


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    ru = json.loads(RU_PATH.read_text(encoding="utf-8")) if RU_PATH.exists() else {}
    todo = {k: sorted(v - ru.keys()) for k, v in collect().items()}
    todo = {k: v for k, v in todo.items() if v}
    total = sum(len(v) for v in todo.values())
    if args.check:
        print(f"{total} untranslated strings")
        sys.exit(1 if total else 0)
    TODO_PATH.parent.mkdir(parents=True, exist_ok=True)
    TODO_PATH.write_text(json.dumps(todo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{total} untranslated strings -> {TODO_PATH.relative_to(ROOT)}")
    for k, v in todo.items():
        print(f"  {k:18} {len(v)}")


if __name__ == "__main__":
    main()
