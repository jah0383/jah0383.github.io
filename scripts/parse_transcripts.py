"""
scrape_transcripts.py
─────────────────────
Downloads MBMBaM transcript PDFs from the official McElroy Dropbox folder.

The folder is public but listing its contents requires a Dropbox API access
token (any Dropbox account's token will do — you don't need to own the folder).
See SETUP.md for instructions on getting one.

Steps:
  1. Exchange refresh token + app credentials for a short-lived access token.
  2. List all files in the shared Dropbox folder via the API.
  3. Filter to PDFs that look like MBMBaM transcripts.
  4. Download any that don't already exist locally.

Credentials are read from environment variables (set as GitHub Actions secrets):
  DROPBOX_APP_KEY       — your Dropbox app's key
  DROPBOX_APP_SECRET    — your Dropbox app's secret
  DROPBOX_REFRESH_TOKEN — offline refresh token obtained during setup

Usage:
    python scrape_transcripts.py
    python scrape_transcripts.py --output ./pdfs
    python scrape_transcripts.py --dry-run     # list files without downloading
    python scrape_transcripts.py --delay 0.5   # seconds between downloads

Dependencies:
    pip install requests
"""

import os
import re
import time
import argparse
from pathlib import Path

import requests


# ── Config ────────────────────────────────────────────────────────────────────

# The public shared-folder URL (the MBMBaM subfolder specifically).
# This is the URL you were given — do not change it.
SHARED_FOLDER_URL = (
    'https://www.dropbox.com/sh/egqdua6s38oxb9p/'
    'AADFJKcNCRliMD-rF89mZB2Fa/MBMBaM?dl=0'
)

DROPBOX_TOKEN_URL  = 'https://api.dropbox.com/oauth2/token'
DROPBOX_LIST_URL   = 'https://api.dropboxapi.com/2/files/list_folder'
DROPBOX_LIST_CONT  = 'https://api.dropboxapi.com/2/files/list_folder/continue'
DROPBOX_DL_URL     = 'https://content.dropboxapi.com/2/sharing/get_shared_link_file'

# Matches the MBMBaM transcript filename pattern, including the known 'Eo' typo.
# Examples this handles:
#   MBMBaM Ep002 Holding a Stranger's Hand.pdf
#   MBMBaM Eo246 Face 2 Face Hot Beans.pdf     ← typo: Eo instead of Ep
#   MBMBaM Ep91 Feeding Frenzy.pdf             ← no zero-padding
#   MBMBaM Ep665 Face 2 Face Cody-Pendant.pdf
MBMBAM_PDF_RE = re.compile(
    r'^MBMBaM\s+E[oOpP](\d+)\s+.+\.pdf$',
    re.IGNORECASE,
)


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_access_token(app_key: str, app_secret: str, refresh_token: str) -> str:
    """
    Exchange a refresh token for a short-lived access token.
    Dropbox deprecated permanent tokens in 2021; this is the correct approach.
    The refresh token itself never expires (unless you revoke it).
    """
    r = requests.post(
        DROPBOX_TOKEN_URL,
        data={
            'grant_type':    'refresh_token',
            'refresh_token': refresh_token,
            'client_id':     app_key,
            'client_secret': app_secret,
        },
        timeout=30,
    )
    r.raise_for_status()
    token = r.json().get('access_token')
    if not token:
        raise RuntimeError(f'No access_token in response: {r.json()}')
    return token


# ── List folder ───────────────────────────────────────────────────────────────

def list_folder(access_token: str) -> list[dict]:
    """
    Returns all file entries in the shared Dropbox folder.
    Handles pagination automatically (Dropbox caps each page at 2000 entries).
    Each entry is a Dropbox file metadata dict; we care about 'name' and '.tag'.
    """
    headers = {'Authorization': f'Bearer {access_token}'}

    # Initial request — path="" means "the root of the shared link"
    payload = {
        'path':        '',
        'shared_link': {'url': SHARED_FOLDER_URL},
        'recursive':   False,
        'limit':       2000,
    }
    r = requests.post(DROPBOX_LIST_URL, json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    data = r.json()

    entries = data.get('entries', [])
    cursor  = data.get('cursor')
    has_more = data.get('has_more', False)

    # Paginate if there are more entries
    while has_more and cursor:
        r = requests.post(
            DROPBOX_LIST_CONT,
            json={'cursor': cursor},
            headers=headers,
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        entries.extend(data.get('entries', []))
        cursor   = data.get('cursor')
        has_more = data.get('has_more', False)

    return entries


# ── Download ──────────────────────────────────────────────────────────────────

def download_pdf(
    filename: str,
    dest: Path,
    access_token: str,
    session: requests.Session,
) -> bool:
    """
    Download a single PDF from the shared folder via the Dropbox content API.
    The 'path' in the API arg is relative to the shared folder root.
    """
    import json

    api_arg = json.dumps({
        'url':  SHARED_FOLDER_URL,
        'path': f'/{filename}',
    })
    headers = {
        'Authorization':   f'Bearer {access_token}',
        'Dropbox-API-Arg': api_arg,
    }
    try:
        r = session.post(DROPBOX_DL_URL, headers=headers, timeout=120, stream=True)
        r.raise_for_status()
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        return True
    except requests.RequestException as e:
        print(f'    ✗ Download failed: {e}')
        if dest.exists():
            dest.unlink()
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Download MBMBaM transcript PDFs from the McElroy Dropbox.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--output',  type=Path, default=Path('./pdfs'),
                        help='Directory to save PDFs into')
    parser.add_argument('--delay',   type=float, default=0.5,
                        help='Seconds to wait between downloads')
    parser.add_argument('--dry-run', action='store_true',
                        help='List files without downloading anything')
    args = parser.parse_args()

    # ── Credentials from environment
    app_key       = os.environ.get('DROPBOX_APP_KEY')
    app_secret    = os.environ.get('DROPBOX_APP_SECRET')
    refresh_token = os.environ.get('DROPBOX_REFRESH_TOKEN')

    if not all([app_key, app_secret, refresh_token]):
        raise SystemExit(
            'Missing Dropbox credentials.\n'
            'Set DROPBOX_APP_KEY, DROPBOX_APP_SECRET, and DROPBOX_REFRESH_TOKEN '
            'as environment variables.\n'
            'See SETUP.md for instructions.'
        )

    if not args.dry_run:
        args.output.mkdir(parents=True, exist_ok=True)

    # ── Step 1: auth
    print('─' * 60)
    print('Step 1: Authenticating with Dropbox…')
    access_token = get_access_token(app_key, app_secret, refresh_token)
    print('  ✓ Got access token')

    # ── Step 2: list folder
    print('─' * 60)
    print('Step 2: Listing folder contents…')
    all_entries = list_folder(access_token)

    # Filter to MBMBaM PDFs only
    pdfs = [
        e for e in all_entries
        if e.get('.tag') == 'file' and MBMBAM_PDF_RE.match(e['name'])
    ]
    # Sort by episode number for tidy output
    def ep_num(entry):
        m = MBMBAM_PDF_RE.match(entry['name'])
        return int(m.group(1)) if m else 0
    pdfs.sort(key=ep_num)

    non_pdf = len(all_entries) - len(pdfs)
    print(f'  Found {len(all_entries)} total entries, '
          f'{len(pdfs)} MBMBaM PDFs, {non_pdf} skipped (non-matching)')

    if not pdfs:
        print('Nothing to download.')
        return

    if args.dry_run:
        print('\nDry run — matching files:')
        for e in pdfs:
            print(f"  {e['name']}")
        return

    # ── Step 3: download new files
    print('─' * 60)
    print('Step 3: Downloading new PDFs…')

    session = requests.Session()
    downloaded = skipped = failed = 0

    for i, entry in enumerate(pdfs, 1):
        filename = entry['name']
        dest     = args.output / filename

        print(f'\n[{i}/{len(pdfs)}] {filename}')

        if dest.exists():
            print(f'  ↷ Already exists — skipping')
            skipped += 1
            continue

        print(f'  ↓ Downloading…')
        ok = download_pdf(filename, dest, access_token, session)
        if ok:
            size_kb = dest.stat().st_size / 1024
            print(f'  ✓ {size_kb:.0f} KB')
            downloaded += 1
        else:
            failed += 1

        time.sleep(args.delay)

    # ── Summary
    print('\n' + '─' * 60)
    print(f'Done.')
    print(f'  Downloaded : {downloaded}')
    print(f'  Skipped    : {skipped} (already existed)')
    print(f'  Failed     : {failed}')
    print(f'  Output dir : {args.output.resolve()}')


if __name__ == '__main__':
    main()