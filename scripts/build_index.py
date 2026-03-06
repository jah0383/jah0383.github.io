"""
build_index.py
──────────────
Stage 2 of the MBMBaM stats pipeline.

Consumes parsed_episodes.json and writes into --output-dir:

    manifest.json       — speakers, episode count, episode metadata
    episode_stats.json  — per-episode per-speaker word counts + top words
    word_index.json     — unigram     → speaker → {ep_id: count}
    bigram_index.json   — "w1 w2"    → speaker → {ep_id: count}  (trimmed)
    trigram_index.json  — "w1 w2 w3" → speaker → {ep_id: count}  (trimmed)
    stage_index.json    — "[direction]" → speaker → {ep_id: count} (all kept)

Trimming keeps file sizes manageable:
    Unigrams:           ~30-70 MB  (all kept)
    Bigrams  (min 5):   ~20-40 MB
    Trigrams (min 10):  ~10-25 MB

Usage:
    python build_index.py parsed_episodes.json
    python build_index.py parsed_episodes.json --min-bigram-count 3 --min-trigram-count 8
    python build_index.py parsed_episodes.json --search "bad idea blanket"
    python build_index.py parsed_episodes.json --search "bad idea" --search "travis"
    python build_index.py parsed_episodes.json --search-only "brother"

Dependencies: none (stdlib only)
"""

import re
import json
import argparse
from pathlib import Path
from collections import defaultdict


# -- Tokenizer -----------------------------------------------------------------

WORD_RE = re.compile(r"\b[a-z'][a-z']*\b")


def tokenize(text: str) -> list:
    # Normalize curly/smart apostrophes → straight apostrophe before matching.
    # PDFs frequently use U+2019 (') or U+2018 (') instead of U+0027 ('),
    # which causes "it's" to split into ["it", "s"] in bigrams etc.
    text = text.replace('’', "'").replace('‘', "'").replace('‟',"'")
    return WORD_RE.findall(text.lower())


def ngrams(tokens: list, n: int) -> list:
    """Return space-joined n-grams for a token list."""
    return [' '.join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


# -- Stopwords (used only for top-words stats, not search indexes) -------------

STOPWORDS = frozenset({
    'the', 'and', 'that', 'this', 'for', 'not', 'but', 'with', 'from',
    'into', 'about', 'over', 'after', 'before', 'between', 'through',
    'during', 'against', 'without',
    'you', 'its', 'they', 'them', 'their', 'we', 'us', 'he', 'she', 'me',
    'my', 'our', 'his', 'her', 'him', 'your', 'it',
    'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'did', 'does',
    'will', 'would', 'could', 'should', 'can', 'may', 'might', 'shall',
    'just', 'like', 'yeah', 'know', 'going', 'get', 'got', 'all', 'so',
    'if', 'as', 'by', 'at', 'to', 'in', 'of', 'on', 'or', 'an', 'up',
    'out', 'when', 'where', 'who', 'what', 'how', 'which', 'then', 'than',
    'more', 'some', 'very', 'also', 'even', 'too', 'right', 'because',
    'now', 'here', 'back', 'well', 'actually', 'kind', 'okay', 'want',
    'come', 'see', 'say', 'said', 'mean', 'way', 'time', 'think', 'really',
    'there', 'no', 'yes', 'oh', 'uh', 'um', 'gonna', 'gotta', 'wanna',
    'guys', 'man', 'hey', 'one', 'two', 'three',
    'im', 'dont', 'thats', 'ive', 'theyre', 'youre', 'cant', 'doesnt',
    'didnt', 'wasnt', 'isnt', 'arent', 'wouldnt', 'couldnt', 'shouldnt',
    'wont', 'hes', 'shes', 'weve', 'theyve', 'id', 'youd', 'hed',
    'shed', 'theyd', 'wed',
})


# -- Index builders ------------------------------------------------------------

def build_ngram_index(episodes: list, n: int, min_total_count: int = 1) -> dict:
    """
    Build an inverted n-gram index.

    Structure: {ngram_str: {speaker: {ep_id_str: count}}}

    n-grams with a total corpus count below min_total_count are dropped,
    which is the primary lever for controlling output file size.
    """
    raw = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for ep in episodes:
        ep_id = str(ep['id'])
        for utt in ep['utterances']:
            speaker = utt['speaker']
            tokens = tokenize(utt['text'])
            for gram in ngrams(tokens, n):
                raw[gram][speaker][ep_id] += 1

    if min_total_count <= 1:
        return {
            gram: {spk: dict(eps) for spk, eps in speakers.items()}
            for gram, speakers in raw.items()
        }

    result = {}
    for gram, speakers in raw.items():
        total = sum(
            count
            for eps in speakers.values()
            for count in eps.values()
        )
        if total >= min_total_count:
            result[gram] = {spk: dict(eps) for spk, eps in speakers.items()}
    return result



def build_vocabulary(episodes: list, speakers: list,
                     min_bigram: int = 5, min_trigram: int = 10) -> dict:
    """
    Build a compact vocabulary summary: total uses per speaker for every
    term in each category (word / bigram / trigram / stage).

    Format:
        {
          "speakers": ["Griffin", "Justin", "Travis"],
          "word":    [["hello", [g_count, j_count, t_count]], ...],  # sorted total desc
          "bigram":  [...],
          "trigram": [...],
          "stage":   [...]
        }

    Using positional arrays instead of {speaker: count} dicts reduces
    file size substantially (vocabulary.json is typically 5-15 MB vs
    50-100 MB for the full per-episode indexes).
    """
    # Accumulate totals: {term: {speaker: total_count}}
    cats = {
        'word':    defaultdict(lambda: defaultdict(int)),
        'bigram':  defaultdict(lambda: defaultdict(int)),
        'trigram': defaultdict(lambda: defaultdict(int)),
        'stage':   defaultdict(lambda: defaultdict(int)),
    }

    for ep in episodes:
        for utt in ep['utterances']:
            spk = utt['speaker']
            if spk not in speakers:
                continue
            tokens = tokenize(utt['text'])
            for gram in ngrams(tokens, 1):
                cats['word'][gram][spk] += 1
            for gram in ngrams(tokens, 2):
                cats['bigram'][gram][spk] += 1
            for gram in ngrams(tokens, 3):
                cats['trigram'][gram][spk] += 1
            for direction in utt.get('directions', []):
                key = f"[{direction.strip().lower()}]"
                cats['stage'][key][spk] += 1

    def to_sorted_list(counts: dict, min_total: int = 1) -> list:
        """Convert {term: {spk: n}} → [[term, [n, n, n]], ...] sorted by total desc."""
        out = []
        for term, spk_counts in counts.items():
            totals = [spk_counts.get(spk, 0) for spk in speakers]
            total = sum(totals)
            if total >= min_total:
                out.append([term, totals])
        out.sort(key=lambda x: sum(x[1]), reverse=True)
        return out

    return {
        'speakers': speakers,
        'word':    to_sorted_list(cats['word'],    min_total=1),
        'bigram':  to_sorted_list(cats['bigram'],  min_total=min_bigram),
        'trigram': to_sorted_list(cats['trigram'], min_total=min_trigram),
        'stage':   to_sorted_list(cats['stage'],   min_total=1),
    }


def build_episode_stats(episodes: list) -> list:
    stats = []
    for ep in episodes:
        speaker_data = defaultdict(lambda: {
            'total_words': 0,
            'word_freq': defaultdict(int),
        })
        for utt in ep['utterances']:
            spk = utt['speaker']
            words = tokenize(utt['text'])
            speaker_data[spk]['total_words'] += len(words)
            for w in words:
                if w not in STOPWORDS:
                    speaker_data[spk]['word_freq'][w] += 1

        speakers_out = {}
        for spk, data in speaker_data.items():
            top = sorted(data['word_freq'].items(), key=lambda x: x[1], reverse=True)[:50]
            speakers_out[spk] = {
                'total_words': data['total_words'],
                'top_words': dict(top),
            }

        stats.append({
            'id': ep['id'],
            'title': ep['title'],
            'date': ep.get('date'),
            'speakers': speakers_out,
        })
    return sorted(stats, key=lambda x: x['id'])


def build_manifest(episodes: list) -> dict:
    all_speakers = sorted({
        utt['speaker']
        for ep in episodes
        for utt in ep['utterances']
    })
    return {
        'speakers': all_speakers,
        'episode_count': len(episodes),
        'episodes': [
            {'id': ep['id'], 'title': ep['title'], 'date': ep.get('date')}
            for ep in sorted(episodes, key=lambda e: e['id'])
        ],
    }

def build_stage_index(episodes: list) -> dict:
    """
    Build an inverted index of inline stage directions.

    Keys are bracket-wrapped lowercase strings, e.g. "[laughs]", "[chortles]".
    Structure: {"[word]": {speaker: {ep_id_str: count}}}

    All directions are kept (no min-count trimming) — there are far fewer
    unique stage directions than words, so the file stays small (~1-5 MB).
    """
    raw = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for ep in episodes:
        ep_id = str(ep['id'])
        for utt in ep['utterances']:
            speaker = utt['speaker']
            for direction in utt.get('directions', []):
                # Normalise: lowercase, strip surrounding whitespace
                key = f"[{direction.strip().lower()}]"
                raw[key][speaker][ep_id] += 1

    return {
        key: {spk: dict(eps) for spk, eps in speakers.items()}
        for key, speakers in raw.items()
    }




# -- Helpers -------------------------------------------------------------------

def write_json(path: Path, data, indent=None) -> float:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    return path.stat().st_size / 1024 / 1024


# -- CLI phrase search ---------------------------------------------------------

def search_phrase(phrase: str, output_dir: Path, episodes: list) -> None:
    """
    Search a phrase (1-3 words) against the appropriate index file.
    Prints a per-speaker episode breakdown to stdout.
    """
    tokens = phrase.lower().split()
    n = len(tokens)

    if n == 0:
        print('  Empty phrase, skipping.')
        return
    if n > 3:
        print(f'  "{phrase}": only 1-3 word phrases are supported (index only covers unigrams, bigrams, trigrams).')
        return

    index_file = {
        1: output_dir / 'word_index.json',
        2: output_dir / 'bigram_index.json',
        3: output_dir / 'trigram_index.json',
    }[n]

    if not index_file.exists():
        print(f'  Index not found: {index_file}')
        print(f'  Run without --search-only to build first.')
        return

    print(f'  Loading {index_file.name} ...', end=' ', flush=True)
    with open(index_file, encoding='utf-8') as f:
        index = json.load(f)
    print('done.')

    key = ' '.join(tokens)
    entry = index.get(key)

    print(f'\n  Results for: "{key}"\n')

    if not entry:
        if n > 1:
            print(f'  Not found. This phrase may have been trimmed by the min-count filter.')
            print(f'  Try rebuilding with --min-bigram-count 1 or --min-trigram-count 1 to include rare phrases.')
        else:
            print('  Not found in any episode.')
        return

    ep_lookup = {str(ep['id']): ep for ep in episodes}
    speakers = sorted(entry.keys())

    print('  Totals:')
    grand_total = 0
    for spk in speakers:
        total = sum(entry[spk].values())
        grand_total += total
        print(f'    {spk:<14} {total:>6,}')
    print(f'    {"ALL":<14} {grand_total:>6,}')

    all_ep_ids = sorted(
        {ep_id for spk in speakers for ep_id in entry[spk]},
        key=lambda eid: sum(entry[spk].get(eid, 0) for spk in speakers),
        reverse=True,
    )

    col_w = 10
    print(f'\n  Top episodes (by total uses across all speakers):')
    header = f'  {"Ep":>4}  {"Title":<45}  ' + '  '.join(f'{s:<{col_w}}' for s in speakers) + '  Total'
    print(header)
    print('  ' + '-' * (len(header) - 2))

    for ep_id in all_ep_ids[:25]:
        ep = ep_lookup.get(ep_id, {})
        title = (ep.get('title') or '?')[:44]
        col_vals = [entry[spk].get(ep_id, 0) for spk in speakers]
        row_total = sum(col_vals)
        cols = '  '.join(f'{v:<{col_w}}' for v in col_vals)
        print(f'  {ep_id:>4}  {title:<45}  {cols}  {row_total}')

    if len(all_ep_ids) > 25:
        print(f'  ... ({len(all_ep_ids) - 25} more episodes with at least one use)')


# -- CLI -----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Build JSON indexes for the MBMBaM stats site.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'parsed_episodes', type=Path,
        help='Path to parsed_episodes.json from parse_transcripts.py',
    )
    parser.add_argument(
        '--output-dir', type=Path, default=Path('site/data'),
        help='Directory to write output JSON files',
    )
    parser.add_argument(
        '--min-bigram-count', type=int, default=5, metavar='N',
        help='Drop bigrams with fewer than N total uses across all episodes/speakers. '
             'Lower = bigger file, more rare phrases covered. Recommended range: 2-10.',
    )
    parser.add_argument(
        '--min-trigram-count', type=int, default=10, metavar='N',
        help='Drop trigrams with fewer than N total uses. Recommended range: 5-20.',
    )
    parser.add_argument(
        '--search', action='append', default=[], metavar='PHRASE',
        help='After building, search this phrase (1-3 words) and print results. '
             'Repeatable: --search "bad idea" --search "kiss your dad"',
    )
    parser.add_argument(
        '--search-only', action='append', default=[], metavar='PHRASE',
        help='Search phrase(s) WITHOUT rebuilding. Indexes must already exist.',
    )
    args = parser.parse_args()

    if not args.parsed_episodes.exists():
        parser.error(f'{args.parsed_episodes} not found')

    print(f'Loading {args.parsed_episodes} ...')
    with open(args.parsed_episodes, encoding='utf-8') as f:
        episodes = json.load(f)
    print(f'  {len(episodes)} episodes loaded\n')

    # Search-only mode
    if args.search_only and not args.search:
        print('Search-only mode (skipping rebuild)\n')
        for phrase in args.search_only:
            print('-' * 60)
            search_phrase(phrase, args.output_dir, episodes)
            print()
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # episode_stats.json
    print('Building episode stats ...')
    stats = build_episode_stats(episodes)
    mb = write_json(args.output_dir / 'episode_stats.json', stats)
    print(f'  -> episode_stats.json  ({mb:.1f} MB)\n')

    # manifest.json
    print('Building manifest ...')
    manifest = build_manifest(episodes)
    write_json(args.output_dir / 'manifest.json', manifest, indent=2)
    print(f'  -> manifest.json')
    print(f'  Speakers: {", ".join(manifest["speakers"])}\n')

    # word_index.json (unigrams)
    print('Building unigram index ...')
    uni = build_ngram_index(episodes, n=1, min_total_count=1)
    mb = write_json(args.output_dir / 'word_index.json', uni)
    print(f'  -> word_index.json  ({mb:.1f} MB)  ({len(uni):,} unique words)\n')

    # bigram_index.json
    print(f'Building bigram index (min total count = {args.min_bigram_count}) ...')
    bi = build_ngram_index(episodes, n=2, min_total_count=args.min_bigram_count)
    mb = write_json(args.output_dir / 'bigram_index.json', bi)
    print(f'  -> bigram_index.json  ({mb:.1f} MB)  ({len(bi):,} bigrams kept)\n')

    # trigram_index.json
    print(f'Building trigram index (min total count = {args.min_trigram_count}) ...')
    tri = build_ngram_index(episodes, n=3, min_total_count=args.min_trigram_count)
    mb = write_json(args.output_dir / 'trigram_index.json', tri)
    print(f'  -> trigram_index.json  ({mb:.1f} MB)  ({len(tri):,} trigrams kept)\n')

    # stage_index.json
    print('Building stage direction index ...')
    stage = build_stage_index(episodes)
    mb = write_json(args.output_dir / 'stage_index.json', stage)
    print(f'  -> stage_index.json  ({mb:.1f} MB)  ({len(stage):,} unique directions)\n')

    # vocabulary.json
    print('Building vocabulary summary ...')
    vocab = build_vocabulary(
        episodes,
        speakers=manifest['speakers'],
        min_bigram=args.min_bigram_count,
        min_trigram=args.min_trigram_count,
    )
    mb = write_json(args.output_dir / 'vocabulary.json', vocab)
    counts = {cat: len(vocab[cat]) for cat in ('word','bigram','trigram','stage')}
    print(f'  -> vocabulary.json  ({mb:.1f} MB)')
    print(f'     words={counts["word"]:,}  bigrams={counts["bigram"]:,}  trigrams={counts["trigram"]:,}  stage={counts["stage"]:,}\n')

    print('Done.\n')

    # Post-build phrase searches
    for phrase in (args.search + args.search_only):
        print('-' * 60)
        search_phrase(phrase, args.output_dir, episodes)
        print()


if __name__ == '__main__':
    main()
