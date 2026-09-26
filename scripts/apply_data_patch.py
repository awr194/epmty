"""Apply a reviewed data patch (patches/data_fixes.json) to data/cz_enrichment.json.

    python scripts/apply_data_patch.py            # dry run: show what would change
    python scripts/apply_data_patch.py --apply    # write the changes

Base records are never edited; fixes land in the overlay. A fix is skipped if the current value no
longer matches its recorded "old" value (the data changed since the audit).
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cz_enrichment import BASE_OVERRIDES, ENRICHMENT_PATH  # noqa: E402
from data_loader import load_curated  # noqa: E402

PATCH = ROOT / "patches" / "data_fixes.json"
ALLOWED = set(BASE_OVERRIDES) | {"needs_rethink_for_cz"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--patch", type=Path, default=PATCH)
    args = ap.parse_args()

    fixes = json.loads(args.patch.read_text(encoding="utf-8"))["fixes"]
    current = {m.name: m for m in load_curated()}
    overlay = json.loads(ENRICHMENT_PATH.read_text(encoding="utf-8"))
    applied = skipped = 0
    for f in fixes:
        name, field = f["model"], f["field"]
        if field not in ALLOWED:
            print(f"SKIP  {name}.{field}: field not patchable"); skipped += 1; continue
        if name not in current:
            print(f"SKIP  {name}: unknown model"); skipped += 1; continue
        now = getattr(current[name], field)
        if now == f["new"]:
            continue  # already applied
        if now != f["old"]:
            print(f"SKIP  {name}.{field}: value changed since the audit ({now!r})"); skipped += 1; continue
        print(f"{'APPLY' if args.apply else 'WOULD'} {name}.{field}: {f['old']!r} -> {f['new']!r}")
        overlay["models"].setdefault(name, {})[field] = f["new"]
        applied += 1

    if args.apply and applied:
        ENRICHMENT_PATH.write_text(json.dumps(overlay, ensure_ascii=False, indent=2), encoding="utf-8")
    verb = "Applied" if args.apply else "Would apply"
    print(f"{verb} {applied} change(s), skipped {skipped}.{'' if args.apply else ' Run with --apply to write.'}")


if __name__ == "__main__":
    main()
