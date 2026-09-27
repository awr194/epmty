"""Compare the rule-based Czech score with blind LLM runs (step 10.3).

Reads the batch summaries (reports/llm_batch_summary_<engine>.md, written by run_llm_batch.py) and
prints, for the current weights in scoring/config.py: correlation and mean absolute error against
each blind engine, and a least-squares fit showing how much weight the LLM gives each rule factor
(1 = same as the rules, 0 = the LLM ignores it). It proposes nothing automatically: weights are
changed by hand after review.

  python scripts/calibrate.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analyzer import CzechAssumptions, quick_metrics  # noqa: E402
from data_loader import load_curated  # noqa: E402
from scoring.czech import czech_adjusted_score  # noqa: E402
from scoring.metrics import derived_metrics  # noqa: E402


def load_summary(path: Path) -> dict[str, float]:
    """Model name -> mean LLM Czech score from a batch summary table."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) == 9 and re.fullmatch(r"-?\d+(\.\d+)?", cells[6]):
            out[cells[0]] = float(cells[6])
    return out


def main() -> None:
    a = CzechAssumptions()
    rules = {}
    for m in load_curated():
        q = quick_metrics(m, a)
        cs = czech_adjusted_score(q["score"], m, derived_metrics(m, a, q))
        rules[m.name] = (cs.base, cs.score, {x.factor: -x.points for x in cs.breakdown})
    for path in sorted((ROOT / "reports").glob("llm_batch_summary_*+blind.md")):
        llm = {n: v for n, v in load_summary(path).items() if n in rules}
        if len(llm) < 5:
            continue
        names = list(llm)
        y = np.array([llm[n] for n in names])
        cz = np.array([rules[n][1] for n in names])
        print(f"\n{path.stem.removeprefix('llm_batch_summary_')}: {len(names)} models")
        print(f"  correlation {np.corrcoef(y, cz)[0, 1]:.2f}, MAE {np.abs(y - cz).mean():.1f}, "
              f"mean LLM - rules {np.mean(y - cz):+.1f}")
        factors = sorted({f for n in names for f in rules[n][2]})
        x = np.column_stack([[rules[n][0] for n in names]] + [[rules[n][2].get(f, 0) for n in names] for f in factors]
                            + [np.ones(len(names))])
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        r2 = 1 - ((y - x @ coef) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        print(f"  fit R2 {r2:.2f}; base score weight {coef[0]:.2f}")
        for f, c in zip(factors, coef[1:-1]):
            n_used = sum(1 for n in names if rules[n][2].get(f, 0) > 0)
            print(f"    {f:32} LLM weight vs rules {-c:5.2f}  (models with this factor: {n_used})")


if __name__ == "__main__":
    main()
