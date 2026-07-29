#!/usr/bin/env python3
"""
OIL DESK — Gmail sender (standard-library only).

Sends the rendered HTML briefing to the configured recipient using the Gmail
API with a locally-cached OAuth refresh token. Uses ONLY the Python standard
library (urllib / http.server) so it runs anywhere — including Windows-on-ARM,
where the usual google-auth stack can't install (no cryptography wheel).

It still uses a normal Google Cloud OAuth client and the gmail.send scope; the
token refresh and message send are plain HTTPS calls, which need no crypto libs.

One-time setup (interactive, run once on this machine):
    python send_email.py --setup
Opens a browser, you grant the "send email" scope, and a refresh token is saved
to gmail_token.json. Every later run reuses/refreshes it automatically.

Daily use (non-interactive):
    python send_email.py <briefing.html> \
        --subject "OIL DESK — Daily Briefing | Monday, June 15, 2026" \
        --body "Short 3-4 line summary of today's top story and price call."

The HTML file is attached AND inlined as the HTML body so the briefing renders
directly in the email client; a plain-text fallback is built from --body.

Files (kept out of git via .gitignore):
    gmail_credentials.json  OAuth client (Desktop app) downloaded from Google Cloud.
    gmail_token.json        Cached refresh token (created by --setup).

Override paths / recipient with env vars if desired:
    OIL_DESK_GMAIL_CREDENTIALS, OIL_DESK_GMAIL_TOKEN, OIL_DESK_EMAIL_TO
"""

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
import webbrowser
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCOPE = "https://www.googleapis.com/auth/gmail.send"
AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SEND_URI = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

HERE = Path(__file__).resolve().parent
CREDENTIALS_FILE = Path(
    os.environ.get("OIL_DESK_GMAIL_CREDENTIALS", HERE / "gmail_credentials.json")
)
TOKEN_FILE = Path(os.environ.get("OIL_DESK_GMAIL_TOKEN", HERE / "gmail_token.json"))
AUTH_URL_FILE = HERE / "_auth_url.txt"
DEFAULT_TO = os.environ.get("OIL_DESK_EMAIL_TO", "hakan.zw@gmail.com")


def _post_form(url, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc


def _load_client():
    if not CREDENTIALS_FILE.exists():
        sys.exit(
            f"OAuth client file not found: {CREDENTIALS_FILE}\n"
            "Create a Desktop-app OAuth client in Google Cloud Console and save the "
            "downloaded JSON there. See automation/EMAIL_SETUP.md for step-by-step."
        )
    raw = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    block = raw.get("installed") or raw.get("web") or raw
    return block["client_id"], block["client_secret"]


class _CodeHandler(BaseHTTPRequestHandler):
    code = None

    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _CodeHandler.code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        msg = "Authorization complete — you can close this tab and return to the terminal."
        self.wfile.write(f"<html><body><h2>OIL DESK</h2><p>{msg}</p></body></html>".encode())

    def log_message(self, *args):
        pass  # keep the console quiet


def run_setup():
    client_id, client_secret = _load_client()
    server = HTTPServer(("127.0.0.1", 0), _CodeHandler)
    redirect_uri = f"http://127.0.0.1:{server.server_address[1]}/"

    auth_url = AUTH_URI + "?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    })

    AUTH_URL_FILE.write_text(auth_url, encoding="utf-8")
    print("\n" + "=" * 72)
    print("AUTHORIZE GMAIL — open this URL in Chrome or Edge:\n")
    print(auth_url)
    print("=" * 72)
    print(f"(URL also saved to: {AUTH_URL_FILE})")
    print("Waiting for you to finish in the browser...\n")
    try:
        webbrowser.open(auth_url)  # best-effort; ignored if it lands in an editor
    except Exception:
        pass
    server.handle_request()  # blocks until Google redirects back with the code
    code = _CodeHandler.code
    if not code:
        sys.exit("Did not receive an authorization code. Try --setup again.")

    tok = _post_form(TOKEN_URI, {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    })
    if "refresh_token" not in tok:
        sys.exit(
            "No refresh token returned. Revoke prior access at "
            "https://myaccount.google.com/permissions and run --setup again."
        )
    TOKEN_FILE.write_text(json.dumps({
        "refresh_token": tok["refresh_token"],
        "client_id": client_id,
        "client_secret": client_secret,
    }, indent=2), encoding="utf-8")
    try:
        AUTH_URL_FILE.unlink()
    except OSError:
        pass
    print(f"Authorization complete. Token saved to {TOKEN_FILE}")


def get_access_token():
    if not TOKEN_FILE.exists():
        sys.exit("No Gmail token. Run a one-time authorization first:\n    python send_email.py --setup")
    saved = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    try:
        tok = _post_form(TOKEN_URI, {
            "client_id": saved["client_id"],
            "client_secret": saved["client_secret"],
            "refresh_token": saved["refresh_token"],
            "grant_type": "refresh_token",
        })
    except RuntimeError as exc:
        sys.exit(
            f"Token refresh failed — the stored refresh token is likely expired or revoked.\n"
            f"Google said: {exc}\n\n"
            "Fix: run  python3 automation/send_email.py --setup  locally, then update\n"
            "the GMAIL_TOKEN_JSON GitHub secret with the new automation/gmail_token.json."
        )
    return tok["access_token"]


def _load_briefing_data():
    """Find the most recent YYYY-MM-DD.json in the repo root."""
    candidates = sorted(HERE.parent.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json"))
    if not candidates:
        return None
    try:
        return json.loads(candidates[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def _meter_bar(meter):
    pct = max(0, min(100, int(meter.get("pct", 0))))
    rest = 100 - pct
    color = "#b03a2e" if meter.get("tone") == "bearish" else "#1e8449"
    name = meter.get("name", "")
    label = meter.get("label", "")
    # Use a thin spacer td for the empty portion to avoid collapsed cells at 0%
    right_td = f'<td width="{rest}%" style="font-size:0;">&nbsp;</td>' if rest > 0 else ""
    return f"""<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;">
      <tr><td style="font-size:11px;font-weight:bold;color:#222222;padding-bottom:2px;text-transform:uppercase;letter-spacing:0.5px;">{name}</td></tr>
      <tr><td style="font-size:11px;color:#666666;padding-bottom:5px;">{label}</td></tr>
      <tr><td><table width="100%" cellpadding="0" cellspacing="0" style="background:#e0e0e0;border-radius:3px;">
        <tr>
          <td width="{pct}%" style="background:{color};border-radius:3px;height:7px;font-size:0;">&nbsp;</td>
          {right_td}
        </tr>
      </table></td></tr>
    </table>"""


def _price_tiles_html(prices):
    tiles = prices[:5]
    cells = []
    for i, tile in enumerate(tiles):
        direction = tile.get("direction", "up")
        change_color = "#1e8449" if direction == "up" else "#b03a2e"
        label = tile.get("label", "")
        value = tile.get("value", "")
        change = tile.get("change", "")
        border = "border-right:1px solid #eeeeee;" if i < len(tiles) - 1 else ""
        cells.append(f"""<td style="padding:14px 8px;text-align:center;{border}">
          <p style="color:#888888;font-size:9px;letter-spacing:1px;text-transform:uppercase;margin:0 0 5px;">{label}</p>
          <p style="color:#1a1a2e;font-size:17px;font-weight:bold;margin:0 0 4px;">{value}</p>
          <p style="color:{change_color};font-size:9px;margin:0;line-height:1.4;">{change}</p>
        </td>""")
    return f"""<tr><td style="padding:0;border-bottom:1px solid #eeeeee;">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>{"".join(cells)}</tr></table>
    </td></tr>"""


def _link_email_html(body_text, url, date_long, data=None):
    verdict_html = ""
    meters_html = ""
    call_html = ""
    prices_html = ""

    if data:
        prices = data.get("prices", [])
        if prices:
            prices_html = _price_tiles_html(prices)

        verdict = data.get("verdict", {})

        # Verdict paragraphs (no heading)
        paras = verdict.get("paragraphs", [])
        if paras:
            verdict_html = "".join(
                f'<p style="color:#333333;font-size:14px;line-height:1.75;margin:0 0 14px;">{p}</p>'
                for p in paras
            )

        # Price call
        call = verdict.get("call", {})
        if call:
            call_html = f"""<table width="100%" cellpadding="0" cellspacing="0" style="background:#1a1a2e;border-radius:4px;margin:4px 0 24px;">
              <tr><td style="padding:16px 20px;">
                <p style="color:#c8a96e;font-size:10px;letter-spacing:2px;text-transform:uppercase;margin:0 0 4px;">{call.get('label','')}</p>
                <p style="color:#ffffff;font-size:22px;font-weight:bold;margin:0 0 4px;">{call.get('value','')}</p>
                <p style="color:#aaaaaa;font-size:12px;margin:0;">{call.get('bias','')}</p>
              </td></tr>
            </table>"""

        # Meters
        meters = verdict.get("meters", [])
        if meters:
            bars = "".join(_meter_bar(m) for m in meters)
            meters_html = f"""<tr><td style="padding:0 30px 8px;">
              <p style="color:#1a1a2e;font-size:11px;font-weight:bold;letter-spacing:2px;text-transform:uppercase;margin:0 0 16px;border-bottom:2px solid #c8a96e;padding-bottom:8px;">Directional Pressure Gauge</p>
              {bars}
            </td></tr>"""

    # Fallback to plain body text if no verdict data
    if not verdict_html:
        verdict_html = f'<p style="color:#333333;font-size:14px;line-height:1.75;margin:0;">{(body_text or "").replace(chr(10), "<br>")}</p>'

    verdict_block = f"""<tr><td style="padding:28px 30px 8px;">
      {verdict_html}
      {call_html}
    </td></tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f0f0;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f0f0;">
    <tr><td align="center" style="padding:40px 16px;">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:6px;max-width:600px;">
        <tr><td style="background:#1a1a2e;padding:28px 30px;text-align:center;border-radius:6px 6px 0 0;">
          <p style="color:#c8a96e;font-size:10px;letter-spacing:3px;margin:0 0 6px;text-transform:uppercase;">Daily Briefing</p>
          <h1 style="color:#ffffff;font-size:22px;margin:0;letter-spacing:2px;">OIL DESK</h1>
          <p style="color:#aaaaaa;font-size:12px;margin:8px 0 0;">{date_long}</p>
        </td></tr>
        {prices_html}
        {verdict_block}
        {meters_html}
        <tr><td align="center" style="padding:20px 30px 36px;">
          <table cellpadding="0" cellspacing="0">
            <tr><td style="background:#c8a96e;border-radius:4px;">
              <a href="{url}" style="display:inline-block;padding:13px 30px;color:#1a1a2e;font-weight:bold;font-size:13px;text-decoration:none;letter-spacing:1px;">READ FULL BRIEFING &#8594;</a>
            </td></tr>
          </table>
        </td></tr>
        <tr><td style="background:#f8f8f8;padding:18px 30px;text-align:center;border-top:1px solid #eeeeee;border-radius:0 0 6px 6px;">
          <p style="color:#999999;font-size:11px;margin:0;">OIL DESK — Daily Market Intelligence</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def build_raw(to_addr, subject, body_text, html_path=None, url=None, date_long=None):
    msg = EmailMessage()
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body_text or "Today's OIL DESK briefing is available online.")
    if url:
        data = _load_briefing_data()
        msg.add_alternative(_link_email_html(body_text, url, date_long or "", data=data), subtype="html")
    elif html_path:
        html_doc = html_path.read_text(encoding="utf-8")
        msg.add_alternative(html_doc, subtype="html")
        msg.add_attachment(
            html_doc.encode("utf-8"),
            maintype="text", subtype="html", filename=html_path.name,
        )
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def send(to_addr, subject, body_text, html_path=None, url=None, date_long=None):
    access_token = get_access_token()
    payload = json.dumps({"raw": build_raw(to_addr, subject, body_text, html_path=html_path, url=url, date_long=date_long)}).encode()
    req = urllib.request.Request(
        SEND_URI, data=payload, method="POST",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())
    print(f"Sent to {to_addr} (message id {result.get('id')})")


def main():
    parser = argparse.ArgumentParser(description="Send the OIL DESK briefing via Gmail.")
    parser.add_argument("html", nargs="?", help="Path to the rendered briefing HTML (fallback if --url not given).")
    parser.add_argument("--url", default="", help="GitHub Pages URL for the briefing.")
    parser.add_argument("--date-long", default="", help="Human-readable date shown in email header.")
    parser.add_argument("--subject", default="OIL DESK — Daily Briefing")
    parser.add_argument("--body", default="", help="Short summary for the email body.")
    parser.add_argument("--to", default=DEFAULT_TO)
    parser.add_argument("--setup", action="store_true",
                        help="Run the one-time interactive OAuth consent and cache a token.")
    args = parser.parse_args()

    if args.setup:
        run_setup()
        return
    if args.url:
        send(args.to, args.subject, args.body, url=args.url, date_long=args.date_long)
        return
    if not args.html:
        parser.error("either --url or a path to the briefing HTML is required (or use --setup)")
    html_path = Path(args.html)
    if not html_path.exists():
        sys.exit(f"HTML file not found: {html_path}")
    send(args.to, args.subject, args.body, html_path=html_path)


if __name__ == "__main__":
    main()
