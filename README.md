# Daily Investment Brief

A mobile-first page for three groups, in this order:

1. Bitcoin
2. Bitcoin-linked equities: Strategy (MSTR), Strive (ASST), and Twenty One Capital (XXI)
3. Space & defense: SpaceX (SPCX), AST SpaceMobile (ASTS), and Merlin (MRLN)

Each group has compact quote rows, a short analysis of the session, and news headlines. `index.html` reads `brief-data.json`. `scripts/refresh-brief.py` rebuilds that file from Yahoo Finance chart data and headline feeds. The script uses the Python standard library only.

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

`.github/workflows/daily-brief.yml` runs at 21:30 UTC Monday through Friday (5:30 p.m. Eastern during daylight time, 4:30 p.m. Eastern during standard time). It regenerates `brief-data.json` and commits the file when it changes. The workflow can also be started manually from the Actions tab (`workflow_dispatch`).

GitHub may delay a scheduled run. The job needs the repository's default `GITHUB_TOKEN` permission to write contents, which the workflow requests.

## GitHub Pages

In the repository on GitHub: **Settings → Pages → Build and deployment → Deploy from a branch**. Choose `main` and `/ (root)`, then save.

The repository includes `.nojekyll` so Pages serves the files directly.

## License

[MIT](LICENSE)
