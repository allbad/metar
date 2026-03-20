import re
import math
import requests
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

_COMPASS = [
    ('north',            'N'),
    ('north-north-east', 'NNE'),
    ('north-east',       'NE'),
    ('east-north-east',  'ENE'),
    ('east',             'E'),
    ('east-south-east',  'ESE'),
    ('south-east',       'SE'),
    ('south-south-east', 'SSE'),
    ('south',            'S'),
    ('south-south-west', 'SSW'),
    ('south-west',       'SW'),
    ('west-south-west',  'WSW'),
    ('west',             'W'),
    ('west-north-west',  'WNW'),
    ('north-west',       'NW'),
    ('north-north-west', 'NNW'),
]

_DESCRIPTOR = {
    'MI': 'shallow', 'PR': 'partial', 'BC': 'patches of',
    'DR': 'drifting', 'BL': 'blowing', 'SH': 'showers',
    'TS': 'thunderstorm', 'FZ': 'freezing',
}

_PRECIPITATION = {
    'DZ': 'drizzle', 'RA': 'rain', 'SN': 'snow', 'SG': 'snow grains',
    'IC': 'ice crystals', 'PL': 'ice pellets', 'GR': 'hail',
    'GS': 'small hail', 'UP': 'unknown precipitation',
}

_OBSCURATION = {
    'BR': 'mist', 'FG': 'fog', 'FU': 'smoke', 'VA': 'volcanic ash',
    'DU': 'dust', 'SA': 'sand', 'HZ': 'haze', 'PY': 'spray',
}

_OTHER_WX = {
    'PO': 'dust whirls', 'SQ': 'squalls', 'FC': 'funnel cloud/tornado',
    'SS': 'sandstorm', 'DS': 'duststorm',
}

_SKY_COVER = {
    'SKC': 'Clear skies', 'CLR': 'Clear skies',
    'NSC': 'No significant cloud', 'NCD': 'No cloud detected',
    'FEW': 'A few clouds', 'SCT': 'Scattered clouds',
    'BKN': 'Broken cloud cover', 'OVC': 'Overcast',
    'VV':  'Sky obscured',
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _degrees_to_compass(degrees: int) -> tuple[str, str]:
    idx = round(degrees / 22.5) % 16
    return _COMPASS[idx]


def _knots_to_mph(knots: int) -> float:
    return round(knots * 1.15078, 1)


def _c_to_f(c: int) -> float:
    return round(c * 9 / 5 + 32, 1)


def _parse_signed_temp(s: str) -> int:
    """Convert 'M05' → -5, '23' → 23."""
    if s.startswith('M'):
        return -int(s[1:])
    return int(s)


def _wind_chill(temp_c: int, wind_mph: float) -> int | None:
    """Wind chill index (°C). Valid when temp ≤ 10°C and wind ≥ 3 mph."""
    if temp_c > 10 or wind_mph < 3:
        return None
    wc = (13.12 + 0.6215 * temp_c
          - 11.37 * wind_mph ** 0.16
          + 0.3965 * temp_c * wind_mph ** 0.16)
    return round(wc)


def _heat_index(temp_c: int, dewpoint_c: int) -> int | None:
    """Heat index (°C). Valid when temp ≥ 27°C."""
    if temp_c < 27:
        return None
    # Relative humidity from dewpoint (Magnus approximation)
    rh = 100 * math.exp((17.625 * dewpoint_c) / (243.04 + dewpoint_c)
                        - (17.625 * temp_c) / (243.04 + temp_c))
    if rh < 40:
        return None
    # Rothfusz equation (°F then convert)
    tf = _c_to_f(temp_c)
    hi = (-42.379 + 2.04901523 * tf + 10.14333127 * rh
          - 0.22475541 * tf * rh - 0.00683783 * tf ** 2
          - 0.05481717 * rh ** 2 + 0.00122874 * tf ** 2 * rh
          + 0.00085282 * tf * rh ** 2 - 0.00000199 * tf ** 2 * rh ** 2)
    return round((hi - 32) * 5 / 9)


# ---------------------------------------------------------------------------
# Field parsers
# ---------------------------------------------------------------------------

def _parse_datetime(token: str) -> str | None:
    m = re.fullmatch(r'(\d{2})(\d{2})(\d{2})Z', token)
    if not m:
        return None
    day, hour, minute = int(m.group(1)), int(m.group(2)), int(m.group(3))
    now = datetime.now(timezone.utc)
    return f"{day:02d} {now.strftime('%B %Y')} at {hour:02d}:{minute:02d} UTC"


def _parse_wind(token: str) -> dict | None:
    m = re.fullmatch(
        r'(VRB|\d{3})(\d{2,3})(?:G(\d{2,3}))?(KT|MPS|KMH)', token
    )
    if not m:
        return None
    direction_raw, speed_raw, gust_raw, unit = m.groups()

    speed = int(speed_raw)
    gust = int(gust_raw) if gust_raw else None

    # Convert to knots
    if unit == 'MPS':
        speed = round(speed * 1.94384)
        gust = round(gust * 1.94384) if gust else None
    elif unit == 'KMH':
        speed = round(speed / 1.852)
        gust = round(gust / 1.852) if gust else None

    speed_mph = _knots_to_mph(speed)
    gust_mph = _knots_to_mph(gust) if gust else None

    if direction_raw == 'VRB':
        direction_text = 'variable direction'
        direction_abbr = 'VRB'
        degrees = None
    else:
        degrees = int(direction_raw)
        if degrees == 0 and speed == 0:
            return {'calm': True, 'speed_kt': 0, 'speed_mph': 0.0}
        direction_text, direction_abbr = _degrees_to_compass(degrees)
        direction_text = f'the {direction_text}'

    result = {
        'calm': False,
        'direction_text': direction_text,
        'direction_abbr': direction_abbr,
        'degrees': degrees,
        'speed_kt': speed,
        'speed_mph': speed_mph,
        'gust_kt': gust,
        'gust_mph': gust_mph,
    }

    if speed == 0 and not gust:
        result['calm'] = True

    return result


def _parse_visibility(token: str) -> str | None:
    # Fractional SM: M1/4SM, 1/2SM, 1 1/4SM (two tokens joined already)
    m = re.fullmatch(r'(M?)(\d+)/(\d+)SM', token)
    if m:
        less_than = 'less than ' if m.group(1) else ''
        frac = int(m.group(2)) / int(m.group(3))
        return f'{less_than}{frac:.2g} mile{"s" if frac != 1 else ""}'

    m = re.fullmatch(r'(M?)(\d+)SM', token)
    if m:
        less_than = 'less than ' if m.group(1) else ''
        miles = int(m.group(2))
        return f'{less_than}{miles} mile{"s" if miles != 1 else ""}'

    # Metric visibility in metres (4-digit)
    m = re.fullmatch(r'(\d{4})', token)
    if m:
        metres = int(m.group(1))
        if metres == 9999:
            return 'more than 10 km'
        km = metres / 1000
        return f'{km:.1f} km'

    return None


def _parse_weather(token: str) -> str | None:
    """Parse a single weather group, e.g. -RASN, +TSRA, BCFG."""
    original = token
    parts = []

    # Intensity / proximity
    intensity = ''
    if token.startswith('VC'):
        intensity = 'nearby'
        token = token[2:]
    elif token.startswith('+'):
        intensity = 'heavy'
        token = token[1:]
    elif token.startswith('-'):
        intensity = 'light'
        token = token[1:]

    # Descriptor
    descriptor = ''
    for code, text in _DESCRIPTOR.items():
        if token.startswith(code):
            descriptor = text
            token = token[len(code):]
            break

    # Precipitation (can be multiple, e.g. RASN)
    precip_parts = []
    while token:
        matched = False
        for code, text in _PRECIPITATION.items():
            if token.startswith(code):
                precip_parts.append(text)
                token = token[len(code):]
                matched = True
                break
        if not matched:
            break

    # Obscuration
    obscuration = ''
    for code, text in _OBSCURATION.items():
        if token.startswith(code):
            obscuration = text
            token = token[len(code):]
            break

    # Other
    other = ''
    for code, text in _OTHER_WX.items():
        if token.startswith(code):
            other = text
            token = token[len(code):]
            break

    if not any([precip_parts, obscuration, other, descriptor]):
        return None  # unrecognised token

    words = []
    if intensity:
        words.append(intensity)
    if descriptor and descriptor != 'showers':
        words.append(descriptor)
    if precip_parts:
        words.append(' and '.join(precip_parts))
        if descriptor == 'showers':
            words.append('showers')
    if obscuration:
        words.append(obscuration)
    if other:
        words.append(other)

    return ' '.join(words).capitalize()


def _parse_sky(token: str) -> dict | None:
    """Parse a sky condition token, e.g. FEW015, BKN030CB, OVC010, VV004."""
    m = re.fullmatch(r'(SKC|CLR|NSC|NCD)()', token)
    if m:
        return {'cover': _SKY_COVER[m.group(1)], 'altitude_ft': None, 'cloud_type': None}

    m = re.fullmatch(r'(FEW|SCT|BKN|OVC|VV)(\d{3})(CB|TCU)?', token)
    if m:
        cover_code, alt_code, cloud_type = m.groups()
        altitude_ft = int(alt_code) * 100
        cover_text = _SKY_COVER[cover_code]
        type_text = {'CB': 'cumulonimbus', 'TCU': 'towering cumulus'}.get(cloud_type, '')
        return {
            'cover': cover_text,
            'altitude_ft': altitude_ft,
            'cloud_type': type_text or None,
        }

    return None


def _parse_temp_dew(token: str) -> tuple[int, int] | None:
    m = re.fullmatch(r'(M?\d+)/(M?\d+)', token)
    if not m:
        return None
    return _parse_signed_temp(m.group(1)), _parse_signed_temp(m.group(2))


def _parse_altimeter(token: str) -> dict | None:
    m = re.fullmatch(r'A(\d{4})', token)
    if m:
        inhg = int(m.group(1)) / 100
        hpa = round(inhg * 33.8639)
        return {'inhg': inhg, 'hpa': hpa}
    m = re.fullmatch(r'Q(\d{4})', token)
    if m:
        hpa = int(m.group(1))
        inhg = round(hpa / 33.8639, 2)
        return {'inhg': inhg, 'hpa': hpa}
    return None


# ---------------------------------------------------------------------------
# Headline builder
# ---------------------------------------------------------------------------

def _build_headline(sky_layers: list, weather_groups: list, wind: dict | None,
                    temp_c: int | None) -> str:
    """Produce a one-line plain-English summary."""
    # Priority: severe weather first
    if weather_groups:
        wx = weather_groups[0].lower()
        if 'thunderstorm' in wx:
            headline = 'Thunderstorm'
        elif 'tornado' in wx or 'funnel' in wx:
            headline = 'Tornado / funnel cloud'
        elif 'sandstorm' in wx or 'duststorm' in wx:
            headline = 'Sandstorm / duststorm'
        elif 'freezing' in wx:
            headline = 'Freezing precipitation'
        elif 'heavy' in wx:
            headline = weather_groups[0]
        else:
            headline = weather_groups[0]
    else:
        # Derive from sky cover
        covers = [s['cover'] for s in sky_layers] if sky_layers else []
        if not covers or covers == ['Clear skies'] or covers == ['No significant cloud']:
            headline = 'Clear skies'
        elif any('Overcast' in c or 'Broken' in c for c in covers):
            headline = 'Overcast'
        elif any('Scattered' in c for c in covers):
            headline = 'Partly cloudy'
        elif any('few' in c.lower() for c in covers):
            headline = 'Mostly clear'
        else:
            headline = 'Clear skies'

    # Append a temperature feel
    if temp_c is not None:
        if temp_c >= 30:
            headline += ' and hot'
        elif temp_c >= 20:
            headline += ' and warm'
        elif temp_c >= 10:
            headline += ' and mild'
        elif temp_c >= 0:
            headline += ' and cool'
        elif temp_c >= -10:
            headline += ' and cold'
        else:
            headline += ' and very cold'

    # Wind modifier
    if wind and not wind.get('calm'):
        speed_mph = wind.get('speed_mph', 0)
        if speed_mph >= 40:
            headline += ', with strong winds'
        elif speed_mph >= 20:
            headline += ', with a brisk wind'
        elif speed_mph >= 10:
            headline += ', with a moderate breeze'

    return headline


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_metar(raw: str) -> dict:
    """
    Parse a raw METAR string and return a structured dict of plain-English fields.
    """
    raw = raw.strip()
    tokens = raw.split()

    result = {
        'raw': raw,
        'station': None,
        'datetime_str': None,
        'auto': False,
        'cavok': False,
        'wind': None,
        'visibility': None,
        'rvr': [],
        'weather': [],
        'sky': [],
        'temp_c': None,
        'temp_f': None,
        'dewpoint_c': None,
        'dewpoint_f': None,
        'feels_like_c': None,
        'feels_like_f': None,
        'feels_like_label': None,
        'altimeter': None,
        'headline': 'No data',
        'remarks': None,
    }

    idx = 0

    # Strip optional METAR/SPECI type prefix
    if tokens[idx] in ('METAR', 'SPECI'):
        idx += 1

    # Station identifier
    if idx < len(tokens) and re.fullmatch(r'[A-Z]{4}', tokens[idx]):
        result['station'] = tokens[idx]
        idx += 1

    # Date/time
    if idx < len(tokens):
        dt = _parse_datetime(tokens[idx])
        if dt:
            result['datetime_str'] = dt
            idx += 1

    # AUTO / COR flags (may appear individually or together, any order)
    while idx < len(tokens) and tokens[idx] in ('AUTO', 'COR'):
        if tokens[idx] == 'AUTO':
            result['auto'] = True
        idx += 1

    # Wind — may be followed by a variable direction range token like 350V060
    if idx < len(tokens):
        wind = _parse_wind(tokens[idx])
        if wind:
            result['wind'] = wind
            idx += 1
            # Variable range: e.g. 350V060
            if idx < len(tokens) and re.fullmatch(r'\d{3}V\d{3}', tokens[idx]):
                m = re.fullmatch(r'(\d{3})V(\d{3})', tokens[idx])
                from1, to1 = _degrees_to_compass(int(m.group(1)))
                from2, to2 = _degrees_to_compass(int(m.group(2)))
                result['wind']['variable_range'] = f'{from1[0].upper() + from1[1:]} to {from2}'
                idx += 1

    # CAVOK (replaces visibility, weather, sky)
    if idx < len(tokens) and tokens[idx] == 'CAVOK':
        result['cavok'] = True
        result['visibility'] = 'More than 10 km — ceiling and visibility OK'
        idx += 1

    # Visibility (may be two tokens: "1" "1/2SM")
    if idx < len(tokens) and not result['cavok']:
        # Check for combined whole + fraction: "1 1/2SM"
        if (idx + 1 < len(tokens)
                and re.fullmatch(r'\d+', tokens[idx])
                and re.fullmatch(r'\d+/\d+SM', tokens[idx + 1])):
            combined = tokens[idx] + ' ' + tokens[idx + 1]
            # e.g. "1 1/2SM" → parse whole + fraction
            whole = int(tokens[idx])
            fm = re.fullmatch(r'(\d+)/(\d+)SM', tokens[idx + 1])
            frac = int(fm.group(1)) / int(fm.group(2))
            total = whole + frac
            result['visibility'] = f'{total:.2g} miles'
            idx += 2
        else:
            vis = _parse_visibility(tokens[idx])
            if vis:
                result['visibility'] = vis
                idx += 1

    # RVR (Runway Visual Range) — skip tokens matching R\d+.../...FT
    while idx < len(tokens) and re.match(r'^R\d+', tokens[idx]):
        result['rvr'].append(tokens[idx])
        idx += 1

    # Weather groups
    if not result['cavok']:
        while idx < len(tokens):
            wx = _parse_weather(tokens[idx])
            if wx:
                result['weather'].append(wx)
                idx += 1
            else:
                break

    # Sky conditions (or CAVOK already handled above)
    if not result['cavok']:
        while idx < len(tokens):
            sky = _parse_sky(tokens[idx])
            if sky:
                result['sky'].append(sky)
                idx += 1
            elif tokens[idx] in ('SKC', 'CLR', 'NSC', 'NCD'):
                result['sky'].append({'cover': _SKY_COVER[tokens[idx]],
                                      'altitude_ft': None, 'cloud_type': None})
                idx += 1
            else:
                break

    # Temperature / dewpoint
    if idx < len(tokens):
        td = _parse_temp_dew(tokens[idx])
        if td:
            temp_c, dew_c = td
            result['temp_c'] = temp_c
            result['temp_f'] = _c_to_f(temp_c)
            result['dewpoint_c'] = dew_c
            result['dewpoint_f'] = _c_to_f(dew_c)
            idx += 1

    # Altimeter
    if idx < len(tokens):
        alt = _parse_altimeter(tokens[idx])
        if alt:
            result['altimeter'] = alt
            idx += 1

    # Remarks
    if idx < len(tokens) and tokens[idx] == 'RMK':
        result['remarks'] = ' '.join(tokens[idx + 1:])

    # Feels-like temperature
    if result['temp_c'] is not None and result['wind']:
        speed_mph = result['wind'].get('speed_mph', 0)
        wc = _wind_chill(result['temp_c'], speed_mph)
        hi = (_heat_index(result['temp_c'], result['dewpoint_c'])
              if result['dewpoint_c'] is not None else None)
        if wc is not None:
            result['feels_like_c'] = wc
            result['feels_like_f'] = _c_to_f(wc)
            result['feels_like_label'] = 'Wind chill'
        elif hi is not None:
            result['feels_like_c'] = hi
            result['feels_like_f'] = _c_to_f(hi)
            result['feels_like_label'] = 'Heat index'

    # Build headline
    result['headline'] = _build_headline(
        result['sky'], result['weather'], result['wind'], result['temp_c']
    )

    return result


# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------

def fetch_metar(airport_code: str) -> tuple[str | None, str | None]:
    """
    Fetch the latest raw METAR for the given ICAO airport code.
    Returns (raw_metar_string, error_message).
    """
    url = (
        'https://aviationweather.gov/api/data/metar'
        f'?ids={airport_code}&format=raw&hours=2'
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        return None, 'Could not connect to the weather service. Check your internet connection.'
    except requests.exceptions.Timeout:
        return None, 'The weather service timed out. Please try again.'
    except requests.exceptions.HTTPError as e:
        return None, f'Weather service returned an error: {e}'

    text = resp.text.strip()
    if not text:
        return None, f'No METAR data found for "{airport_code}". Check the airport code and try again.'

    # The API may return multiple lines; take the last non-empty line.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1], None
