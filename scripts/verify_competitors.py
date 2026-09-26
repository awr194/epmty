"""Check the URLs of imported (LLM) competitors in data/llm_competitors.json (step 10.2).

An LLM can name a real company with an invented address. Each URL gets a url_status:
"ok", "http_<code>" or an error name, plus checked_at. The card hides links that are not "ok".
Only URLs never checked are requested unless --refresh. One request per second.

  python scripts/verify_competitors.py
  python scripts/verify_competitors.py --refresh
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market.competitors import RESULTS_PATH  # noqa: E402

USER_AGENT = "CzechBizRadar/1.0 (research; verifies competitor links)"
TIMEOUT = 12
PAUSE_S = 1.0


def url_status(url: str) -> str:
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.head(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code in (403, 405) or r.status_code >= 500:  # many sites refuse HEAD: retry with GET
            r = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True, stream=True)
            r.close()
    except requests.RequestException as e:
        return type(e).__name__
    return "ok" if r.status_code < 400 else f"http_{r.status_code}"


def verify(data: dict[str, list[dict]], refresh: bool = False, pause: float = PAUSE_S) -> int:
    n = 0
    for name, items in data.items():
        for item in items:
            if not item.get("url") or (item.get("url_status") and not refresh):
                continue
            item["url_status"] = url_status(item["url"])
            item["checked_at"] = date.today().isoformat()
            print(f"{item['url_status']:<12} {name} -> {item['name']} {item['url']}")
            n += 1
            time.sleep(pause)
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-check URLs already checked")
    args = ap.parse_args()
    if not RESULTS_PATH.exists():
        sys.exit("Run scripts/import_llm_competitors.py first.")
    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    n = verify(data["models"], args.refresh)
    RESULTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nChecked {n} URL(s).")


if __name__ == "__main__":
    main()
