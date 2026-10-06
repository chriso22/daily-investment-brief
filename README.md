# Daily Investment Brief

A mobile-first page for three groups, in this order:

1. Bitcoin
2. Bitcoin-linked equities: Strategy (MSTR), Strive (ASST), and Twenty One Capital (XXI)
3. Space & defense: SpaceX (SPCX), AST SpaceMobile (ASTS), Merlin (MRLN), and Kraken Robotics (KRKNF)

Each group has compact quote rows, a short analysis of the session, and news headlines. Bitcoin headlines are Bitcoin-only: stories about other cryptocurrencies (for example Ethereum, Solana, or Litecoin) are excluded. `index.html` reads `brief-data.json`. `scripts/refresh-brief.py` rebuilds that file from Yahoo Finance chart data and headline feeds. The script uses the Python standard library only.

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

The script writes `brief-data.json` in the repository root and prints each quote. It exits with an error only when every quote fails. A single missing symbol is recorded on that row and the rest of the brief is still written.

## Weekday automation

`.github/workflows/daily-brief.yml` targets about 6:45 a.m. Central Time (`America/Chicago`) Monday through Friday. GitHub schedules are UTC-only and often delayed, so the workflow registers several morning UTC slots (`47 11` through `47 15`, Monday–Friday). The first scheduled run whose `brief-data.json` is not already from today’s Central calendar date refreshes; later slots that day no-op.

The run rebuilds `brief-data.json`, commits it when prices changed, and posts a notice on the open issue titled **Daily Investment Brief**, mentioning @chriso22 and @bevstr. The first successful run opens that issue. GitHub sends the mentions through the notification settings on those accounts. The workflow can also be started manually from the Actions tab (`workflow_dispatch`), which refreshes and notifies immediately even if today’s brief already exists.

GitHub may delay or drop a scheduled run under load. Extra morning slots are there so a late trigger can still publish the weekday brief. The workflow requests permission to write contents and issues.

## GitHub Pages

In the repository on GitHub: **Settings → Pages → Build and deployment → Deploy from a branch**. Choose `main` and `/ (root)`, then save.

The repository includes `.nojekyll` so Pages serves the files directly.

## License

[MIT](LICENSE)
