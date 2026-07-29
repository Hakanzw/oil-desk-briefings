#!/usr/bin/env python3
"""
OIL DESK — Daily Briefing generator.

Reads a JSON data file describing one day's briefing and renders a
self-contained HTML report in the exact OIL DESK newspaper style.

Usage:
    python build_report.py briefing-data.json [output.html]

If no output path is given, the file is written next to the data file as
    oil-market-briefing-<slug>.html
where <slug> is derived from the `date_slug` field (e.g. jun15-2026).

The CSS/layout is fixed; everything else is driven by the JSON so a
scheduled agent only has to assemble the day's facts, not touch markup.
See sample-data.json for the full schema and an annotated example.
"""

import json
import sys
import html
from pathlib import Path

CSS = """
  :root {
    --ink: #0d0d0d; --paper: #f5f0e8; --crude: #c8500a; --crude-dark: #8b3508;
    --crude-light: #e8813a; --gold: #d4a017; --green: #2d6a4f; --red: #9b1d20;
    --muted: #6b6055; --rule: #c5b89a; --column-bg: #ede8de;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--paper); color: var(--ink); font-family: 'DM Sans', sans-serif;
    font-weight: 300; line-height: 1.6; font-size: 15px; }
  header { background: var(--ink); color: var(--paper); padding: 0; position: relative; overflow: hidden; }
  .header-ticker { background: var(--crude); padding: 6px 0; overflow: hidden; white-space: nowrap; }
  .ticker-inner { display: inline-block; animation: ticker 40s linear infinite;
    font-family: 'IBM Plex Mono', monospace; font-size: 12px; font-weight: 600;
    letter-spacing: 0.05em; color: #fff; }
  @keyframes ticker { from { transform: translateX(100vw); } to { transform: translateX(-100%); } }
  .masthead-inner { max-width: 1100px; margin: 0 auto; padding: 36px 40px 28px; display: grid;
    grid-template-columns: 1fr auto 1fr; align-items: center; border-bottom: 1px solid #333; }
  .masthead-left { font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: #888;
    text-transform: uppercase; letter-spacing: 0.1em; line-height: 2; }
  .masthead-title { text-align: center; }
  .masthead-title .pub-name { font-family: 'Bebas Neue', sans-serif; font-size: 72px;
    letter-spacing: 0.12em; line-height: 1; color: var(--paper); }
  .masthead-title .pub-sub { font-family: 'Playfair Display', serif; font-style: italic;
    font-size: 14px; color: var(--crude-light); letter-spacing: 0.08em; margin-top: 4px; }
  .masthead-right { font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: #888;
    text-transform: uppercase; letter-spacing: 0.1em; line-height: 2; text-align: right; }
  .prices-bar { max-width: 1100px; margin: 0 auto; padding: 16px 40px; display: flex;
    gap: 40px; justify-content: center; }
  .price-item { text-align: center; }
  .price-label { font-family: 'IBM Plex Mono', monospace; font-size: 10px; color: #666;
    text-transform: uppercase; letter-spacing: 0.1em; }
  .price-val { font-family: 'Bebas Neue', sans-serif; font-size: 36px; letter-spacing: 0.05em;
    line-height: 1; color: var(--paper); }
  .price-change { font-family: 'IBM Plex Mono', monospace; font-size: 11px; margin-top: 2px; }
  .up { color: #5cb85c; } .down { color: #e05252; }
  .price-divider { width: 1px; background: #333; align-self: stretch; margin: 4px 0; }
  main { max-width: 1100px; margin: 0 auto; padding: 40px 40px; }
  .section-header { display: flex; align-items: center; gap: 16px; margin: 48px 0 24px; }
  .section-header h2 { font-family: 'Bebas Neue', sans-serif; font-size: 13px; letter-spacing: 0.25em;
    color: var(--muted); text-transform: uppercase; white-space: nowrap; }
  .section-header::before, .section-header::after { content: ''; flex: 1; height: 1px; background: var(--rule); }
  .lead-story { display: grid; grid-template-columns: 1fr 380px; gap: 40px; padding: 32px 0;
    border-bottom: 2px solid var(--ink); }
  .lead-eyebrow { font-family: 'IBM Plex Mono', monospace; font-size: 10px; text-transform: uppercase;
    letter-spacing: 0.15em; color: var(--crude); font-weight: 600; margin-bottom: 10px; }
  .lead-story h3 { font-family: 'Playfair Display', serif; font-size: 34px; line-height: 1.2;
    font-weight: 700; margin-bottom: 16px; color: var(--ink); }
  .lead-story p { color: #444; font-size: 15.5px; margin-bottom: 14px; }
  .lead-sidebar { border-left: 3px solid var(--crude); padding-left: 28px; display: flex;
    flex-direction: column; gap: 28px; }
  .stat-block { background: var(--column-bg); padding: 18px 20px; border-radius: 2px; }
  .stat-block .stat-num { font-family: 'Bebas Neue', sans-serif; font-size: 48px; line-height: 1; color: var(--crude); }
  .stat-block .stat-desc { font-size: 12px; color: var(--muted); margin-top: 4px;
    text-transform: uppercase; letter-spacing: 0.07em; }
  .news-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 2px; background: var(--rule);
    border: 1px solid var(--rule); margin-bottom: 4px; }
  .news-card { background: var(--paper); padding: 24px 22px; transition: background 0.2s; }
  .news-card:hover { background: var(--column-bg); }
  .news-card .card-num { font-family: 'Bebas Neue', sans-serif; font-size: 42px; color: var(--rule);
    line-height: 1; margin-bottom: 4px; }
  .news-card .card-tag { font-family: 'IBM Plex Mono', monospace; font-size: 9px; text-transform: uppercase;
    letter-spacing: 0.15em; color: var(--crude); font-weight: 600; margin-bottom: 8px; }
  .news-card h4 { font-family: 'Playfair Display', serif; font-size: 17px; line-height: 1.3;
    font-weight: 700; margin-bottom: 10px; color: var(--ink); }
  .news-card p { font-size: 13.5px; color: #555; line-height: 1.55; margin-bottom: 14px; }
  .read-link { font-family: 'IBM Plex Mono', monospace; font-size: 10px; text-transform: uppercase;
    letter-spacing: 0.1em; color: var(--crude); text-decoration: none; font-weight: 600;
    border-bottom: 1px solid var(--crude-light); padding-bottom: 1px;
    transition: color 0.2s, border-color 0.2s; }
  .read-link:hover { color: var(--crude-dark); border-color: var(--crude-dark); }
  .events-table { width: 100%; border-collapse: collapse; }
  .events-table thead tr { background: var(--ink); color: var(--paper); }
  .events-table thead th { padding: 12px 18px; font-family: 'IBM Plex Mono', monospace; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.12em; text-align: left; font-weight: 600; }
  .events-table tbody tr { border-bottom: 1px solid var(--rule); transition: background 0.15s; }
  .events-table tbody tr:hover { background: var(--column-bg); }
  .events-table tbody td { padding: 14px 18px; font-size: 13.5px; vertical-align: top; }
  .event-date { font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--crude);
    font-weight: 600; white-space: nowrap; }
  .event-name { font-weight: 500; color: var(--ink); font-size: 14px; }
  .event-impact { font-size: 12px; color: var(--muted); margin-top: 3px; }
  .badge { display: inline-block; padding: 2px 8px; font-family: 'IBM Plex Mono', monospace;
    font-size: 9px; text-transform: uppercase; letter-spacing: 0.1em; border-radius: 2px; font-weight: 600; }
  .badge-high { background: #fce8e8; color: var(--red); }
  .badge-med { background: #fef3dc; color: #8b5e00; }
  .badge-low { background: #e8f4ec; color: var(--green); }
  .verdict-section { background: var(--ink); color: var(--paper); padding: 48px; margin-top: 48px;
    position: relative; overflow: hidden; }
  .verdict-section::before { content: 'VERDICT'; position: absolute; right: -20px; top: 50%;
    transform: translateY(-50%) rotate(90deg); font-family: 'Bebas Neue', sans-serif; font-size: 120px;
    color: rgba(255,255,255,0.04); letter-spacing: 0.1em; pointer-events: none; }
  .verdict-header { display: flex; align-items: flex-start; gap: 28px; margin-bottom: 32px; }
  .verdict-icon { font-family: 'Bebas Neue', sans-serif; font-size: 80px; line-height: 1;
    color: var(--crude); flex-shrink: 0; }
  .verdict-title h2 { font-family: 'Bebas Neue', sans-serif; font-size: 42px; letter-spacing: 0.06em;
    color: var(--paper); line-height: 1; margin-bottom: 8px; }
  .verdict-title .guru-sig { font-family: 'Playfair Display', serif; font-style: italic; font-size: 13px;
    color: #888; letter-spacing: 0.05em; }
  .verdict-body { display: grid; grid-template-columns: 1fr 240px; gap: 40px; align-items: start; }
  .verdict-text p { font-size: 15.5px; line-height: 1.75; color: #ccc; margin-bottom: 16px; }
  .verdict-text p strong { color: var(--paper); }
  .verdict-meter { background: rgba(255,255,255,0.05); padding: 24px; border: 1px solid #333; border-radius: 2px; }
  .meter-label { font-family: 'IBM Plex Mono', monospace; font-size: 9px; text-transform: uppercase;
    letter-spacing: 0.15em; color: #666; margin-bottom: 16px; }
  .meter-item { margin-bottom: 14px; }
  .meter-name { font-size: 12px; color: #aaa; margin-bottom: 5px; display: flex; justify-content: space-between; }
  .meter-bar-bg { height: 5px; background: #222; border-radius: 2px; overflow: hidden; }
  .meter-bar-fill { height: 100%; border-radius: 2px; transition: width 1s ease; }
  .bullish { background: #5cb85c; } .bearish { background: #e05252; } .neutral-bar { background: #f0a500; }
  .verdict-call { margin-top: 20px; padding: 16px; background: var(--crude); text-align: center; border-radius: 2px; }
  .verdict-call .call-label { font-family: 'IBM Plex Mono', monospace; font-size: 9px; text-transform: uppercase;
    letter-spacing: 0.15em; color: rgba(255,255,255,0.7); margin-bottom: 4px; }
  .verdict-call .call-text { font-family: 'Bebas Neue', sans-serif; font-size: 28px; letter-spacing: 0.1em;
    color: #fff; line-height: 1; }
  footer { max-width: 1100px; margin: 0 auto; padding: 24px 40px; border-top: 1px solid var(--rule);
    display: flex; justify-content: space-between; align-items: center; font-family: 'IBM Plex Mono', monospace;
    font-size: 10px; color: #aaa; text-transform: uppercase; letter-spacing: 0.08em; }
  @media (max-width: 800px) {
    .masthead-inner { grid-template-columns: 1fr; text-align: center; padding: 24px 20px; }
    .masthead-title .pub-name { font-size: 48px; }
    .prices-bar { flex-wrap: wrap; gap: 20px; }
    main { padding: 24px 20px; }
    .lead-story { grid-template-columns: 1fr; }
    .news-grid { grid-template-columns: 1fr; }
    .verdict-body { grid-template-columns: 1fr; }
    .verdict-section { padding: 28px 20px; }
    .verdict-section::before { display: none; }
  }
"""

FONTS = ("https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Playfair+Display:"
         "ital,wght@0,400;0,700;1,400&family=IBM+Plex+Mono:wght@400;600&"
         "family=DM+Sans:wght@300;400;500&display=swap")


def esc(text):
    """Escape text for HTML but keep intentional <strong>/<em> markup the
    author may have included in body copy."""
    if text is None:
        return ""
    return str(text)


def change_class(direction):
    return {"up": "up", "down": "down"}.get((direction or "").lower(), "")


def render(data):
    d = data
    # ---- ticker ----
    ticker_items = " &nbsp;|&nbsp; ".join(esc(t) for t in d.get("ticker", []))

    # ---- prices bar ----
    price_blocks = []
    prices = d.get("prices", [])
    for i, p in enumerate(prices):
        cls = change_class(p.get("direction"))
        change_style = ' style="color:#888;"' if not cls else ""
        price_blocks.append(f"""    <div class="price-item">
      <div class="price-label">{esc(p.get('label'))}</div>
      <div class="price-val">{esc(p.get('value'))}</div>
      <div class="price-change {cls}"{change_style}>{esc(p.get('change'))}</div>
    </div>""")
        if i != len(prices) - 1:
            price_blocks.append('    <div class="price-divider"></div>')
    prices_html = "\n".join(price_blocks)

    # masthead right uses first two prices if present
    brent = prices[0] if len(prices) > 0 else {"value": ""}
    wti = prices[1] if len(prices) > 1 else {"value": ""}

    # ---- lead story stats ----
    stat_html = "\n".join(f"""      <div class="stat-block">
        <div class="stat-num">{esc(s.get('num'))}</div>
        <div class="stat-desc">{esc(s.get('desc'))}</div>
      </div>""" for s in d.get("lead", {}).get("stats", []))

    lead = d.get("lead", {})
    lead_paras = "\n      ".join(f"<p>{esc(p)}</p>" for p in lead.get("paragraphs", []))
    lead_link = ""
    if lead.get("link_url"):
        lead_link = (f'<a href="{esc(lead["link_url"])}" class="read-link" '
                     f'target="_blank">{esc(lead.get("link_text", "Read more"))} →</a>')

    # ---- news cards ----
    cards = []
    for i, c in enumerate(d.get("news", []), start=1):
        link = ""
        if c.get("link_url"):
            link = (f'<a href="{esc(c["link_url"])}" class="read-link" '
                    f'target="_blank">{esc(c.get("link_text", "Read more"))} →</a>')
        cards.append(f"""    <div class="news-card">
      <div class="card-num">{i:02d}</div>
      <div class="card-tag">{esc(c.get('tag'))}</div>
      <h4>{esc(c.get('headline'))}</h4>
      <p>{esc(c.get('body'))}</p>
      {link}
    </div>""")
    news_html = "\n".join(cards)

    # ---- events table ----
    badge_map = {"very high": "badge-high", "high": "badge-high",
                 "medium": "badge-med", "med": "badge-med", "low": "badge-low"}
    rows = []
    for e in d.get("events", []):
        badge_cls = badge_map.get((e.get("risk", "")).lower(), "badge-med")
        rows.append(f"""      <tr>
        <td class="event-date">{esc(e.get('date'))}</td>
        <td>
          <div class="event-name">{esc(e.get('name'))}</div>
          <div class="event-impact">{esc(e.get('impact'))}</div>
        </td>
        <td>{esc(e.get('market_impact'))}</td>
        <td><span class="badge {badge_cls}">{esc(e.get('risk'))}</span></td>
      </tr>""")
    events_html = "\n".join(rows)

    # ---- verdict ----
    v = d.get("verdict", {})
    verdict_paras = "\n        ".join(f"<p>{esc(p)}</p>" for p in v.get("paragraphs", []))
    if v.get("disclaimer"):
        verdict_paras += (f"\n        <p style=\"color:#999; font-size:13px; font-style:italic;\">"
                          f"{esc(v['disclaimer'])}</p>")

    meter_color = {"bullish": ("bullish", "#5cb85c"), "bearish": ("bearish", "#e05252"),
                   "neutral": ("neutral-bar", "#f0a500")}
    meters = []
    for m in v.get("meters", []):
        bar_cls, txt_color = meter_color.get((m.get("tone", "neutral")).lower(),
                                             ("neutral-bar", "#f0a500"))
        meters.append(f"""          <div class="meter-item">
            <div class="meter-name"><span>{esc(m.get('name'))}</span><span style="color:{txt_color}">{esc(m.get('label'))}</span></div>
            <div class="meter-bar-bg"><div class="meter-bar-fill {bar_cls}" style="width:{int(m.get('pct', 50))}%"></div></div>
          </div>""")
    meters_html = "\n".join(meters)

    watch = v.get("watch_levels", {})
    watch_html = ""
    if watch:
        watch_html = f"""
        <div style="margin-top:16px; padding:16px; background:rgba(255,255,255,0.05); border:1px solid #333; border-radius:2px;">
          <div style="font-family:'IBM Plex Mono',monospace; font-size:9px; text-transform:uppercase; letter-spacing:0.12em; color:#666; margin-bottom:10px;">Key Watch Levels</div>
          <div style="font-size:12px; color:#aaa; line-height:2;">
            <div>🔴 Resistance: <span style="color:#fff">{esc(watch.get('resistance'))}</span></div>
            <div>🟢 Support: <span style="color:#fff">{esc(watch.get('support'))}</span></div>
            <div>⚡ Breakout: <span style="color:#fff">{esc(watch.get('breakout'))}</span></div>
            <div>📉 Breakdown: <span style="color:#fff">{esc(watch.get('breakdown'))}</span></div>
          </div>
        </div>"""

    call = v.get("call", {})

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OIL DESK — Market Briefing | {esc(d.get('date_long'))}</title>
<link href="{FONTS}" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>

<header>
  <div class="header-ticker">
    <span class="ticker-inner">&nbsp;&nbsp;&nbsp;&nbsp;{ticker_items}&nbsp;&nbsp;&nbsp;&nbsp;</span>
  </div>

  <div class="masthead-inner">
    <div class="masthead-left">
      {esc(d.get('date_long'))}<br>
      {esc(d.get('volume'))}<br>
      {esc(d.get('dateline', 'Harare, Zimbabwe'))}
    </div>
    <div class="masthead-title">
      <div class="pub-name">OIL DESK</div>
      <div class="pub-sub">The Daily Briefing for Global Energy Markets</div>
    </div>
    <div class="masthead-right">
      {esc(brent.get('label', 'Brent Spot'))}<br>
      <span style="font-size:18px; color:var(--crude-light); font-family:'Bebas Neue',sans-serif; letter-spacing:0.1em;">{esc(brent.get('value'))}</span><br>
      {esc(wti.get('label', 'WTI Spot'))}<br>
      <span style="font-size:18px; color:var(--crude-light); font-family:'Bebas Neue',sans-serif; letter-spacing:0.1em;">{esc(wti.get('value'))}</span>
    </div>
  </div>

  <div class="prices-bar">
{prices_html}
  </div>
</header>

<main>

  <div class="section-header"><h2>Top Story</h2></div>

  <div class="lead-story">
    <div>
      <div class="lead-eyebrow">{esc(lead.get('eyebrow'))}</div>
      <h3>{esc(lead.get('headline'))}</h3>
      {lead_paras}
      {lead_link}
    </div>
    <div class="lead-sidebar">
{stat_html}
    </div>
  </div>

  <div class="section-header"><h2>Today's Key Headlines</h2></div>

  <div class="news-grid">
{news_html}
  </div>

  <div class="section-header"><h2>This Week's Market-Moving Events &amp; Announcements</h2></div>

  <table class="events-table">
    <thead>
      <tr><th>Date</th><th>Event</th><th>Expected Market Impact</th><th>Risk</th></tr>
    </thead>
    <tbody>
{events_html}
    </tbody>
  </table>

  <div class="verdict-section">
    <div class="verdict-header">
      <div class="verdict-icon">⚡</div>
      <div class="verdict-title">
        <h2>The Guru's Verdict — {esc(d.get('date_long'))}</h2>
        <div class="guru-sig">Oil Trading Intelligence — Independent Market Opinion</div>
      </div>
    </div>

    <div class="verdict-body">
      <div class="verdict-text">
        {verdict_paras}
      </div>

      <div>
        <div class="verdict-meter">
          <div class="meter-label">Directional Pressure Gauge</div>
{meters_html}
        </div>

        <div class="verdict-call">
          <div class="call-label">{esc(call.get('label', "Today's Price Call — Brent Crude"))}</div>
          <div class="call-text">{esc(call.get('value'))}</div>
          <div style="font-family:'IBM Plex Mono',monospace; font-size:10px; color:rgba(255,255,255,0.7); margin-top:6px; text-transform:uppercase; letter-spacing:0.1em;">{esc(call.get('bias'))}</div>
        </div>
{watch_html}
      </div>
    </div>
  </div>

</main>

<footer>
  <span>Oil Desk Daily Briefing — {esc(d.get('date_long'))}</span>
  <span>Sources: {esc(d.get('sources', 'IEA, EIA, OPEC, Reuters'))}</span>
  <span>For Informational Purposes Only</span>
</footer>

</body>
</html>
"""
    return html_doc


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    data_path = Path(sys.argv[1])
    data = json.loads(data_path.read_text(encoding="utf-8"))

    if len(sys.argv) >= 3:
        out_path = Path(sys.argv[2])
    else:
        slug = data.get("date_slug", "report")
        out_path = data_path.parent / f"oil-market-briefing-{slug}.html"

    out_path.write_text(render(data), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
