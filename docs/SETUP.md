# Auto-Update Pipeline — Setup Guide

Keeps `data/` fresh automatically by scraping new MBMBaM transcripts
from maximumfun.org every Monday and rebuilding the site indexes.

---

## Prerequisites

- Your repo is on GitHub with GitHub Pages serving from `docs/`
- The three scripts are in a `scripts/` folder at the repo root
- `data/` contains at least a first-run build of the JSON files

---

## Repo layout expected by the workflow

```
your-repo/
├── .github/
│   └── workflows/
│       └── update-data.yml   ← the workflow file
├── data/
│   ├── manifest.json
│   ├── episode_stats.json
│   ├── word_index.json
│   ├── bigram_index.json
│   ├── trigram_index.json
│   └── stage_index.json
├── index.html
└── scripts/
    ├── scrape_transcripts.py
    ├── parse_transcripts.py
    └── build_index.py
```

---

## One-time setup steps

### 1. Do a local first-run build

The workflow is incremental — it needs existing data to compare against.
Run this locally once to populate `data/`:

```
# Install deps
pip install requests beautifulsoup4 pdfplumber

# Download all available PDFs (~800 episodes, takes a while)
python scripts/scrape_transcripts.py --output pdfs --delay 1.5

# Parse all PDFs
python scripts/parse_transcripts.py pdfs --output parsed_episodes.json

# Build indexes (outputs to data/)
python scripts/build_index.py parsed_episodes.json --output-dir data
```

Commit the resulting `data/*.json` files.  
**Do not commit** `parsed_episodes.json` or the `pdfs/` folder — add them to `.gitignore`.

```gitignore
# .gitignore additions
pdfs/
parsed_episodes.json
```

### 2. Add the workflow file

Copy `update-data.yml` to `.github/workflows/update-data.yml` in your repo.

If your data folder is somewhere other than `data/`, change the two
`data` references in the workflow (one in the cache key, one in
`build_index.py` args).

### 3. Enable workflow permissions

In your repo: **Settings → Actions → General → Workflow permissions**  
Select **"Read and write permissions"** and save.

This lets the workflow commit the updated JSON files back to the repo.

### 4. Push and test

```
git add .github/ data/ scripts/ .gitignore
git commit -m "add auto-update pipeline"
git push
```

Then trigger a manual test:
**Actions → Update transcript data → Run workflow**

Watch the logs. On success it will commit updated `data/` files
(or log "nothing to commit" if no new episodes were found).

---

## How it works

```
Monday 09:00 UTC
       │
       ▼
scrape_transcripts.py
  • Pages through maximumfun.org/transcripts/my-brother-my-brother-and-me/
  • Skips PDFs already in the runner cache (most weeks: all but 1-2 new ones)
  • Downloads new PDFs to pdfs/
       │
       ▼
parse_transcripts.py --incremental
  • Loads existing parsed_episodes.json from the cache
  • Skips episode IDs already present
  • Parses only the new PDFs
  • Appends + re-sorts
       │
       ▼
build_index.py
  • Full rebuild of all 6 JSON files in data/
  • (Fast — pure Python over in-memory data, ~10s for 800 episodes)
       │
       ▼
git diff data/
  • If changed → commit + push → GitHub Pages redeploys automatically
  • If unchanged → log "up to date", exit cleanly
```

---

## Caching

The workflow uses GitHub Actions cache to persist the `pdfs/` folder between
runs. The cache key includes a hash of `manifest.json`, so it is invalidated
when new episodes are found (ensuring new PDFs are always fetched).

PDFs are never committed to the repo — they live only in the runner cache.
The cache is automatically evicted after 7 days of disuse.

---

## Manual triggers

**Actions → Update transcript data → Run workflow**

There is a **"Force full rebuild"** checkbox. Use this if:
- You updated a parser regex (e.g. the FILENAME_RE fix)
- You suspect some episodes were parsed incorrectly
- The `parsed_episodes.json` cache is out of sync

A full rebuild re-parses all ~800 PDFs from scratch. It takes longer
(~5-10 minutes) but the result is authoritative.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| "No new episodes found" every week | Cache hit on all PDFs; check if maximumfun.org actually has new transcripts |
| Workflow fails on `git push` | Workflow permissions not set to read/write (step 3) |
| Some episodes missing from indexes | FILENAME_RE didn't match — check the parse logs for `SKIP` lines |
| Index files didn't update | Check `git diff` step output — may already be up to date |
| `parsed_episodes.json` grows unboundedly | Normal — it accumulates all episodes. Not committed, so no repo impact. |
