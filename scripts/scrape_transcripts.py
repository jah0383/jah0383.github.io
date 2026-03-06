"""
scrape_transcripts.py
─────────────────────
Scrapes MBMBaM transcript PDFs from maximumfun.org.

Steps:
  1. Pages through the transcript listing to collect all episode URLs.
  2. Filters out non-MBMBaM entries (Adventure Zone, etc.).
  3. Visits each episode page, finds the PDF download link.
  4. Downloads the PDF, skipping files that already exist.

Usage:
    python scrape_transcripts.py
    python scrape_transcripts.py --output ./pdfs
    python scrape_transcripts.py --output ./pdfs --delay 1.5
    python scrape_transcripts.py --dry-run        # list URLs without downloading

Dependencies:
    pip install requests beautifulsoup4
"""

import re
import time
import argparse
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ── Config ────────────────────────────────────────────────────────────────────

LISTING_URL  = 'https://maximumfun.org/transcripts/my-brother-my-brother-and-me/'
HEADERS      = {'User-Agent': 'Mozilla/5.0 (compatible; MBMBaM-transcript-scraper/1.0)'}

# Titles containing any of these are NOT MBMBaM and will be skipped.
# Everything else on the MBMBaM listing page is assumed to be MBMBaM.
# Add to this list if other shows start appearing in the feed.
NON_MBMBAM = [
    'adventure zone',
    'judge john hodgman',
    'still buffering',
    'sawbones',
    'shmanners',
    'wonderful!',
    'young people',
    'feed drop',
    'minority korner'
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def get(url: str, session: requests.Session, retries: int = 3) -> requests.Response | None:
    for attempt in range(retries):
        try:
            r = session.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f'  ✗ Failed after {retries} attempts: {url} — {e}')
                return None


def is_mbmbam(title: str) -> bool:
    """
    Assume everything on the MBMBaM listing page is MBMBaM unless the title
    contains a known marker for another show.
    """
    t = title.lower()
    return not any(marker in t for marker in NON_MBMBAM)


# ── Step 1: Collect episode page URLs from listing ────────────────────────────

def collect_episode_urls(session: requests.Session) -> list[dict]:
    """
    Pages through the transcript listing and returns all MBMBaM entries
    as a list of {title, url} dicts.

    Tries common WordPress pagination patterns (?page=N and ?paged=N).
    Stops when a page returns no new episode links or returns a 404.
    """
    episodes = []
    seen_urls = set()
    page = 1

    while True:
        # Try both common WordPress pagination params
        url = LISTING_URL if page == 1 else f'{LISTING_URL}?_paged={page}'
        print(f'  Listing page {page}: {url}')

        r = get(url, session)
        if r is None:
            break

        soup = BeautifulSoup(r.text, 'html.parser')

        # Episode links are <h4> or <h3> anchors inside article/li elements.
        # More robustly: find all links whose href is under the transcript path
        # and whose text looks like an episode title.
        new_this_page = 0
        for a in soup.find_all('a', href=True):
            href = a['href']
            # Must be a transcript sub-page (not the listing itself)
            if '/transcripts/my-brother-my-brother-and-me/' not in href:
                continue
            if href.rstrip('/') == LISTING_URL.rstrip('/'):
                continue
            if href in seen_urls:
                continue

            title_text = a.get_text(strip=True)
            # Skip navigation links (← Previous, → Next, image-only links)
            if len(title_text) < 8:
                continue
            # Skip "← Previous" / "→ Next" navigation
            if any(s in title_text for s in ['←', '→', 'Previous', 'Next']):
                continue

            seen_urls.add(href)

            if is_mbmbam(title_text):
                episodes.append({'title': title_text, 'url': href})
                new_this_page += 1
            else:
                print(f'    skip (not MBMBaM): {title_text[:60]}')

        if new_this_page == 0:
            print(f'  No new episodes on page {page}, stopping.')
            break

        print(f'  Found {new_this_page} MBMBaM episodes on page {page}')
        page += 1
        time.sleep(0.5)

    return episodes


# ── Step 2: Find PDF URL on an episode page ───────────────────────────────────

PDF_RE = re.compile(r'\.pdf(\?|$)', re.IGNORECASE)

def find_pdf_url(episode_url: str, session: requests.Session) -> str | None:
    r = get(episode_url, session)
    if r is None:
        return None
    soup = BeautifulSoup(r.text, 'html.parser')

    # Look for anchor tags whose href ends in .pdf
    for a in soup.find_all('a', href=True):
        href = a['href']
        if PDF_RE.search(href):
            # Make absolute if relative
            return urljoin(episode_url, href)
    return None


# ── Step 3: Download PDF ──────────────────────────────────────────────────────

def download_pdf(pdf_url: str, dest: Path, session: requests.Session) -> bool:
    try:
        r = session.get(pdf_url, headers=HEADERS, timeout=60, stream=True)
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
        description='Download MBMBaM transcript PDFs from maximumfun.org.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--output', type=Path, default=Path('./pdfs'),
                        help='Directory to save PDFs into')
    parser.add_argument('--delay', type=float, default=1.0,
                        help='Seconds to wait between PDF downloads (be polite)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Discover and list URLs without downloading anything')
    args = parser.parse_args()

    if not args.dry_run:
        args.output.mkdir(parents=True, exist_ok=True)

    session = requests.Session()

    # ── Step 1: collect all episode page URLs
    print('─' * 60)
    print('Step 1: Collecting episode list…')
    print('─' * 60)
    episodes = collect_episode_urls(session)
    print(f'\nFound {len(episodes)} MBMBaM episodes total.\n')

    if not episodes:
        print('Nothing to download.')
        return

    if args.dry_run:
        print('Dry run — episode URLs:')
        for ep in episodes:
            print(f'  {ep["title"]}')
            print(f'    {ep["url"]}')
        return

    # ── Step 2 + 3: for each episode, find PDF and download
    print('─' * 60)
    print('Step 2: Downloading PDFs…')
    print('─' * 60)

    downloaded = skipped = failed = 0

    for i, ep in enumerate(episodes, 1):
        title  = ep['title']
        ep_url = ep['url']
        print(f'\n[{i}/{len(episodes)}] {title}')

        # Find PDF URL
        pdf_url = find_pdf_url(ep_url, session)
        if not pdf_url:
            print(f'  ✗ No PDF link found on page')
            failed += 1
            continue

        # Derive filename from PDF URL (preserves the original name)
        filename = pdf_url.split('/')[-1].split('?')[0]
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
        dest = args.output / filename

        if dest.exists():
            print(f'  ↷ Already exists: {filename}')
            skipped += 1
            continue

        print(f'  ↓ {filename}')
        ok = download_pdf(pdf_url, dest, session)
        if ok:
            size_kb = dest.stat().st_size / 1024
            print(f'    ✓ {size_kb:.0f} KB')
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