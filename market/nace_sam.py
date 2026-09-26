"""Serviceable market (SAM) sizes from the ČSÚ Register of Economic Subjects (RES).

Source: ČSÚ open data "Registr ekonomických subjektů" (product 140134-26), updated twice a month.
    https://opendata.csu.gov.cz/soubory/od/od_org03/res_data.csv  (~540 MB, UTF-8, comma-separated)
Documentation: https://csu.gov.cz/statistika/registr-ekonomickych-subjektu-otevrena-data-dokumentace

Only active subjects count (empty DDATZAN). Counts use the primary activity (column NACE,
CZ-NACE classification 80004) and are stored for every code prefix (2-5 digits), split by:
  * natural_persons - legal forms 101, 105, 107 (codelist 56: sole traders / OSVČ, farmers)
  * legal_entities  - all other legal forms
  * with_employees  - KATPO (codelist 579) 120-510, i.e. at least one employee
The aggregated result is cached in data/nace_counts.json with the source date, so the app never
needs the raw file. ARES was evaluated as a secondary source but its czNace search does not
return usable counts (see README).
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date
from functools import lru_cache
from pathlib import Path

import requests

RES_URL = "https://opendata.csu.gov.cz/soubory/od/od_org03/res_data.csv"
ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "cache" / "res_data.csv"  # gitignored
COUNTS_PATH = ROOT / "data" / "nace_counts.json"

NATURAL_PERSON_FORMS = {"101", "105", "107"}
NO_EMPLOYEE_KATPO = {"000", "110"}  # 000 = not stated, 110 = no employees
SEGMENTS = ("total", "natural_persons", "legal_entities", "with_employees")


def download_res(dest: Path = RAW_PATH, url: str = RES_URL, chunk: int = 1 << 20) -> dict:
    """Stream the RES CSV to disk. Returns HTTP metadata for the cache file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(".part")
        with open(tmp, "wb") as f:
            for block in r.iter_content(chunk):
                f.write(block)
        tmp.replace(dest)
        # Content-Length is absent when the server compresses the stream; use the size on disk.
        return {"url": url, "last_modified": r.headers.get("Last-Modified", ""), "bytes": dest.stat().st_size}


def count_active_by_nace(csv_path: Path = RAW_PATH) -> tuple[dict[str, dict[str, int]], str]:
    """Aggregate active subjects per CZ-NACE prefix. Returns (counts, data_as_of)."""
    counts: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(SEGMENTS, 0))
    as_of = ""
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["DDATZAN"]:  # terminated subject
                continue
            nace = row["NACE"].strip()
            if not nace.isdigit() or len(nace) < 2:
                continue
            as_of = max(as_of, row.get("DATPLAT", ""))
            natural = row["FORMA"] in NATURAL_PERSON_FORMS
            employees = row["KATPO"] not in NO_EMPLOYEE_KATPO and row["KATPO"] != ""
            for length in range(2, len(nace) + 1):
                c = counts[nace[:length]]
                c["total"] += 1
                c["natural_persons" if natural else "legal_entities"] += 1
                c["with_employees"] += employees
    return dict(counts), as_of


def write_cache(counts: dict, as_of: str, source: dict, path: Path = COUNTS_PATH) -> None:
    payload = {"source": source, "data_as_of": as_of, "refreshed": date.today().isoformat(),
               "note": "Active subjects (DDATZAN empty) by primary CZ-NACE prefix; see market/nace_sam.py",
               "counts": dict(sorted(counts.items()))}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=0), encoding="utf-8")
    load_counts.cache_clear()


@lru_cache(maxsize=1)
def load_counts(path: str = str(COUNTS_PATH)) -> dict:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _dedupe_prefixes(codes: list[str]) -> list[str]:
    """Drop codes already covered by a shorter prefix in the list (avoids double counting)."""
    codes = sorted({c.strip() for c in codes if c.strip()}, key=len)
    kept: list[str] = []
    for c in codes:
        if not any(c.startswith(k) for k in kept):
            kept.append(c)
    return kept


def sam_for_nace(codes: list[str], segment: str = "total", cache: dict | None = None) -> int | None:
    """Number of active subjects for the given CZ-NACE codes, or None if no data is cached."""
    data = (cache if cache is not None else load_counts()).get("counts")
    if not data or not codes:
        return None
    if segment not in SEGMENTS:
        raise ValueError(f"segment must be one of {SEGMENTS}")
    return sum(data.get(c, {}).get(segment, 0) for c in _dedupe_prefixes(codes))


def cache_info() -> str:
    d = load_counts()
    return f"ČSÚ RES as of {d['data_as_of']} (refreshed {d['refreshed']})" if d else "no NACE cache"
