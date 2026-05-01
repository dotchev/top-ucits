#!/usr/bin/env python3
"""Look up Yahoo Finance symbols for ETFs by ISIN.

Reads INPUT csv (cols: isin,ticker,name), writes OUTPUT csv (cols: isin,
symbol, name). Uses yahoo-symbol-cache.csv as a persistent cache: each
new lookup is appended to the cache and saved immediately, so re-running
the script reuses cached results and only calls Yahoo for uncached ISINs.

Usage:
    python3 yahoo_lookup.py
    python3 yahoo_lookup.py --input X --output Y --cache C

Algorithm (see yahoo-lookup.md):
  1. Search Yahoo for "<ticker>.DE"; pick first listing whose symbol == "<ticker>.DE".
  2. Search Yahoo for ISIN; pick a .DE listing if present.
  3. Take longname (or shortname) of the first listing from step 2, search by it,
     filter results to those whose longname/shortname equals the query,
     priority pick (.DE > .MI > .AS > .PA > .SW > .MC).
  4. Apply the same priority pick to step 2's results.
  5. Pick the first listing from step 2's results.
  6. Search Yahoo for the CSV name; priority pick.

Only quotes with quoteType in (ETF, EQUITY) are considered.
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request

INPUT_DEFAULT = os.path.join(os.path.dirname(__file__), 'justetf-top-3y-rr.csv')
OUTPUT_DEFAULT = os.path.join(os.path.dirname(__file__), 'yahoo-top-3y-rr.csv')
CACHE_DEFAULT = os.path.join(os.path.dirname(__file__), 'yahoo-symbol-cache.csv')

PRIORITY = ['.DE', '.MI', '.AS', '.PA', '.SW', '.MC']
CACHE_FIELDS = ['isin', 'ticker', 'name', 'yahoo_symbol', 'yahoo_name']
OUTPUT_FIELDS = ['isin', 'symbol', 'name']
SEARCH_URL = 'https://query2.finance.yahoo.com/v1/finance/search'


def yahoo_search(q):
    time.sleep(1 + random.random()) # seconds to sleep between API calls to avoid rate limits
    url = f'{SEARCH_URL}?q={urllib.parse.quote(q)}&quotesCount=20&newsCount=0&listsCount=0'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


ALLOWED_QUOTE_TYPES = {'ETF', 'EQUITY'}


def _listings(data):
    return [q for q in data.get('quotes', [])
            if q.get('quoteType') in ALLOWED_QUOTE_TYPES and q.get('symbol')]


def _search_listings(query):
    if not query:
        return []
    try:
        data = yahoo_search(query)
    except Exception:
        return []
    return _listings(data)


def _yahoo_name(q):
    return q.get('longname') or q.get('shortname') or ''


_CCY_RE = re.compile(r'\b(eur|usd|gbp|chf|jpy|cad|aud)\b')
_CLASS_NOISE = re.compile(r'[^a-z0-9]+')
_LEVERAGE_RE = re.compile(r'(\d+)x\b')

# Tokens that aren't useful for theme comparison (wrappers, issuers, share-class markers).
_THEME_NOISE = {
    'ucits', 'etf', 'etfs', 'fund', 'funds', 'class', 'share', 'shares',
    'dist', 'distributing', 'distribution', 'distr', 'dis',
    'acc', 'accumulation', 'accumulating', 'income', 'inc',
    'eur', 'usd', 'gbp', 'chf', 'jpy', 'cad', 'aud',
    'a', 'b', 'c', 'd', 'r', '1c', '1d', '2c', '2d', '3c', '3d',
    'plc', 'icav', 'ireland', 'luxembourg', 'multi', 'units',
    'index', 'indices', 'solutions', 'solution', 'public', 'limited',
    'company', 'the', 'of', 'and', 'an', 'de', 'ie', 'lu', 'fr',
    'hedged', 'hedge', 'unhedged',
    'ishares', 'xtrackers', 'amundi', 'invesco', 'jpmorgan', 'jpm',
    'spdr', 'state', 'street', 'pimco', 'franklin', 'vaneck',
    'wisdomtree', 'hsbc', 'ubs', 'bnp', 'paribas', 'easy', 'deka',
    'expat', 'first', 'trust', 'lyxor', 'globalx', 'global', 'x',
    'leverage', 'etp', 'vii', 'viii', 'iii', 'iv', 'vi',
}


def _share_class(s):
    """Return 'A' (acc), 'D' (dist), or None if unspecified/ambiguous."""
    padded = ' ' + re.sub(_CLASS_NOISE, ' ', s.lower()) + ' '
    has_acc = bool(re.search(r' (acc|accumulating|accumulation|1c|2c|3c) ', padded))
    has_dist = bool(re.search(r' (dist|distr|distributing|distribution|1d|2d|3d) ', padded))
    if has_acc and not has_dist:
        return 'A'
    if has_dist and not has_acc:
        return 'D'
    return None


def _currencies(s):
    s = s.lower().replace('€', ' eur ').replace('$', ' usd ').replace('£', ' gbp ')
    return set(_CCY_RE.findall(s))


def _theme_tokens(s):
    s = s.lower().replace('€', ' eur ').replace('$', ' usd ').replace('£', ' gbp ')
    tokens = re.findall(r'[a-z0-9]+', s)
    return {t for t in tokens if len(t) > 1 and t not in _THEME_NOISE}


def is_obvious_mismatch(input_name, yahoo_name):
    """True if the two names clearly refer to different funds.

    Conservative — only flags share-class, currency, leverage, or
    completely-disjoint theme tokens. Returns False on ambiguous cases.
    """
    if not input_name or not yahoo_name:
        return False
    a, b = _share_class(input_name), _share_class(yahoo_name)
    if a and b and a != b:
        print(f'share class mismatch: "{input_name}" vs "{yahoo_name}"', file=sys.stderr)
        return True
    ca, cb = _currencies(input_name), _currencies(yahoo_name)
    if ca and cb and ca.isdisjoint(cb):
        print(f'currency mismatch: "{input_name}" vs "{yahoo_name}"', file=sys.stderr)
        return True
    la = set(_LEVERAGE_RE.findall(input_name.lower()))
    lb = set(_LEVERAGE_RE.findall(yahoo_name.lower()))
    if la and lb and la != lb:
        print(f'leverage mismatch: "{input_name}" vs "{yahoo_name}"', file=sys.stderr)
        return True
    ta, tb = _theme_tokens(input_name), _theme_tokens(yahoo_name)
    if len(ta) >= 3 and len(tb) >= 1 and ta.isdisjoint(tb):
        print(f'theme mismatch: "{input_name}" vs "{yahoo_name}"', file=sys.stderr)
        return True
    return False


def _drop_obvious_mismatches(quotes, input_name):
    if not input_name:
        return quotes
    return [q for q in quotes if not is_obvious_mismatch(input_name, _yahoo_name(q))]


def _pick_de(quotes):
    return next((q for q in quotes if q['symbol'].endswith('.DE')), None)


def _pick_priority(quotes):
    for suffix in PRIORITY:
        for q in quotes:
            if q['symbol'].endswith(suffix):
                return q
    return None


def lookup(isin, ticker='', name=''):
    """Return (symbol, yahoo_name, status). Implements yahoo-lookup.md.

    Candidates whose Yahoo name is an obvious mismatch with the input
    name (different share class, currency, leverage, or completely
    disjoint theme tokens) are discarded so lookup falls through to the
    next step.
    """
    # Step 1: search by "<ticker>.DE", pick first listing whose symbol == <ticker>.DE
    if ticker:
        target = f'{ticker}.DE'
        q = next((e for e in _search_listings(target)
                  if e['symbol'] == target), None)
        if q:
            return q['symbol'], _yahoo_name(q), 'step1_ticker_de'

    # Step 2: search by ISIN, pick .DE listing
    isin_listings = _search_listings(isin)
    q = _pick_de(isin_listings)
    if q:
        return q['symbol'], _yahoo_name(q), 'step2_isin_de'

    # Step 3: search by yahoo name of first ISIN listing, filter by exact name match, priority pick
    if isin_listings:
        yname_query = _yahoo_name(isin_listings[0])
        if yname_query:
            yname_listings = _search_listings(yname_query)
            matched = [l for l in yname_listings
                       if (l.get('longname') == yname_query or l.get('shortname') == yname_query)]
            q = _pick_priority(matched)
            if q:
                return q['symbol'], _yahoo_name(q), f'step3_yname_{q["symbol"].rsplit(".",1)[-1]}'

    # Step 4: priority pick from ISIN results
    q = _pick_priority(isin_listings)
    if q:
        return q['symbol'], _yahoo_name(q), f'step4_isin_{q["symbol"].rsplit(".",1)[-1]}'

    # Step 5: first listing from ISIN results
    if isin_listings:
        first = isin_listings[0]
        return first['symbol'], _yahoo_name(first), 'step5_isin_first'

    # Step 6: search by CSV name, priority pick
    if name:
        name_listings = _drop_obvious_mismatches(_search_listings(name), name)
        q = _pick_priority(name_listings)
        if q:
            return q['symbol'], _yahoo_name(q), f'step6_name_{q["symbol"].rsplit(".",1)[-1]}'

    return '', '', 'no_match'


def read_cache(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return {row['isin']: row for row in csv.DictReader(f)}


def write_cache(path, cache):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=CACHE_FIELDS)
        w.writeheader()
        for row in cache.values():
            w.writerow({k: row.get(k, '') for k in CACHE_FIELDS})


def write_output(path, input_rows, cache):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        w.writeheader()
        for r in input_rows:
            entry = cache.get(r['isin'], {})
            if entry['yahoo_symbol']:
                w.writerow({
                    'isin': r['isin'],
                    'symbol': entry['yahoo_symbol'],
                    'name': entry['yahoo_name'] or r['name'],
                })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', default=INPUT_DEFAULT)
    ap.add_argument('--output', default=OUTPUT_DEFAULT)
    ap.add_argument('--cache', default=CACHE_DEFAULT)
    ap.add_argument('--retry-empty', action='store_true',
                    help='Re-look-up cached entries that have no yahoo_symbol')
    args = ap.parse_args()

    with open(args.input) as f:
        input_rows = list(csv.DictReader(f))

    cache = read_cache(args.cache)
    print(f'input={len(input_rows)} cached={len(cache)}', flush=True)

    for i, r in enumerate(input_rows, 1):
        isin = r['isin']
        if isin in cache and (not args.retry_empty or cache[isin].get('yahoo_symbol')):
            continue
        ysym, yname, status = lookup(isin, r['ticker'], r['name'])
        cache[isin] = {'isin': isin, 'ticker': r['ticker'], 'name': r['name'],
                       'yahoo_symbol': ysym, 'yahoo_name': yname}
        write_cache(args.cache, cache)
        print(f'{i}/{len(input_rows)}\t{isin}\t{r["ticker"]}\t{ysym}\t{yname}\t{status}', flush=True)

    write_output(args.output, input_rows, cache)


if __name__ == '__main__':
    main()
