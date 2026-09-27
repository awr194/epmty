"""Shortlist of business models for the founder profile (step 11).

Applies the profile's hard filters (scoring/profile.py), ranks the rest by the Czech-adjusted score
with the profile's weights and writes:

  reports/shortlist.md      - the ranked table with the main reasons behind each score
  data/shortlist.json       - the top names, for scripts/run_llm_batch.py --sample-file

  python scripts/shortlist.py            # top 15
  python scripts/shortlist.py --top 20
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analyzer import CzechAssumptions, quick_metrics  # noqa: E402
from data_loader import load_curated  # noqa: E402
from scoring.czech import czech_adjusted_score  # noqa: E402
from scoring.metrics import derived_metrics  # noqa: E402
from scoring.profile import OWNER_PROFILE, FounderProfile  # noqa: E402

REPORT = ROOT / "reports" / "shortlist.md"
NAMES = ROOT / "data" / "shortlist.json"


def build(profile: FounderProfile = OWNER_PROFILE) -> tuple[list[dict], Counter]:
    a = CzechAssumptions()
    weights = profile.weights()
    kept, rejected = [], Counter()
    for m in load_curated():
        q = quick_metrics(m, a)
        reason = profile.rejection(m, q["price_czk"])
        if reason:
            rejected[reason[0]] += 1
            continue
        dm = derived_metrics(m, a, q)
        cs = czech_adjusted_score(q["score"], m, dm, weights)
        kept.append({"m": m, "score": cs.score, "base": cs.base, "price": q["price_czk"],
                     "customers": profile.customers_for_goal(q["price_czk"]), "cs": cs, "dm": dm})
    kept.sort(key=lambda r: (-r["score"], -r["base"], r["m"].name))
    return kept, rejected


def _n(v: int) -> str:
    return f"{v:,}".replace(",", " ")


def to_markdown(rows: list[dict], rejected: Counter, total: int, profile: FounderProfile, top: int) -> str:
    out = ["# Shortlist for the founder profile", "",
           "Profile: " + "; ".join(profile.notes) + ".",
           f"Income goal: {_n(profile.target_net_czk)} CZK net + ~{_n(profile.overhead_czk)} CZK costs = "
           f"{_n(profile.target_mrr_czk)} CZK MRR; at most {profile.max_customers} customers.", "",
           f"Passed the filters: **{len(rows)}** of {total}. Rejected: "
           + ", ".join(f"{k} ({v})" for k, v in rejected.most_common()) + ".", "",
           "Score = Czech-adjusted score with the profile's weights (native Czech: no language penalty). "
           "It ranks candidates for a closer look; it does not decide.", "",
           "| # | Model | Category | Type | Score | Base | Price CZK/mo | Customers for goal | "
           "Incumbents | Original in CZ | Main deductions |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows[:top], 1):
        m = r["m"]
        deductions = ", ".join(f"{a.factor} {a.points:+.0f}" for a in r["cs"].breakdown) or "-"
        out.append(f"| {i} | {m.name} | {m.category} | {m.model_type} | **{r['score']}** | {r['base']} | "
                   f"{_n(r['price'])} | {r['customers']} | {len(m.local_incumbents)} | "
                   f"{m.original_available_in_cz} | {deductions} |")
    out += ["", "Next: LLM deep-dive of this list (`python scripts/run_llm_batch.py --sample-file data/shortlist.json "
            "--model gemini-3.5-flash --runs 2`), then customer interviews for the top 3."]
    return "\n".join(out).replace(",", " ").replace("  ", ", ") + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()
    rows, rejected = build()
    total = len(rows) + sum(rejected.values())
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(to_markdown(rows, rejected, total, OWNER_PROFILE, args.top), encoding="utf-8")
    NAMES.write_text(json.dumps({"models": [r["m"].name for r in rows[:args.top]]}, ensure_ascii=False, indent=1)
                     + "\n", encoding="utf-8")
    for i, r in enumerate(rows[:args.top], 1):
        print(f"{i:2}. {r['score']:3}  {r['m'].name}  ({r['m'].model_type}, {r['price']} CZK, "
              f"{r['customers']} customers)")
    print(f"\n{REPORT.relative_to(ROOT)}, {NAMES.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
