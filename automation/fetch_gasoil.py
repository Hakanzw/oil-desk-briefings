#!/usr/bin/env python3
"""Fetch the ICE Low Sulphur Gasoil front-month (ICEEUR:ULS1!) quote from TradingView.

Writes automation/_gasoil.json with ready-to-use tile strings, or {"error": ...} if the
quote can't be fetched. Never exits non-zero, so the daily workflow carries on and
Claude falls back to its own research.
"""

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCAN_URL = "https://scanner.tradingview.com/futures/scan"
TICKER = "ICEEUR:ULS1!"
SOURCE = "https://www.tradingview.com/symbols/ICEEUR-ULS1!/"
OUT = Path(__file__).resolve().parent / "_gasoil.json"


def fetch():
    payload = json.dumps({
        "symbols": {"tickers": [TICKER]},
        "columns": ["close", "change", "change_abs", "description"],
    }).encode()
    req = urllib.request.Request(SCAN_URL, data=payload, headers={
        "Content-Type": "application/json",
        "Origin": "https://www.tradingview.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    rows = data.get("data") or []
    if not rows:
        raise ValueError(f"no data returned for {TICKER}")
    close, pct, abs_chg, desc = rows[0]["d"]
    if close is None or not 300 <= close <= 3000:
        raise ValueError(f"implausible gasoil price: {close}")
    pct = pct or 0.0
    abs_chg = abs_chg or 0.0
    arrow, sign = ("▲", "+") if pct >= 0 else ("▼", "−")
    return {
        "value": f"${close:,.2f}/mt",
        "change": f"{arrow} {sign}{abs(pct):.2f}% ({sign}${abs(abs_chg):,.2f})",
        "direction": "up" if pct >= 0 else "down",
        "description": desc,
        "source": SOURCE,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main():
    try:
        result = fetch()
    except Exception as exc:
        result = {"error": f"{type(exc).__name__}: {exc}", "source": SOURCE}
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
