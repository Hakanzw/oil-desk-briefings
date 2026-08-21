# OIL DESK — daily run prompt

This is the self-contained prompt the scheduled job executes each morning at
09:00 Dubai time. It is also the prompt to paste if you ever run the briefing by
hand. Working directory: `C:\Users\hakan\Desktop\Cowork\Oil Market Updates`.

---

You are producing today's **OIL DESK** daily oil-market briefing. Work in
`C:\Users\hakan\Desktop\Cowork\Oil Market Updates`. Use `python` (not `python3`)
on this Windows machine.

1. **Research** the current state of the global oil market as of today's date:
   latest Brent front-month price, Low Sulphur Gasoil Futures (ICE Europe,
   ticker ULS1!) front-month price, both with daily % change; natural gas; the
   dominant geopolitical/supply story, OPEC+ developments, the latest EIA
   inventory data, and 5–6 distinct news items. Prefer reputable sources
   (Reuters, Al Jazeera, CNBC, NPR, PBS, EIA, OPEC, Bloomberg, NBC, WSJ) and keep
   a real, working article URL for each headline. Do **not** fabricate prices or
   quotes — every figure must trace to a source you retrieved today. If a source
   can't be reached, note it rather than guessing.

2. **Determine the volume number.** Find the most recent prior briefing (the
   newest `oil-market-briefing-*.html` or `*.json` in the folder), read its
   `Vol./No.`, and increment the issue number by 1 (e.g. `Vol. XLII — No. 166`
   → `No. 167`).

3. **Write** a data file `YYYY-MM-DD.json` in the folder that matches the schema
   in `automation\sample-data.json` exactly. Fill in: `date_long`, `date_slug`
   (e.g. `jun16-2026`), `volume`, `dateline`, `sources`; the `ticker`; 5 `prices`
   tiles (first two are Brent then Low Sulphur Gasoil ULS1! — they also feed the
   masthead; label the Gasoil tile "Low Sulphur Gasoil (ULS1!)"); the `lead`
   story (eyebrow, headline, 3 paragraphs, 4 stats, source link); 6 `news` cards;
   5 `events` with risk badges (`Very High`/`High`/`Medium`/`Low`); and the
   `verdict` (4 paragraphs, disclaimer, 6 directional meters, the price `call`,
   and `watch_levels`). Keep the editorial voice consistent with prior issues.
   Body copy may contain `<strong>`/`<em>`.

4. **Render:** `python automation\build_report.py YYYY-MM-DD.json`
   This writes `oil-market-briefing-<slug>.html`. Open/verify it built and all
   sections are present.

5. **Commit + push:**
   ```
   git add -A
   git commit -m "Briefing: <date_long>"
   git push
   ```

6. **Email** the report to **hakan.zw@gmail.com**:
   ```
   python automation\send_email.py oil-market-briefing-<slug>.html ^
     --subject "OIL DESK — Daily Briefing | <date_long>" ^
     --body "<3-4 line summary of the top story and the Brent price call>"
   ```
   If this step fails because Gmail authorization hasn't been completed yet
   (`automation\gmail_token.json` missing — see `automation\EMAIL_SETUP.md`),
   note the failure in your summary but treat the run as otherwise successful —
   the briefing is already built, committed, and pushed.

7. Report a short summary: the headline, the price call, the commit, and whether
   the email sent.
