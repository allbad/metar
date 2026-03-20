"""
Airport name/code lookup backed by the OurAirports public dataset.

The CSV is downloaded once and cached locally as a trimmed JSON file.
The cache is refreshed automatically after CACHE_MAX_AGE seconds.
"""

import csv
import io
import json
import os
import time

import requests

_AIRPORTS_URL = 'https://davidmegginson.github.io/ourairports-data/airports.csv'
_CACHE_FILE = os.path.join(os.path.dirname(__file__), '.airports_cache.json')
_CACHE_MAX_AGE = 7 * 24 * 3600  # one week

_INCLUDED_TYPES = {'large_airport', 'medium_airport', 'small_airport'}


def _download_and_parse() -> list[dict]:
    resp = requests.get(_AIRPORTS_URL, timeout=30)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    airports = []
    for row in reader:
        ident = row.get('ident', '').strip()
        if len(ident) != 4 or not ident.isalpha():
            continue
        if row.get('type', '') not in _INCLUDED_TYPES:
            continue
        airports.append({
            'icao': ident.upper(),
            'name': row.get('name', '').strip(),
            'city': row.get('municipality', '').strip(),
            'iata': row.get('iata_code', '').strip().upper(),
            'country': row.get('iso_country', '').strip().upper(),
        })
    return airports


def _load() -> list[dict]:
    if os.path.exists(_CACHE_FILE):
        age = time.time() - os.path.getmtime(_CACHE_FILE)
        if age < _CACHE_MAX_AGE:
            with open(_CACHE_FILE, encoding='utf-8') as f:
                return json.load(f)
    airports = _download_and_parse()
    with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(airports, f)
    return airports


# Load once at import time; failures leave an empty list so the app still runs.
try:
    _AIRPORTS: list[dict] = _load()
except Exception as exc:
    import sys
    print(f'[airports] Failed to load airport data: {exc}', file=sys.stderr)
    _AIRPORTS = []


def search_airports(query: str, limit: int = 8) -> list[dict]:
    """
    Return up to `limit` airports matching `query` against name, city, ICAO,
    or IATA code.  Results are ranked:
      1. Exact ICAO match
      2. Exact IATA match
      3. Name starts with query
      4. City starts with query
      5. Name or city contains query
    """
    if not query or len(query) < 2:
        return []

    q = query.strip().upper()
    q_lower = q.lower()

    buckets: list[list[dict]] = [[], [], [], [], []]

    for apt in _AIRPORTS:
        name_l = apt['name'].lower()
        city_l = apt['city'].lower()

        if apt['icao'] == q:
            buckets[0].append(apt)
        elif apt['iata'] == q:
            buckets[1].append(apt)
        elif name_l.startswith(q_lower):
            buckets[2].append(apt)
        elif city_l.startswith(q_lower):
            buckets[3].append(apt)
        elif q_lower in name_l or q_lower in city_l:
            buckets[4].append(apt)

    results = []
    for bucket in buckets:
        for apt in bucket:
            if apt not in results:
                results.append(apt)
            if len(results) >= limit:
                return results

    return results
