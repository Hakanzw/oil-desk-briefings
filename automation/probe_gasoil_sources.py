#!/usr/bin/env python3
"""One-off probe: which public sources return an ICE Low Sulphur Gasoil quote from this runner."""

import json
import re
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def get(url, data=None, headers=None):
    h = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def show(name, status, body, pattern=None):
    found = ""
    if body and pattern:
        m = re.findall(pattern, body, re.S)
        found = " | match: " + repr(m[:3]) if m else " | no match"
    snippet = re.sub(r"\s+", " ", body[:300]) if body and not pattern else ""
    print(f"\n### {name}\nstatus={status} len={len(body or '')}{found}")
    if snippet:
        print("snippet:", snippet)


# TradingView scanner (public, unauthenticated)
for tick in ["ICEEUR:ULS1!", "ICEEUR:G1!", "ICEEUR:LGO1!"]:
    payload = json.dumps({"symbols": {"tickers": [tick]},
                          "columns": ["close", "change", "change_abs", "description", "update_mode"]}).encode()
    s, b = get("https://scanner.tradingview.com/futures/scan", data=payload,
               headers={"Content-Type": "application/json", "Origin": "https://www.tradingview.com"})
    show(f"TradingView scanner {tick}", s, b)

# CNBC quote service
for sym in ["@LGO.1", "LGO.1", "@GO.1"]:
    s, b = get(f"https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols={sym}"
               "&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json")
    show(f"CNBC {sym}", s, b, r'"last":"([^"]+)".{0,200}?"change_pct":"([^"]+)"')

# Yahoo Finance symbol search + chart
s, b = get("https://query2.finance.yahoo.com/v1/finance/search?q=gasoil&quotesCount=10&newsCount=0")
show("Yahoo search 'gasoil'", s, b, r'"symbol":"([^"]+)","[^}]*?"shortname":"([^"]+)"')
for sym in ["GO=F", "LGO=F", "QS=F"]:
    s, b = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d")
    show(f"Yahoo chart {sym}", s, b, r'"shortName":"([^"]+)".{0,400}?"regularMarketPrice":([\d.]+)')

# Barchart, MarketWatch, ICE
s, b = get("https://www.barchart.com/futures/quotes/LF*0/overview")
show("Barchart LF*0", s, b, r'"lastPrice":"([^"]+)"')
s, b = get("https://www.marketwatch.com/investing/future/lgo00?countrycode=uk")
show("MarketWatch lgo00", s, b, r'class="value"[^>]*>([\d,.]+)<')
s, b = get("https://www.ice.com/products/34361119/Low-Sulphur-Gasoil-Futures/data")
show("ICE product page", s, b, r'(\d{3,4}\.\d{2})')

# Stooq
for sym in ["lf.f", "go.f"]:
    s, b = get(f"https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcn&h&e=csv")
    show(f"Stooq {sym}", s, b)
