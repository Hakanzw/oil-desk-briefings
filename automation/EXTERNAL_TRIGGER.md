# Reliable 9am trigger (external scheduler)

GitHub's built-in `schedule:` ran the workflow 4–5 hours late, so it was removed.
Instead, a free external scheduler fires the workflow **on time** at 09:00 Dubai
by calling GitHub's `workflow_dispatch` API — the same thing the "Run workflow"
button does. Fully cloud; your machine stays off.

You do this once. Two parts: a narrowly-scoped GitHub token, and a cron-job.org job.

## Part 1 — Create a fine-grained GitHub token

1. Go to **GitHub → Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token**
   (direct: <https://github.com/settings/personal-access-tokens/new>).
2. **Token name:** `oil-desk-cron-trigger`
3. **Expiration:** 1 year (set a reminder to regenerate before it lapses).
4. **Resource owner:** Hakanzw
5. **Repository access:** *Only select repositories* → **oil-desk-briefings**
6. **Permissions:** expand *Repository permissions* → set **Actions** to
   **Read and write**. (Leave everything else as "No access"; *Metadata: Read*
   is added automatically. Nothing else is needed.)
7. **Generate token** and copy it (starts `github_pat_…`). You won't see it again.

This token can do exactly one thing if leaked: start/stop Actions on this one
repo. It cannot read your code elsewhere or touch other repos.

## Part 2 — Create the cron-job.org job

1. Sign up (free) at <https://cron-job.org> and click **Create cronjob**.
2. **Title:** `OIL DESK daily trigger`
3. **URL:**
   ```
   https://api.github.com/repos/Hakanzw/oil-desk-briefings/actions/workflows/daily-briefing.yml/dispatches
   ```
4. **Schedule:** every day at **09:00**, and set the job's **timezone to
   Asia/Dubai** (cron-job.org has a timezone selector). That equals 05:00 UTC.
5. Open **Advanced / Request settings**:
   - **Request method:** `POST`
   - **Headers** (add each as key / value):
     | Key | Value |
     |-----|-------|
     | `Accept` | `application/vnd.github+json` |
     | `Authorization` | `Bearer github_pat_…`  (paste your token) |
     | `X-GitHub-Api-Version` | `2022-11-28` |
     | `Content-Type` | `application/json` |
   - **Request body:**
     ```json
     {"ref":"main"}
     ```
6. **Save.**

## Part 3 — Test it

On cron-job.org, use **Test run / Run now**. A successful call returns
**HTTP 204** (GitHub's "accepted, no content"). Then check the repo's **Actions**
tab — a new "Daily OIL DESK Briefing" run should appear within seconds.

If you get **401/403**: the token is wrong or missing the Actions: write
permission. If **404**: re-check the URL (owner/repo/workflow filename) and that
the token's repository access includes oil-desk-briefings.

After it works, you're done — the briefing fires at 09:00 Dubai daily, on time,
with your computer off.
