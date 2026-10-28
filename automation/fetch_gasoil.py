#!/usr/bin/env python3
"""Fetch the ICE Low Sulphur Gasoil front-month (LGOc1) quote from Investing.com.

Writes automation/_gasoil.json with {value, change, change_pct, direction, source, fetched_at}
or {"error": ...} if the page can't be fetched or parsed. Never exits non-zero, so the
daily workflow carries on (Claude falls back to its own research).
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.investing.com/commodities/london-gas-oil"
OUT = Path(__file__).resolve().parent / "_gasoil.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def _field(html, name):
    m = re.search(rf'data-test="{name}"[^>]*>(.*?)</', html, re.S)
    return re.sub(r"<[^>]+>|[()\s]", "", m.group(1)) if m else None


def fetch():
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    last = _field(html, "instrument-price-last")
    change = _field(html, "instrument-price-change")
    pct = _field(html, "instrument-price-change-percent")
    if not last:
        raise ValueError("price element not found (page layout changed or bot check served)")
    num = float(last.replace(",", ""))
    if not 300 <= num <= 3000:
        raise ValueError(f"implausible gasoil price parsed: {last}")
    direction = ""
    if change:
        direction = "down" if change.startswith("-") else "up"
    return {
        "value": f"${last}/mt",
        "change": change,
        "change_pct": pct,
        "direction": direction,
        "source": URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main():
    try:
        result = fetch()
    except Exception as exc:
        result = {"error": f"{type(exc).__name__}: {exc}", "source": URL}
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    sys.exit(main())
