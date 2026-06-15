# Gmail send setup (one-time, ~10 minutes)

The daily briefing is emailed via the Gmail API using a refresh token cached on
this machine. `send_email.py` uses only the Python standard library (no
`google-auth`/`cryptography`, which can't build on this Windows-on-ARM machine),
but it still authenticates with a normal Google OAuth client and the minimal
`gmail.send` scope.

You do steps 1–3 once. After that, every run — including the scheduled job —
sends silently.

## 1. Create an OAuth client in Google Cloud Console

1. Go to <https://console.cloud.google.com/> and sign in as **hakan.zw@gmail.com**.
2. Create a project (or pick one), e.g. **"Oil Desk Briefings"**.
3. **Enable the Gmail API:** APIs & Services → Library → search "Gmail API" → **Enable**.
4. **Configure the consent screen:** APIs & Services → OAuth consent screen.
   - User type: **External** (or Internal if this is a Workspace account).
   - App name: *Oil Desk*, user support email + developer email: your address.
   - **Scopes:** you can leave empty here (the script requests `gmail.send`).
   - **Test users:** add **hakan.zw@gmail.com**.
   - You can leave the app in **Testing** mode — no Google verification needed
     for your own account. (Refresh tokens for test apps can expire after 7 days
     of disuse; since this runs daily, that won't be an issue. If a token ever
     stops working, just re-run `--setup`.)
5. **Create the credential:** APIs & Services → Credentials → **Create
   Credentials → OAuth client ID** → Application type **Desktop app** → Create.
6. **Download** the JSON. Save it as:

   ```
   automation\gmail_credentials.json
   ```

   (This path is already git-ignored, so the secret is never pushed.)

## 2. Authorize once (interactive)

From the `Oil Market Updates` folder:

```powershell
python automation\send_email.py --setup
```

A browser opens → choose **hakan.zw@gmail.com** → you'll see an "unverified app"
warning (expected for a personal test app) → **Advanced → Go to Oil Desk
(unsafe) → Continue → Allow**. The terminal prints
`Authorization complete. Token saved to ...\gmail_token.json`.

## 3. Test a real send

```powershell
python automation\send_email.py oil-market-briefing-jun15-2026.html ^
  --subject "OIL DESK — Test Send" ^
  --body "Test of the daily briefing email pipeline."
```

Check hakan.zw@gmail.com — you should get the briefing rendered in-body with the
HTML file attached. Once this works, the scheduled daily job will email
automatically.

## Files this creates (all git-ignored)

| File | What it is | Keep secret? |
|------|------------|--------------|
| `automation/gmail_credentials.json` | OAuth client (client_id/secret) | Yes |
| `automation/gmail_token.json` | Cached refresh token | Yes |

If you ever want to revoke access: <https://myaccount.google.com/permissions>.
