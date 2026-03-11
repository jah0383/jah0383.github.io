"""
parse_transcripts.py
────────────────────
Stage 1 of the MBMBaM stats pipeline.

Reads a directory of PDF transcripts (just drop them all in one folder)
and outputs parsed_episodes.json with structured utterances per episode.

Episode number, title, and date are extracted from the PDF text itself.
Expected header on page 1:

    MBMBaM 801: Bad Idea Blanket
    Published on February 16th, 2026

Filename is used as a fallback for episode number/title only if the PDF
header can't be parsed (handy for very old or oddly formatted episodes).

Usage:
    python parse_transcripts.py ./pdfs
    python parse_transcripts.py ./pdfs --output data/parsed.json
    python parse_transcripts.py ./pdfs --speakers Justin Travis Griffin Bob

Dependencies:
    pip install pdfplumber
"""

import re
import json
import argparse
from pathlib import Path
from typing import Optional

import pdfplumber


# ── Regexes ───────────────────────────────────────────────────────────────────

# PDF page-1 header: "MBMBaM 801: Bad Idea Blanket"
# Also tolerates: "My Brother, My Brother and Me 42: ..."
HEADER_RE = re.compile(
    r'(?:MBMBaM|My Brother[^:\n]{0,40}?)\s+(\d+)\s*:\s*(.+)',
    re.IGNORECASE,
)

# Fallback: episode number + title from filename
# Matches: MBMBaM-Ep801-Bad-Idea-Blanket.pdf  /  ep42-title.pdf
FILENAME_RE = re.compile(r'mbmbam e[po](\d+)\s(.*)\.pdf',re.IGNORECASE)

# "Published on February 16th, 2026"
DATE_RE = re.compile(
    r'Published on\s+([A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?,?\s*\d{4})',
    re.IGNORECASE,
)

# Speaker turn: "Name:" or "Name Name:" at line start.
# Also handles character roles: "Justin [as Richard Stink]: ..."
# Group 1: speaker name   Group 2: optional role (may be None)   Group 3: rest of line
SPEAKER_RE = re.compile(
    r'^([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)'   # speaker name
    r'(?:\s*\[[Aa]s\s+([^\]]+)\])?'           # optional [as Character Name]
    r'\s*:\s*(.*)'                          # colon + rest of line
)

# Entire line is a stage direction, e.g. [theme song plays]
STAGE_LINE_RE = re.compile(r'^\[.*\]$')

# Inline stage direction: [laughs], [sings], etc.
INLINE_STAGE_RE = re.compile(r'\[.*?\]')



# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_pdf_header(text: str) -> Optional[dict]:
    """
    Extract episode number and title from the PDF's own page-1 header.
    Only searches the first 500 characters to avoid false matches in transcript body.
    """
    snippet = text[:500]
    m = HEADER_RE.search(snippet)
    if not m:
        return None
    return {
        'episode': int(m.group(1)),
        'title':   m.group(2).strip(),
    }


def parse_filename_fallback(filename: str) -> Optional[dict]:
    """Fallback: extract episode number and title from the PDF filename."""
    m = FILENAME_RE.search(filename)
    if not m:
        return None
    return {
        'episode': int(m.group(1)),
        'title':   m.group(2).replace('-', ' ').replace('_', ' ').title(),
    }


def extract_pdf_text(path: Path) -> str:
    """Extract all text from a PDF, joining pages with newlines."""
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return '\n'.join(pages)


def parse_date(text: str) -> Optional[str]:
    """Extract publication date from PDF text."""
    m = DATE_RE.search(text)
    return m.group(1) if m else None


def parse_utterances(text: str, known_speakers: set) -> list:
    """
    Parse speaker turns from raw transcript text.

    Rules:
    - A line matching SPEAKER_RE where the name is in known_speakers
      (or known_speakers is empty for permissive mode) starts a new turn.
    - Pure stage-direction lines ([...]) are skipped entirely.
    - Inline stage directions are captured into 'directions' then stripped from 'text'.
    - Continuation lines are appended to the current turn.
    - Lines before the first recognised speaker are skipped.

    Returns a list of dicts: {'speaker': str, 'text': str, 'directions': list[str]}
    Directions are lowercase strings WITHOUT brackets, e.g. 'laughs', 'chortles'.
    The index builder will prefix them with brackets when indexing.
    """
    utterances = []
    current_speaker    = None
    current_tokens     = []
    current_directions = []

    def flush():
        if current_speaker and (current_tokens or current_directions):
            utterances.append({
                'speaker':    current_speaker,
                'text':       ' '.join(current_tokens),
                'directions': current_directions[:],
            })

    def capture_directions(s: str) -> list:
        return [m.lower() for m in re.findall(r'\[([^\]]+)\]', s)]

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if STAGE_LINE_RE.match(line):
            continue

        m = SPEAKER_RE.match(line)
        if m:
            candidate = m.group(1)
            if (not known_speakers) or (candidate in known_speakers):
                flush()
                current_speaker = candidate
                rest_raw        = m.group(3)

                # Pre-colon format: "Justin [as Richard Stink]: text"
                # Group 2 holds the role — prepend it as a bracketed token so
                # capture_directions and INLINE_STAGE_RE treat it like [laughs].
                if m.group(2):
                    rest_raw = f'[as {m.group(2).strip()}] {rest_raw}'

                current_directions = capture_directions(rest_raw)
                rest = INLINE_STAGE_RE.sub('', rest_raw).strip()
                current_tokens     = [rest] if rest else []
                continue

        if current_speaker:
            current_directions.extend(capture_directions(line))
            clean = INLINE_STAGE_RE.sub('', line).strip()
            if clean:
                current_tokens.append(clean)

    flush()
    return utterances


# ── Main processing ───────────────────────────────────────────────────────────

def process_directory(pdf_dir: Path, known_speakers: set, skip_ids: set[int] | None = None) -> list:
    skip_ids = skip_ids or set()
    """
    Process every .pdf in pdf_dir (non-recursive).
    Returns a list of episode dicts sorted by episode number.
    """
    pdf_paths = sorted(pdf_dir.glob('*.pdf'))
    if not pdf_paths:
        print(f'No PDFs found in {pdf_dir}')
        return []

    episodes   = []
    skipped    = 0
    no_filename  = 0

    for pdf_path in pdf_paths:
        # Fast pre-check: if we can determine the episode ID from the filename
        # before parsing the PDF, skip early to avoid loading it at all.
        if skip_ids:
            quick_meta = parse_filename_fallback(pdf_path.name)
            if quick_meta and quick_meta['episode'] in skip_ids:
                print(f'  {pdf_path.name[:60]:<60} already parsed, skipping')
                continue
        print(f'  {pdf_path.name[:60]:<60}', end=' ', flush=True)
        try:
            text = extract_pdf_text(pdf_path)

            # Try PDF header first, fall back to filename
            meta = parse_filename_fallback(pdf_path.name)
            source = "filename"
            if not meta:
                meta = parse_pdf_header(text)
                source = 'pdf'
                no_filename += 1

            if not meta:
                print('SKIP (no episode number found in PDF or filename)')
                skipped += 1
                continue

            # Also skip if this episode ID is already in the existing data
            # (catches cases where filename parse failed but PDF header worked)
            if meta['episode'] in skip_ids:
                print(f'already parsed, skipping')
                continue

            date       = parse_date(text)
            utterances = parse_utterances(text, known_speakers)

            episodes.append({
                'id':        meta['episode'],
                'title':     meta['title'],
                'filename':  pdf_path.name,
                'date':      date,
                'utterances': utterances,
            })
            flag = '' if source == 'pdf' else ' [filename fallback]'
            print(f'Ep {meta["episode"]:>4} | {len(utterances):>4} utterances{flag}')

        except Exception as exc:
            print(f'ERROR: {exc}')
            skipped += 1

    episodes.sort(key=lambda ep: ep['id'])

    print(f'\nProcessed : {len(episodes)} episodes')
    if no_filename:
        print(f'  Fallback : {no_filename} used filename (no PDF header match)')
    if skipped:
        print(f'  Skipped  : {skipped}')
    print(f'Utterances: {sum(len(ep["utterances"]) for ep in episodes):,} total')
    return episodes


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Parse MBMBaM transcript PDFs into structured JSON.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('pdf_dir', type=Path, help='Folder containing PDF files')
    parser.add_argument(
        '--output', type=Path, default=Path('parsed_episodes.json'),
        help='Output JSON path',
    )
    parser.add_argument(
        '--speakers', nargs='+',
        default=['Justin', 'Travis', 'Griffin'],
        help='Recognised speaker names. Add guests if needed.',
    )
    parser.add_argument(
        '--incremental', action='store_true',
        help=(
            'Load existing --output JSON and skip PDFs whose episode ID is '
            'already present. New episodes are appended and the file is '
            're-sorted. Useful for CI runs where most PDFs are unchanged.'
        ),
    )
    args = parser.parse_args()

    if not args.pdf_dir.is_dir():
        parser.error(f'{args.pdf_dir} is not a directory')

    # ── Incremental: load existing episodes, build skip-set ──────────────────
    existing_episodes: list = []
    skip_ids: set[int] = set()
    if args.incremental and args.output.exists():
        try:
            with open(args.output, encoding='utf-8') as f:
                existing_episodes = json.load(f)
            skip_ids = {ep['id'] for ep in existing_episodes}
            print(f'Incremental mode: {len(skip_ids)} episodes already in {args.output}')
        except Exception as e:
            print(f'Warning: could not load existing output ({e}), doing full parse.')
            existing_episodes = []
            skip_ids = set()

    print(f'Scanning: {args.pdf_dir}')
    print(f'Speakers: {", ".join(args.speakers)}\n')

    new_episodes = process_directory(args.pdf_dir, set(args.speakers), skip_ids=skip_ids)

    if args.incremental and existing_episodes:
        if not new_episodes:
            print('No new episodes found — nothing to update.')
            return
        print(f'\nMerging {len(new_episodes)} new + {len(existing_episodes)} existing episodes.')
        episodes = existing_episodes + new_episodes
        episodes.sort(key=lambda ep: ep['id'])
    else:
        episodes = new_episodes

    if not episodes:
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(episodes, f, ensure_ascii=False, indent=2)

    size_kb = args.output.stat().st_size / 1024
    print(f'\n→ {args.output}  ({size_kb:.0f} KB)')


if __name__ == '__main__':
    main()