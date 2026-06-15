# OIL DESK — Daily Briefing Automation: Setup Handoff for Claude Code

This folder contains everything needed to automate a daily oil-market briefing.
Hand this whole folder to **Claude Code** (which can install the `gh` CLI, hold
your GitHub auth locally, and reach github.com — things the Cowork sandbox could
not do). The goal:

1. A **private GitHub repo** holding the dated briefings, with full history.
2. A job that runs **daily at 09:00 Dubai time (GST, UTC+4)** that builds the
   day's report, commits + pushes it, and emails it to **hakan.zw@gmail.com**.

---

## What's in this folder

| File | Purpose |
|------|---------|
| `build_report.py` | Renders a full OIL DESK HTML briefing from a JSON data file. Layout/CSS is fixed; all content is data-driven. No external dependencies (standard library only). |
| `sample-data.json` | The June 15, 2026 briefing, doubling as the **schema example**. Copy it to create each new day's data file. |
| `SETUP_FOR_CLAUDE_CODE.md` | This file. |

### How the generator works
```bash
python3 build_report.py <data.json> [output.html]
# e.g.
python3 build_report.py 2026-06-16.json
# -> writes oil-market-briefing-<date_slug>.html next to the JSON
```
The JSON schema (see `sample-data.json` for a filled example):
- `date_long`, `date_slug`, `volume`, `dateline`, `sources` — masthead/footer strings.
- `ticker[]` — scrolling headline strings.
- `prices[]` — `{label, value, change, direction}` where `direction` is `up`/`down`/`""`. First two entries also feed the masthead (Brent, WTI).
- `lead` — `{eyebrow, headline, paragraphs[], link_url, link_text, stats[]}`; each stat is `{num, desc}`. Body copy may contain `<strong>`/`<em>`.
- `news[]` — `{tag, headline, body, link_url, link_text}` (renders numbered cards 01..NN).
- `events[]` — `{date, name, impact, market_impact, risk}`; `risk` of `Very High`/`High`→red, `Medium`→amber, `Low`→green badge.
- `verdict` — `{paragraphs[], disclaimer, meters[], call, watch_levels}`; each meter is `{name, label, tone, pct}` with `tone` ∈ `bullish`/`bearish`/`neutral`; `call` is `{label, value, bias}`; `watch_levels` is `{resistance, support, breakout, breakdown}`.

---

## One-time setup (do this once)

1. **Create the private repo** (with your own GitHub account/auth):
   ```bash
   gh auth login                      # if not already authenticated
   cd "<path>/Oil Market Updates"     # the folder with the briefings
   git init
   gh repo create oil-desk-briefings --private --source=. --remote=origin
   printf "automation/__pycache__/\n*.pyc\n" > .gitignore
   git add . && git commit -m "Initial commit: OIL DESK briefings + generator"
   git push -u origin main
   ```

2. **Confirm the schedule timezone.** Cron on your machine runs in the machine's
   local time. If your computer's clock is **Dubai time (GST)**, use `0 9 * * *`.
   If it's set to another zone, convert 09:00 Dubai (UTC+4) to local — examples:
   - US Pacific (UTC−7, summer): `0 22 * * *` (10pm the prior day)
   - US Eastern (UTC−4, summer): `0 1 * * *`
   - UK (UTC+1, summer): `0 6 * * *`
   - Central Europe (UTC+2, summer): `0 7 * * *`

   (Note daylight-saving shifts move these by an hour; Dubai itself does **not**
   observe DST.) The most robust option is to pin the job to Dubai time
   explicitly — e.g. a cron line `CRON_TZ=Asia/Dubai` prefix on Linux, or in the
   scheduling script set `TZ=Asia/Dubai`.

---

## The daily run

Each morning the job must (a) gather the day's facts, (b) build the JSON, (c)
render the HTML, (d) commit + push, (e) email it. Steps (a)/(b) are editorial,
so the cleanest design is to have **Claude Code run as the daily agent** with the
prompt below, rather than a dumb script — it researches the market, writes the
JSON, then calls the generator.

### Paste-ready daily prompt for Claude Code
> You are producing today's **OIL DESK** daily oil-market briefing.
>
> 1. Research the current state of the global oil market as of today: latest
>    Brent and WTI spot/front-month prices and daily % change, natural gas,
>    the dominant geopolitical/supply story, OPEC+ developments, the latest EIA
>    inventory data, and 5–6 distinct news items. Prefer reputable sources
>    (Reuters, Al Jazeera, CNBC, NPR, PBS, EIA, OPEC, Bloomberg) and keep real
>    article URLs for each headline.
> 2. Write a data file `YYYY-MM-DD.json` in the `Oil Market Updates` folder that
>    matches the schema in `automation/sample-data.json` exactly. Fill in: the
>    ticker, 5 price tiles, the lead story (eyebrow, headline, 3 paragraphs, 4
>    stats, source link), 6 news cards, 5 events with risk badges, and the
>    Guru's Verdict (4 paragraphs, 6 directional meters, the price call, and
>    watch levels). Keep the editorial voice consistent with prior issues.
>    Increment the `volume` number by 1 from the previous issue.
> 3. Run `python3 automation/build_report.py YYYY-MM-DD.json` to render
>    `oil-market-briefing-<slug>.html`.
> 4. Verify the HTML built (opens, all sections present), then:
>    `git add -A && git commit -m "Briefing: <date_long>" && git push`
> 5. Email the report to **hakan.zw@gmail.com**: subject
>    `OIL DESK — Daily Briefing | <date_long>`, with a 3–4 line summary of the
>    day's top story and price call in the body, and the HTML file attached (or
>    its contents inline). Use your configured email tool/SMTP.
>
> Do not fabricate prices or quotes — every figure must trace to a source you
> actually retrieved today. If a source can't be reached, note it rather than
> guessing.

### Scheduling it
- **macOS/Linux:** a `launchd`/`cron` entry at the converted time that invokes
  `claude` (Claude Code, headless/`--print` mode) with the prompt above, pointed
  at this repo as the working directory.
- **Windows:** Task Scheduler running the same command daily at the converted time.

---

## Email options (since the Cowork Gmail tool can only draft, not send)

For true auto-send each morning, in Claude Code use one of:
- **Gmail API** with your own OAuth credentials (send scope), or
- **SMTP** (e.g. an app password) via a small `send_email.py`, or
- the **`gh`/Actions** route below, which can email via a GitHub Action step.

> ⚠️ Handle any tokens, app passwords, or OAuth secrets yourself inside Claude
> Code / your machine's keychain — don't paste them into a chat. The Cowork
> assistant deliberately does not handle these.

---

## Alternative: run it entirely in GitHub Actions (no local machine needed)

If you'd rather not depend on your computer being on at 09:00, move the schedule
into the repo:
- Add `.github/workflows/daily-briefing.yml` with
  `on: schedule: - cron: "0 5 * * *"` (05:00 UTC = 09:00 Dubai — **UTC, not local,
  in Actions**).
- The job checks out the repo, runs the generator (you'd supply the day's JSON,
  e.g. via an API/LLM step or a committed data source), commits the HTML back,
  and emails via an action like `dawidd6/action-send-mail` using repo secrets for
  SMTP credentials.

This is the most hands-off option but needs the data-gathering step wired to an
API key you control.
