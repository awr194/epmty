"""Refresh data/nace_counts.json from the ČSÚ RES open-data CSV.

Usage:
    python scripts/refresh_nace_sam.py              # download (~540 MB) and aggregate
    python scripts/refresh_nace_sam.py --local PATH # aggregate an already downloaded CSV (offline)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market.nace_sam import RAW_PATH, RES_URL, count_active_by_nace, download_res, write_cache  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local", type=Path, help="Use this local res_data.csv instead of downloading")
    args = ap.parse_args()

    if args.local:
        csv_path, source = args.local, {"url": str(args.local), "last_modified": "local file"}
    else:
        print(f"Downloading {RES_URL} ...", flush=True)
        source, csv_path = download_res(), RAW_PATH
        print(f"  {source['bytes'] / 1e6:.0f} MB, last modified {source['last_modified']}")

    print("Aggregating active subjects by CZ-NACE ...", flush=True)
    counts, as_of = count_active_by_nace(csv_path)
    write_cache(counts, as_of, source)
    print(f"Done: {len(counts)} NACE prefixes, data as of {as_of}. Top 2-digit sections:")
    for code, c in sorted(((k, v) for k, v in counts.items() if len(k) == 2), key=lambda kv: -kv[1]["total"])[:8]:
        print(f"  {code}: {c['total']:>9,} active ({c['with_employees']:,} with employees)")


if __name__ == "__main__":
    main()
