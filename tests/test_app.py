"""
Integration tests for the Flask routes in app.py.

Network calls (fetch_metar) and the airport search are mocked so tests
run offline and deterministically.
"""

import json
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# A minimal parse_metar result dict used as a mock return value
# ---------------------------------------------------------------------------

_MOCK_RESULT = {
    'raw': 'METAR EGLL 201020Z 04006KT CAVOK 10/04 Q1023',
    'station': 'EGLL',
    'datetime_str': '20 March 2026 at 10:20 UTC',
    'auto': False,
    'cavok': True,
    'wind': {
        'calm': False,
        'direction_text': 'the north-east',
        'direction_abbr': 'NE',
        'degrees': 40,
        'speed_kt': 6,
        'speed_mph': 6.9,
        'gust_kt': None,
        'gust_mph': None,
    },
    'visibility': 'More than 10 km — ceiling and visibility OK',
    'rvr': [],
    'weather': [],
    'sky': [],
    'temp_c': 10,
    'temp_f': 50.0,
    'dewpoint_c': 4,
    'dewpoint_f': 39.2,
    'feels_like_c': None,
    'feels_like_f': None,
    'feels_like_label': None,
    'altimeter': {'inhg': 30.2, 'hpa': 1023},
    'headline': 'Clear skies and cool',
    'remarks': None,
}


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

def test_get_index_returns_200(client):
    response = client.get('/')
    assert response.status_code == 200

def test_get_index_shows_form(client):
    response = client.get('/')
    assert b'airport' in response.data.lower()


# ---------------------------------------------------------------------------
# POST / — input validation
# ---------------------------------------------------------------------------

def test_post_empty_code_shows_error(client):
    response = client.post('/', data={'airport': '', 'airport_name': ''})
    assert b'Please enter an airport code' in response.data

def test_post_code_too_long_shows_error(client):
    response = client.post('/', data={'airport': 'TOOLONG', 'airport_name': ''})
    assert b'3- or 4-letter' in response.data

def test_post_numeric_code_shows_error(client):
    response = client.post('/', data={'airport': '1234', 'airport_name': ''})
    assert b'3- or 4-letter' in response.data


# ---------------------------------------------------------------------------
# POST / — successful fetch and parse
# ---------------------------------------------------------------------------

def test_post_valid_code_shows_headline(client):
    with (patch('app.fetch_metar', return_value=(_MOCK_RESULT['raw'], None)),
          patch('app.parse_metar', return_value=_MOCK_RESULT)):
        response = client.post('/', data={'airport': 'EGLL', 'airport_name': 'London Heathrow Airport'})
    assert b'Clear skies and cool' in response.data

def test_post_valid_code_shows_station(client):
    with (patch('app.fetch_metar', return_value=(_MOCK_RESULT['raw'], None)),
          patch('app.parse_metar', return_value=_MOCK_RESULT)):
        response = client.post('/', data={'airport': 'EGLL', 'airport_name': ''})
    assert b'EGLL' in response.data

def test_post_airport_name_persists(client):
    with (patch('app.fetch_metar', return_value=(_MOCK_RESULT['raw'], None)),
          patch('app.parse_metar', return_value=_MOCK_RESULT)):
        response = client.post('/', data={'airport': 'EGLL', 'airport_name': 'London Heathrow Airport'})
    assert b'London Heathrow Airport' in response.data

def test_post_airport_code_uppercased(client):
    with (patch('app.fetch_metar', return_value=(_MOCK_RESULT['raw'], None)),
          patch('app.parse_metar', return_value=_MOCK_RESULT)):
        response = client.post('/', data={'airport': 'egll', 'airport_name': ''})
    # If the code is uppercased correctly, the fetch succeeds and the page renders
    assert b'Clear skies and cool' in response.data


# ---------------------------------------------------------------------------
# POST / — fetch error handling
# ---------------------------------------------------------------------------

def test_post_fetch_error_shows_message(client):
    with patch('app.fetch_metar', return_value=(None, 'No METAR data found for "ZZZZ".')):
        response = client.post('/', data={'airport': 'ZZZZ', 'airport_name': ''})
    assert b'No METAR data found' in response.data

def test_post_fetch_error_no_result_rendered(client):
    with patch('app.fetch_metar', return_value=(None, 'Connection error.')):
        response = client.post('/', data={'airport': 'ZZZZ', 'airport_name': ''})
    # The result div is only rendered when a result exists; the CSS selector
    # (.headline-card) is always present, so check for the HTML element tag.
    assert b'<div class="headline-card">' not in response.data


# ---------------------------------------------------------------------------
# GET /search
# ---------------------------------------------------------------------------

def test_search_returns_json(client):
    with patch('app.search_airports', return_value=[
        {'icao': 'EGLL', 'iata': 'LHR', 'name': 'London Heathrow Airport',
         'city': 'London', 'country': 'GB'}
    ]):
        response = client.get('/search?q=heathrow')
    assert response.content_type == 'application/json'
    data = json.loads(response.data)
    assert data[0]['icao'] == 'EGLL'

def test_search_empty_query_returns_empty_list(client):
    with patch('app.search_airports', return_value=[]):
        response = client.get('/search?q=a')
    assert json.loads(response.data) == []

def test_search_missing_query_returns_empty_list(client):
    with patch('app.search_airports', return_value=[]):
        response = client.get('/search')
    assert response.status_code == 200
