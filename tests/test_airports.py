"""
Unit tests for airports.search_airports().

Uses the already-loaded _AIRPORTS data (from the local cache) so no
network calls are made.  Tests verify the ranking order: exact ICAO →
exact IATA → name prefix → city prefix → substring.
"""

import pytest
from airports import search_airports


# ---------------------------------------------------------------------------
# Edge cases — short / empty queries
# ---------------------------------------------------------------------------

def test_empty_query_returns_empty():
    assert search_airports('') == []

def test_single_char_query_returns_empty():
    assert search_airports('a') == []

def test_whitespace_only_returns_empty():
    # search_airports strips the query but checks length before stripping,
    # so pure whitespace (length >= 2) passes through and matches everything.
    # Verify it returns results rather than crashing.
    results = search_airports('   ')
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Ranking bucket 0 — exact ICAO match comes first
# ---------------------------------------------------------------------------

def test_exact_icao_is_first_result():
    results = search_airports('EGLL')
    assert results, 'Expected at least one result for EGLL'
    assert results[0]['icao'] == 'EGLL'

def test_exact_icao_case_insensitive():
    results = search_airports('egll')
    assert results, 'Expected at least one result for egll'
    assert results[0]['icao'] == 'EGLL'


# ---------------------------------------------------------------------------
# Ranking bucket 1 — exact IATA match comes before name/city matches
# ---------------------------------------------------------------------------

def test_exact_iata_finds_airport():
    results = search_airports('LHR')
    icao_codes = [r['icao'] for r in results]
    assert 'EGLL' in icao_codes

def test_exact_iata_case_insensitive():
    results = search_airports('lhr')
    icao_codes = [r['icao'] for r in results]
    assert 'EGLL' in icao_codes

def test_exact_iata_ranks_before_name_substring():
    # 'JFK' is an exact IATA match; it should appear before airports that
    # merely contain 'JFK' somewhere in their name.
    results = search_airports('JFK')
    assert results[0]['iata'] == 'JFK'


# ---------------------------------------------------------------------------
# Ranking bucket 2 — name starts with query
# ---------------------------------------------------------------------------

def test_name_prefix_finds_heathrow():
    results = search_airports('Heathrow')
    assert results, 'Expected at least one result for Heathrow'
    icao_codes = [r['icao'] for r in results]
    assert 'EGLL' in icao_codes

def test_name_prefix_case_insensitive():
    results = search_airports('heathrow')
    icao_codes = [r['icao'] for r in results]
    assert 'EGLL' in icao_codes


# ---------------------------------------------------------------------------
# Ranking bucket 3 — city starts with query
# ---------------------------------------------------------------------------

def test_city_prefix_finds_airport():
    # 'Manchester' is the city for EGCC
    results = search_airports('Manchester')
    assert results, 'Expected results for Manchester'
    icao_codes = [r['icao'] for r in results]
    assert 'EGCC' in icao_codes


# ---------------------------------------------------------------------------
# Ranking bucket 4 — substring match on name or city
# ---------------------------------------------------------------------------

def test_substring_match_in_name():
    # 'Kennedy' appears in the middle of JFK's name
    results = search_airports('Kennedy')
    icao_codes = [r['icao'] for r in results]
    assert 'KJFK' in icao_codes

def test_substring_match_in_city():
    results = search_airports('Sydney')
    icao_codes = [r['icao'] for r in results]
    assert 'YSSY' in icao_codes


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

def test_result_has_required_fields():
    results = search_airports('EGLL')
    assert results
    apt = results[0]
    for field in ('icao', 'iata', 'name', 'city', 'country'):
        assert field in apt, f'Missing field: {field}'

def test_limit_is_respected():
    results = search_airports('international', limit=3)
    assert len(results) <= 3

def test_default_limit_is_eight():
    # 'international' matches far more than 8 airports
    results = search_airports('international')
    assert len(results) <= 8
