#!/usr/bin/env python3
"""Fetch ICE Brent (BRN1!) and ICE Low Sulphur Gasoil (ULS1!) front-month quotes from TradingView.

Writes automation/_prices.json as {"brent": {...}, "gasoil": {...}}. Each entry holds
ready-to-use tile strings, or {"error": ...} if that quote couldn't be fetched. Never
exits non-zero, so the daily workflow carries on and Claude falls back to its own research.
"""

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCAN_URL = "https://scanner.tradingview.com/futures/scan"
OUT = Path(__file__).resolve().parent / "_prices.json"

# key: (ticker, unit, plausible price range)
INSTRUMENTS = {
    "brent": ("ICEEUR:BRN1!", "/bbl", (20, 300)),
    "gasoil": ("ICEEUR:ULS1!", "/mt", (300, 3000)),
}


def _scan(tickers):
    payload = json.dumps({
        "symbols": {"tickers": tickers},
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
    return {row["s"]: row["d"] for row in data.get("data") or []}


def _tile(row, ticker, unit, bounds):
    if row is None:
        raise ValueError(f"no data returned for {ticker}")
    close, pct, abs_chg, desc = row
    lo, hi = bounds
    if close is None or not lo <= close <= hi:
        raise ValueError(f"implausible price for {ticker}: {close}")
    pct = pct or 0.0
    abs_chg = abs_chg or 0.0
    arrow, sign = ("▲", "+") if pct >= 0 else ("▼", "−")
    return {
        "value": f"${close:,.2f}{unit}",
        "change": f"{arrow} {sign}{abs(pct):.2f}% ({sign}${abs(abs_chg):,.2f})",
        "direction": "up" if pct >= 0 else "down",
        "description": desc,
        "source": f"https://www.tradingview.com/symbols/{ticker.replace(':', '-')}/",
    }


def main():
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        rows = _scan([t for t, _, _ in INSTRUMENTS.values()])
        scan_error = None
    except Exception as exc:
        rows, scan_error = {}, f"{type(exc).__name__}: {exc}"

    result = {}
    for key, (ticker, unit, bounds) in INSTRUMENTS.items():
        try:
            if scan_error:
                raise RuntimeError(scan_error)
            entry = _tile(rows.get(ticker), ticker, unit, bounds)
        except Exception as exc:
            entry = {"error": f"{type(exc).__name__}: {exc}"}
        entry["fetched_at"] = fetched_at
        result[key] = entry

    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
