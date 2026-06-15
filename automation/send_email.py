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
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


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
    tok = _post_form(TOKEN_URI, {
        "client_id": saved["client_id"],
        "client_secret": saved["client_secret"],
        "refresh_token": saved["refresh_token"],
        "grant_type": "refresh_token",
    })
    return tok["access_token"]


def build_raw(to_addr, subject, body_text, html_path):
    msg = EmailMessage()
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body_text or "Today's OIL DESK briefing is attached.")
    if html_path:
        html_doc = html_path.read_text(encoding="utf-8")
        msg.add_alternative(html_doc, subtype="html")
        msg.add_attachment(
            html_doc.encode("utf-8"),
            maintype="text", subtype="html", filename=html_path.name,
        )
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def send(to_addr, subject, body_text, html_path):
    access_token = get_access_token()
    payload = json.dumps({"raw": build_raw(to_addr, subject, body_text, html_path)}).encode()
    req = urllib.request.Request(
        SEND_URI, data=payload, method="POST",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())
    print(f"Sent to {to_addr} (message id {result.get('id')})")


def main():
    parser = argparse.ArgumentParser(description="Send the OIL DESK briefing via Gmail.")
    parser.add_argument("html", nargs="?", help="Path to the rendered briefing HTML.")
    parser.add_argument("--subject", default="OIL DESK — Daily Briefing")
    parser.add_argument("--body", default="", help="Short summary for the email body.")
    parser.add_argument("--to", default=DEFAULT_TO)
    parser.add_argument("--setup", action="store_true",
                        help="Run the one-time interactive OAuth consent and cache a token.")
    args = parser.parse_args()

    if args.setup:
        run_setup()
        return
    if not args.html:
        parser.error("a path to the briefing HTML is required (or use --setup)")
    html_path = Path(args.html)
    if not html_path.exists():
        sys.exit(f"HTML file not found: {html_path}")
    send(args.to, args.subject, args.body, html_path)


if __name__ == "__main__":
    main()
