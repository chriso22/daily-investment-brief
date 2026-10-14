# Daily Investment Brief

A mobile-first page for three groups, in this order:

1. Bitcoin
2. Bitcoin-linked equities: Strategy (MSTR), Strive (ASST), and Twenty One Capital (XXI)
3. Space & defense: SpaceX (SPCX), AST SpaceMobile (ASTS), Merlin (MRLN), and Kraken Robotics (KRKNF)

Each group has compact quote rows, a short analysis of the session, and news headlines. Bitcoin headlines are Bitcoin-only: stories about other cryptocurrencies (for example Ethereum, Solana, or Litecoin) are excluded. `index.html` reads `brief-data.json`. `scripts/refresh-brief.py` rebuilds that file from Yahoo Finance chart data and headline feeds, and also writes `brief-email.html`: a self-contained, email-safe HTML brief meant to render inline in an email client (no link-out required). The script uses the Python standard library only.

Figures are delayed market data for information only. This is not investment advice.

## View the page

After GitHub Pages is enabled from the `main` branch at `/` (root):

https://chriso22.github.io/daily-investment-brief/

Locally, from the repository root:

```bash
python3 scripts/refresh-brief.py
python3 -m http.server 8000
```

Open http://127.0.0.1:8000/

Opening `index.html` as a file will not load the JSON. Use the local server or GitHub Pages.

## Refresh the data

Python 3.11 or newer, with network access:

```bash
python3 scripts/refresh-brief.py
```

The script writes `brief-data.json` and `brief-email.html` in the repository root and prints each quote. It exits with an error only when every quote fails. A single missing symbol is recorded on that row and the rest of the brief is still written.

Rebuild only the embedded email HTML from the saved JSON:

```bash
python3 scripts/refresh-brief.py --email-html
```

### HTML email delivery

GitHub issue notifications stay as a short text backup. To send the styled brief so it shows inside the email when opened, set these repository secrets and the workflow will SMTP-send `brief-email.html` as a multipart HTML message:

- `BRIEF_SMTP_HOST`
- `BRIEF_SMTP_PORT` (optional, default `587`)
- `BRIEF_SMTP_USER`
- `BRIEF_SMTP_PASSWORD`
- `BRIEF_MAIL_FROM` (optional if it matches `BRIEF_SMTP_USER`)
- `BRIEF_MAIL_TO` (comma-separated recipients)
- `BRIEF_SMTP_SSL` (optional; set `true` for implicit SSL instead of STARTTLS)

Local send with the same env vars:

```bash
python3 scripts/refresh-brief.py --send-email
```

If those secrets are unset, the send step skips and the Pages copy at `/brief-email.html` is still updated for preview.

## Weekday automation

The brief is due at **6:45 a.m. Central** (`America/Chicago`), Monday through Friday. That is about an hour and 45 minutes before the US cash open at 8:30 a.m. Central. The clock time is not the problem: 6:45 a.m. is early enough. GitHub’s own scheduler is often hours late, so it is only a backup.

The on-time run is the weekday morning check in this project’s Cursor chat. At 6:45 a.m. Central it refreshes `brief-data.json` and pushes that file to `main` when today’s Central date is not already published. That push starts the workflow’s notify job, which comments on the **Daily Investment Brief** issue as `github-actions[bot]`. The comment mentions @chriso22 and @bevstr, and those mentions are the two GitHub notifications. The morning check itself cannot comment. One check is 11:45 UTC (6:45 a.m. CDT) and the other is 12:45 UTC (6:45 a.m. CST). Outside 6:40–7:40 a.m. Central the check stays quiet.

`.github/workflows/daily-brief.yml` still has backup slots at 47 minutes past 11:00–15:00 UTC, weekdays. The first run whose saved brief is not already from today’s Central date refreshes, commits `brief-data.json` when it changed, and posts a notice on the open issue titled **Daily Investment Brief**, mentioning @chriso22 and @bevstr. Later slots that day do nothing. A manual run from the Actions tab (`workflow_dispatch`) refreshes and notifies even if today’s brief already exists.

The workflow requests permission to write contents and issues.

## GitHub Pages

In the repository on GitHub: **Settings → Pages → Build and deployment → Deploy from a branch**. Choose `main` and `/ (root)`, then save.

The repository includes `.nojekyll` so Pages serves the files directly.

## License

[MIT](LICENSE)
