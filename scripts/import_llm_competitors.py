"""Import local competitors from stored LLM reports into data/llm_competitors.json (step 10.2).

Reads every data/llm_reports/*.json (all runs), normalises threat -> strength 1-3, skips substitutes
and the model itself, merges duplicates, and keeps URL checks already made by verify_competitors.py.
Everything imported is unverified: the card shows it with a "not verified" mark.

  python scripts/import_llm_competitors.py            # write data/llm_competitors.json
  python scripts/import_llm_competitors.py --dry-run  # print only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market.competitors import RESULTS_PATH, extract, same_company  # noqa: E402
from report_store import STORE_DIR  # noqa: E402

_KEEP = ("url_status", "checked_at", "verified")  # results of later checks survive a re-import


def build(store_dir: Path, urls: dict[str, str], previous: dict[str, list[dict]]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for path in sorted(store_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        name = data["model"]
        items = extract(name, urls.get(name, ""), data.get("runs", []))
        for item in items:
            old = next((o for o in previous.get(name, []) if same_company(item, o) and o.get("url") == item["url"]),
                       None)
            if old:
                item.update({k: old[k] for k in _KEEP if k in old})
        if items:
            out[name] = items
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from data_loader import load_curated
    urls = {m.name: m.url for m in load_curated()}
    previous = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))["models"] if RESULTS_PATH.exists() else {}
    result = build(STORE_DIR, urls, previous)
    for name, items in result.items():
        print(f"{name}: " + ", ".join(f"{i['name']} ({i['strength']}, x{i['mentions']})" for i in items))
    total = sum(len(v) for v in result.values())
    print(f"\n{total} competitor(s) for {len(result)} model(s).")
    if not args.dry_run:
        RESULTS_PATH.write_text(json.dumps({"models": result}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"Written: {RESULTS_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
