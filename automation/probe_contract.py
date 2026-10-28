import json, urllib.request
URL = "https://scanner.tradingview.com/futures/scan"
H = {"Content-Type": "application/json", "Origin": "https://www.tradingview.com",
     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
def scan(tickers, cols):
    req = urllib.request.Request(URL, data=json.dumps({"symbols": {"tickers": tickers}, "columns": cols}).encode(), headers=H)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()[:400]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
for col in ["expiration", "front_contract", "contract_month", "root", "description", "name",
            "pro_name", "symbol_proname", "base_name", "short_description"]:
    print(col, *scan(["ICEEUR:BRN1!", "ICEEUR:ULS1!"], ["close", col]))
print("contracts", *scan(["ICEEUR:BRN1!", "ICEEUR:BRNZ2026", "ICEEUR:BRNF2027", "ICEEUR:BRNG2027",
                          "ICEEUR:ULS1!", "ICEEUR:ULSX2026", "ICEEUR:ULSZ2026"], ["close", "description"]))
