"""Persist LLM deep-dive reports so their scores, rationale and confidence survive restarts.

One JSON file per model in data/llm_reports/ (gitignored) holding every run, newest last.
Offline (heuristic) reports are not stored - they can always be recomputed.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from analyzer import AnalysisResult, CzechReport

STORE_DIR = Path(__file__).parent / "data" / "llm_reports"


def _path(model_id: str) -> Path:
    return STORE_DIR / f"{re.sub(r'[^A-Za-z0-9_-]', '_', model_id)}.json"


def save(model_id: str, model_name: str, result: AnalysisResult, store_dir: Path | None = None) -> Path | None:
    if result.engine == "mock":
        return None
    path = _path(model_id) if store_dir is None else store_dir / _path(model_id).name
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"model": model_name, "runs": []}
    data["runs"].append({"timestamp": datetime.now().isoformat(timespec="seconds"), "engine": result.engine,
                         "report": result.report.model_dump()})
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def latest(model_id: str, store_dir: Path | None = None) -> dict | None:
    """Newest stored run as {'timestamp', 'engine', 'report': CzechReport}, or None."""
    path = _path(model_id) if store_dir is None else store_dir / _path(model_id).name
    if not path.exists():
        return None
    run = json.loads(path.read_text(encoding="utf-8"))["runs"][-1]
    try:
        report = CzechReport.model_validate(run["report"])
    except ValueError:  # stored before a schema change
        return None
    return {"timestamp": run["timestamp"], "engine": run["engine"], "report": report}
