"""Run the LLM deep-dive for a stratified sample of models, several times each (step 10.7).

The runs feed the calibration of the rule-based Czech score (step 10.3): more models, spread over
categories, model types and the whole score range, plus repeated runs to measure the LLM's own spread.

  python scripts/run_llm_batch.py --sample-only           # write data/llm_batch_sample.json, no API calls
  python scripts/run_llm_batch.py                         # Gemini, 2 runs per sampled model
  python scripts/run_llm_batch.py --model gemini-3.5-flash --runs 2 --pause 8
  python scripts/run_llm_batch.py --summary-only          # rebuild reports/llm_batch_summary.md

Needs GEMINI_API_KEY (or GOOGLE_API_KEY) in the environment. Every successful run is stored by
report_store (data/llm_reports/, outside git) exactly like a run from the app. Models that already
have enough runs with this engine are skipped, so an interrupted batch resumes. A rate-limit /
quota error stops the batch (progress is kept); run it again later.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import report_store  # noqa: E402
from analyzer import DEFAULT_GEMINI_MODEL, CzechAssumptions, analyze, quick_metrics  # noqa: E402
from data_loader import BusinessModel, load_curated  # noqa: E402
from scoring.czech import czech_adjusted_score, to_context  # noqa: E402
from scoring.metrics import derived_metrics  # noqa: E402

SAMPLE_PATH = ROOT / "data" / "llm_batch_sample.json"
SUMMARY_PATH = ROOT / "reports" / "llm_batch_summary.md"
PER_CATEGORY = 4
QUANTILES = (0.1, 0.4, 0.7, 0.95)  # spread picks over each category's score range
ALWAYS = ("Slice", "6AM City", "Nicereply")  # models already run by hand: keep them comparable


def rule_scores(models: list[BusinessModel], a: CzechAssumptions, lang: str = "ru") -> dict[str, tuple]:
    """name -> (base score, Czech score, context for the LLM)."""
    out = {}
    for m in models:
        q = quick_metrics(m, a)
        dm = derived_metrics(m, a, q)
        cs = czech_adjusted_score(q["score"], m, dm, lang=lang)
        out[m.name] = (cs.base, cs.score, to_context(cs, m, dm))
    return out


def stratified_sample(models: list[BusinessModel], scores: dict[str, tuple]) -> list[str]:
    """PER_CATEGORY models per category at score quantiles, plus ALWAYS, plus one of each missing type.
    Deterministic: the same data gives the same sample."""
    picked: list[str] = [n for n in ALWAYS if n in scores]
    by_cat: dict[str, list[BusinessModel]] = {}
    for m in models:
        by_cat.setdefault(m.category, []).append(m)
    for cat in sorted(by_cat):
        ranked = sorted(by_cat[cat], key=lambda m: (scores[m.name][1], m.name))
        for q in QUANTILES[:PER_CATEGORY]:
            i = min(len(ranked) - 1, int(q * len(ranked)))
            # nearest not-yet-picked model around the quantile
            for j in sorted(range(len(ranked)), key=lambda j: (abs(j - i), j)):
                if ranked[j].name not in picked:
                    picked.append(ranked[j].name)
                    break
    types = {m.name: m.model_type for m in models}
    for t in sorted({m.model_type for m in models}):
        if not any(types[n] == t for n in picked):
            cand = sorted((m for m in models if m.model_type == t), key=lambda m: -scores[m.name][1])
            picked.append(cand[0].name)
    return picked


def runs_with(model_id: str, engine: str) -> list[dict]:
    path = report_store._path(model_id)
    if not path.exists():
        return []
    return [r for r in json.loads(path.read_text(encoding="utf-8"))["runs"] if r["engine"] == engine]


def summarize(models: dict[str, BusinessModel], names: list[str], scores: dict[str, tuple], engine: str) -> str:
    lines = [f"# LLM batch summary ({engine})", "",
             "Rules = rule-based scores now; LLM = czech_adjusted_score of each stored run (oldest first).",
             "Spread = max - min over runs. Diff = LLM mean - rules Czech score.", "",
             "| Model | Category | Type | Rules base | Rules CZ | LLM runs | LLM mean | Spread | Diff |",
             "|---|---|---|---|---|---|---|---|---|"]
    diffs, spreads = [], []
    for n in names:
        m = models[n]
        runs = runs_with(m.id, engine)
        llm = [r["report"]["czech_adjusted_score"] for r in runs]
        base, cz, _ = scores[n]
        if llm:
            mean = statistics.mean(llm)
            spread = max(llm) - min(llm)
            diffs.append(mean - cz)
            if len(llm) > 1:
                spreads.append(spread)
            cells = [", ".join(map(str, llm)), f"{mean:.0f}", str(spread), f"{mean - cz:+.0f}"]
        else:
            cells = ["-", "-", "-", "-"]
        lines.append(f"| {n} | {m.category} | {m.model_type} | {base} | {cz} | " + " | ".join(cells) + " |")
    lines += ["", f"Models with runs: {len(diffs)} of {len(names)}."]
    if diffs:
        lines.append(f"Mean diff (LLM - rules): {statistics.mean(diffs):+.1f}; "
                     f"mean |diff|: {statistics.mean(abs(d) for d in diffs):.1f}.")
    if spreads:
        lines.append(f"LLM run-to-run spread: mean {statistics.mean(spreads):.1f}, max {max(spreads)} "
                     f"(over {len(spreads)} models with 2+ runs). Differences smaller than this are noise.")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_GEMINI_MODEL, help="Gemini model id")
    ap.add_argument("--runs", type=int, default=2, help="runs per model")
    ap.add_argument("--pause", type=float, default=8.0, help="seconds between API calls (free-tier limits)")
    ap.add_argument("--lang", default="ru", choices=("ru", "en"))
    ap.add_argument("--limit", type=int, default=0, help="stop after N API calls")
    ap.add_argument("--sample-only", action="store_true")
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument("--resample", action="store_true", help="rebuild the sample even if the file exists")
    args = ap.parse_args()

    a = CzechAssumptions()
    all_models = load_curated()
    by_name = {m.name: m for m in all_models}
    scores = rule_scores(all_models, a, args.lang)

    if SAMPLE_PATH.exists() and not args.resample:
        names = [n for n in json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))["models"] if n in by_name]
    else:
        names = stratified_sample(all_models, scores)
        SAMPLE_PATH.write_text(json.dumps({"models": names}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"Sample of {len(names)} models written to {SAMPLE_PATH}")
    if args.sample_only:
        return

    if not args.summary_only:
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            sys.exit("Set GEMINI_API_KEY first (e.g. `set GEMINI_API_KEY=...` in cmd).")
        calls = 0
        try:
            for i, n in enumerate(names, 1):
                m = by_name[n]
                have = len(runs_with(m.id, args.model))
                for k in range(have, args.runs):
                    if args.limit and calls >= args.limit:
                        raise StopIteration
                    print(f"[{i}/{len(names)}] {n} run {k + 1}/{args.runs} ... ", end="", flush=True)
                    res = analyze(m, a, engine="gemini", gemini_model=args.model,
                                  czech_context=scores[n][2], lang=args.lang)
                    calls += 1
                    if res.engine == "mock":  # the call failed and analyze fell back to the heuristic
                        print("FAILED: " + "; ".join(res.warnings))
                        if any(w in " ".join(res.warnings).lower() for w in ("quota", "limit", "квот", "лимит")):
                            print("Rate limit / quota reached - progress saved, run again later.")
                            raise StopIteration
                        break  # skip this model, go on with the next one
                    report_store.save(m.id, m.name, res)
                    print(f"CZ {res.report.czech_adjusted_score} (rules {scores[n][1]}), "
                          f"{len(res.report.competitors)} competitors, confidence {res.report.confidence}")
                    time.sleep(args.pause)
        except (StopIteration, KeyboardInterrupt):
            print("\nStopped.")
        print(f"API calls made: {calls}")

    SUMMARY_PATH.parent.mkdir(exist_ok=True)
    SUMMARY_PATH.write_text(summarize(by_name, names, scores, args.model), encoding="utf-8")
    print(f"Summary: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
