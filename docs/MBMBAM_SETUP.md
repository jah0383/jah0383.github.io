# Setup Guide

This document covers one-time setup steps. The weekly auto-update runs on its
own after this is done.

---

## 1. Create a Dropbox App

You need a free Dropbox app to get API credentials. This does NOT need to be
the McElroy family's Dropbox — any account will work, since the folder is
public.

1. Go to **https://www.dropbox.com/developers/apps** and sign in.
2. Click **Create app**.
3. Choose:
   - API: **Scoped access**
   - Type of access: **Full Dropbox**
   - Name: anything (e.g. `mbmbam-transcripts`)
4. Click **Create app**.
5. On the app settings page, go to the **Permissions** tab and enable:
   - `files.metadata.read`
   - `files.content.read`
   - Click **Submit** to save permissions.
6. Go back to the **Settings** tab. Note down your:
   - **App key**
   - **App secret** (click "Show")

---

## 2. Get a Refresh Token

Dropbox no longer issues permanent access tokens. Instead you get a
**refresh token** which never expires, and the script exchanges it for a
short-lived access token on each run.

Getting a refresh token requires a one-time browser-based flow. Run this
in Python once on your local machine:

```python
import urllib.parse, webbrowser, requests

APP_KEY    = 'your_app_key_here'
APP_SECRET = 'your_app_secret_here'

# Step 1 — open the authorization URL in your browser
params = urllib.parse.urlencode({
    'client_id':          APP_KEY,
    'response_type':      'code',
    'token_access_type':  'offline',   # <-- this is what gets you a refresh token
})
url = f'https://www.dropbox.com/oauth2/authorize?{params}'
print(f'Opening: {url}')
webbrowser.open(url)

# Step 2 — paste the code shown in the browser after you authorize
auth_code = input('Paste the authorization code here: ').strip()

# Step 3 — exchange for tokens
r = requests.post(
    'https://api.dropbox.com/oauth2/token',
    data={
        'code':         auth_code,
        'grant_type':   'authorization_code',
        'client_id':    APP_KEY,
        'client_secret': APP_SECRET,
    },
)
r.raise_for_status()
data = r.json()
print(f'\nRefresh token: {data["refresh_token"]}')
```

Copy the refresh token printed at the end.

---

## 3. Add Secrets to GitHub

1. In your GitHub repo, go to **Settings → Secrets and variables → Actions**.
2. Click **New repository secret** for each of the following:

| Secret name             | Value                          |
|-------------------------|--------------------------------|
| `DROPBOX_APP_KEY`       | App key from step 1            |
| `DROPBOX_APP_SECRET`    | App secret from step 1         |
| `DROPBOX_REFRESH_TOKEN` | Refresh token from step 2      |

---

## 4. First Run

The first run after setup will parse all ~800 episodes from scratch, which
takes 10–20 minutes. After that, only new episodes are processed each week.

To trigger it manually:
1. Go to **Actions** in your repo.
2. Click **Update transcript data**.
3. Click **Run workflow**.

To force a full rebuild at any time, check the "Force full rebuild" box
before running.

---

## Repo Layout

```
repo/
├── .github/
│   └── workflows/
│       └── update-data.yml    # auto-update workflow
├── data/                      # committed — served directly to the site
│   ├── manifest.json
│   ├── episode_stats.json
│   ├── word_index.json
│   ├── bigram_index.json
│   ├── trigram_index.json
│   ├── stage_index.json
│   └── vocabulary.json
├── scripts/
│   ├── requirements.txt
│   ├── scrape_transcripts.py  # downloads PDFs from Dropbox
│   ├── parse_transcripts.py   # PDF → JSON
│   └── build_index.py         # JSON → search indexes
└── index.html                 # the site
```

`pdfs/` and `parsed_episodes.json` are never committed — they live only in the
GitHub Actions runner cache between runs.

---

## Troubleshooting

**"Missing Dropbox credentials" error**
The three secrets aren't set, or the workflow isn't passing them as env vars.
Check Settings → Secrets and verify all three names match exactly.

**"401 Unauthorized" from Dropbox**
The refresh token or app credentials are wrong. Re-run the Python snippet in
step 2 to get a fresh token.

**"400 Bad Request" on list_folder**
The shared folder URL may have changed. Check whether the Dropbox link in
`scrape_transcripts.py` (`SHARED_FOLDER_URL`) still works in a browser.

**No PDFs found / 0 matching files**
The filename pattern changed. Check a few filenames manually via the Dropbox
web UI and compare against `MBMBAM_PDF_RE` in `scrape_transcripts.py`.