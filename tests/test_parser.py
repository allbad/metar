"""
Unit tests for metar_parser.parse_metar().

Each test passes a hand-crafted METAR string and asserts the decoded
output matches the expected plain-English values.  No network calls are
made — parse_metar() is a pure string → dict function.
"""

import pytest
from metar_parser import parse_metar


# ---------------------------------------------------------------------------
# Fixture: a well-formed, fully-populated standard METAR
# ---------------------------------------------------------------------------

_STANDARD_RAW = "METAR KJFK 201756Z 18005KT 10SM FEW050 23/12 A3012 RMK AO2"


@pytest.fixture
def standard():
    return parse_metar(_STANDARD_RAW)


# ---------------------------------------------------------------------------
# Standard METAR — all fields
# ---------------------------------------------------------------------------

class TestStandardMetar:
    def test_station(self, standard):
        assert standard['station'] == 'KJFK'

    def test_raw_preserved(self, standard):
        assert standard['raw'] == _STANDARD_RAW

    def test_wind_direction_degrees(self, standard):
        assert standard['wind']['degrees'] == 180

    def test_wind_direction_abbr(self, standard):
        assert standard['wind']['direction_abbr'] == 'S'

    def test_wind_speed_kt(self, standard):
        assert standard['wind']['speed_kt'] == 5

    def test_wind_speed_mph(self, standard):
        assert standard['wind']['speed_mph'] == 5.8

    def test_wind_not_calm(self, standard):
        assert not standard['wind']['calm']

    def test_no_gusts(self, standard):
        assert standard['wind']['gust_kt'] is None
        assert standard['wind']['gust_mph'] is None

    def test_visibility(self, standard):
        assert standard['visibility'] == '10 miles'

    def test_sky_layer_count(self, standard):
        assert len(standard['sky']) == 1

    def test_sky_cover(self, standard):
        assert standard['sky'][0]['cover'] == 'A few clouds'

    def test_sky_altitude(self, standard):
        assert standard['sky'][0]['altitude_ft'] == 5000

    def test_sky_no_cloud_type(self, standard):
        assert standard['sky'][0]['cloud_type'] is None

    def test_temperature_c(self, standard):
        assert standard['temp_c'] == 23

    def test_temperature_f(self, standard):
        assert standard['temp_f'] == 73.4

    def test_dewpoint_c(self, standard):
        assert standard['dewpoint_c'] == 12

    def test_altimeter_inhg(self, standard):
        assert standard['altimeter']['inhg'] == 30.12

    def test_altimeter_hpa(self, standard):
        assert standard['altimeter']['hpa'] == 1020

    def test_remarks(self, standard):
        assert standard['remarks'] == 'AO2'

    def test_not_auto(self, standard):
        assert not standard['auto']

    def test_not_cavok(self, standard):
        assert not standard['cavok']

    def test_no_weather_phenomena(self, standard):
        assert standard['weather'] == []

    def test_headline_not_empty(self, standard):
        assert standard['headline']


# ---------------------------------------------------------------------------
# CAVOK
# ---------------------------------------------------------------------------

def test_cavok_flag():
    r = parse_metar("METAR EGLL 201020Z 04006KT CAVOK 10/04 Q1023")
    assert r['cavok'] is True

def test_cavok_visibility_description():
    r = parse_metar("METAR EGLL 201020Z 04006KT CAVOK 10/04 Q1023")
    assert '10 km' in r['visibility']

def test_cavok_sky_empty():
    r = parse_metar("METAR EGLL 201020Z 04006KT CAVOK 10/04 Q1023")
    assert r['sky'] == []


# ---------------------------------------------------------------------------
# Wind variations
# ---------------------------------------------------------------------------

def test_calm_wind():
    r = parse_metar("METAR KJFK 201756Z 00000KT 10SM CLR 20/10 A3010")
    assert r['wind']['calm'] is True

def test_variable_wind_abbr():
    r = parse_metar("METAR KJFK 201756Z VRB03KT 10SM CLR 20/10 A3010")
    assert r['wind']['direction_abbr'] == 'VRB'

def test_variable_wind_speed():
    r = parse_metar("METAR KJFK 201756Z VRB03KT 10SM CLR 20/10 A3010")
    assert r['wind']['speed_kt'] == 3

def test_variable_wind_not_calm():
    r = parse_metar("METAR KJFK 201756Z VRB03KT 10SM CLR 20/10 A3010")
    assert not r['wind']['calm']

def test_wind_gust_kt():
    r = parse_metar("METAR KJFK 201756Z 18015G25KT 10SM CLR 20/10 A3010")
    assert r['wind']['gust_kt'] == 25

def test_wind_gust_mph():
    r = parse_metar("METAR KJFK 201756Z 18015G25KT 10SM CLR 20/10 A3010")
    assert r['wind']['gust_mph'] == 28.8

def test_wind_variable_range_present():
    r = parse_metar("METAR KJFK 201756Z 18010KT 160V220 10SM CLR 20/10 A3010")
    assert r['wind']['variable_range'] is not None

def test_wind_variable_range_content():
    r = parse_metar("METAR KJFK 201756Z 18010KT 160V220 10SM CLR 20/10 A3010")
    # 160° = SSE, 220° = SW — both contain 'south'
    assert 'south' in r['wind']['variable_range'].lower()

def test_mps_wind_conversion():
    # 10 MPS ≈ 19 knots (10 * 1.94384)
    r = parse_metar("METAR ESGG 201756Z 18010MPS 9999 NCD 15/10 Q1015")
    assert r['wind']['speed_kt'] == round(10 * 1.94384)


# ---------------------------------------------------------------------------
# AUTO / COR flags
# ---------------------------------------------------------------------------

def test_auto_flag():
    r = parse_metar("METAR KJFK 201756Z AUTO 18005KT 10SM CLR 20/10 A3010")
    assert r['auto'] is True

def test_cor_does_not_set_auto():
    r = parse_metar("METAR KJFK 201756Z COR 18005KT 10SM CLR 20/10 A3010")
    assert r['auto'] is False

def test_cor_and_auto_together_parses_wind():
    # Regression: both flags must be consumed before wind is parsed
    r = parse_metar("METAR EGLL 200850Z COR AUTO 05005KT 9999 NCD 08/03 Q1024")
    assert r['auto'] is True
    assert r['wind']['speed_kt'] == 5


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------

def test_visibility_statute_miles():
    r = parse_metar("METAR KJFK 201756Z 18005KT 10SM CLR 20/10 A3010")
    assert r['visibility'] == '10 miles'

def test_visibility_fractional():
    r = parse_metar("METAR KJFK 201756Z 18005KT 1/4SM FG OVC002 02/01 A2990")
    assert r['visibility'] == '0.25 miles'

def test_visibility_metric_9999():
    r = parse_metar("METAR EGLL 201020Z 04006KT 9999 NCD 10/04 Q1023")
    assert r['visibility'] == 'more than 10 km'

def test_visibility_metric_partial():
    r = parse_metar("METAR EGLL 201020Z 04006KT 0800 FG OVC002 05/04 Q1010")
    assert '0.8 km' in r['visibility']


# ---------------------------------------------------------------------------
# Sky conditions
# ---------------------------------------------------------------------------

def test_multiple_sky_layers_count():
    r = parse_metar("METAR KJFK 201756Z 18010KT 10SM FEW020 SCT050 BKN100 20/10 A3010")
    assert len(r['sky']) == 3

def test_multiple_sky_layers_covers():
    r = parse_metar("METAR KJFK 201756Z 18010KT 10SM FEW020 SCT050 BKN100 20/10 A3010")
    assert r['sky'][0]['cover'] == 'A few clouds'
    assert r['sky'][1]['cover'] == 'Scattered clouds'
    assert r['sky'][2]['cover'] == 'Broken cloud cover'

def test_sky_altitudes():
    r = parse_metar("METAR KJFK 201756Z 18010KT 10SM FEW020 SCT050 BKN100 20/10 A3010")
    assert r['sky'][0]['altitude_ft'] == 2000
    assert r['sky'][1]['altitude_ft'] == 5000
    assert r['sky'][2]['altitude_ft'] == 10000

def test_sky_cumulonimbus():
    r = parse_metar("METAR KJFK 201756Z 18010KT 10SM FEW020CB 20/10 A3010")
    assert r['sky'][0]['cloud_type'] == 'cumulonimbus'

def test_sky_towering_cumulus():
    r = parse_metar("METAR KJFK 201756Z 18010KT 10SM SCT025TCU 20/10 A3010")
    assert r['sky'][0]['cloud_type'] == 'towering cumulus'

def test_sky_clear():
    r = parse_metar("METAR KJFK 201756Z 18005KT 10SM CLR 20/10 A3010")
    assert r['sky'][0]['cover'] == 'Clear skies'
    assert r['sky'][0]['altitude_ft'] is None

def test_overcast():
    r = parse_metar("METAR KJFK 201756Z 18005KT 10SM OVC010 20/10 A3010")
    assert r['sky'][0]['cover'] == 'Overcast'
    assert r['sky'][0]['altitude_ft'] == 1000


# ---------------------------------------------------------------------------
# Weather phenomena
# ---------------------------------------------------------------------------

def test_light_rain():
    r = parse_metar("METAR KJFK 201756Z 18005KT 5SM -RA OVC015 15/12 A2990")
    assert len(r['weather']) == 1
    assert 'light' in r['weather'][0].lower()
    assert 'rain' in r['weather'][0].lower()

def test_heavy_thunderstorm_rain():
    r = parse_metar("METAR KJFK 201756Z 18010KT 2SM +TSRA OVC010 20/18 A2975")
    assert 'heavy' in r['weather'][0].lower()
    assert 'thunderstorm' in r['weather'][0].lower()
    assert 'rain' in r['weather'][0].lower()

def test_fog_patches():
    r = parse_metar("METAR KJFK 201756Z 18005KT 1/4SM BCFG OVC002 10/09 A2990")
    assert 'fog' in r['weather'][0].lower()

def test_snow():
    r = parse_metar("METAR KJFK 201756Z 18005KT 2SM SN OVC010 M02/M04 A2985")
    assert 'snow' in r['weather'][0].lower()

def test_freezing_rain():
    r = parse_metar("METAR KJFK 201756Z 18005KT 1SM FZRA OVC005 00/M01 A2990")
    assert 'freezing' in r['weather'][0].lower()
    assert 'rain' in r['weather'][0].lower()

def test_multiple_weather_groups():
    r = parse_metar("METAR KJFK 201756Z 18005KT 3SM -RA BR OVC010 12/11 A2990")
    assert len(r['weather']) == 2


# ---------------------------------------------------------------------------
# Temperature and dewpoint
# ---------------------------------------------------------------------------

def test_negative_temperature():
    r = parse_metar("METAR KJFK 201756Z 18005KT 10SM CLR M05/M10 A3010")
    assert r['temp_c'] == -5
    assert r['dewpoint_c'] == -10

def test_negative_temp_fahrenheit():
    r = parse_metar("METAR KJFK 201756Z 18005KT 10SM CLR M05/M10 A3010")
    assert r['temp_f'] == 23.0

def test_zero_temperature():
    r = parse_metar("METAR KJFK 201756Z 18005KT 10SM CLR 00/M02 A3010")
    assert r['temp_c'] == 0
    assert r['dewpoint_c'] == -2


# ---------------------------------------------------------------------------
# Altimeter
# ---------------------------------------------------------------------------

def test_altimeter_a_prefix():
    r = parse_metar("METAR KJFK 201756Z 18005KT 10SM CLR 20/10 A3012")
    assert r['altimeter']['inhg'] == 30.12
    assert r['altimeter']['hpa'] == 1020

def test_altimeter_q_prefix():
    r = parse_metar("METAR EGLL 201020Z 04006KT 9999 NCD 10/04 Q1023")
    assert r['altimeter']['hpa'] == 1023
    assert r['altimeter']['inhg'] == 30.21  # round(1023 / 33.8639, 2)


# ---------------------------------------------------------------------------
# Feels-like temperature
# ---------------------------------------------------------------------------

def test_wind_chill_applied():
    # -5°C and 10kt wind → wind chill should apply
    r = parse_metar("METAR KJFK 201756Z 09010KT 10SM CLR M05/M10 A3010")
    assert r['feels_like_label'] == 'Wind chill'
    assert r['feels_like_c'] is not None
    assert r['feels_like_c'] < r['temp_c']

def test_wind_chill_not_applied_when_calm():
    r = parse_metar("METAR KJFK 201756Z 00000KT 10SM CLR 05/00 A3010")
    assert r['feels_like_c'] is None

def test_heat_index_applied():
    # 35°C and high dewpoint → heat index should apply
    r = parse_metar("METAR KMIA 201756Z 18005KT 10SM CLR 35/25 A3010")
    assert r['feels_like_label'] == 'Heat index'
    assert r['feels_like_c'] is not None
    assert r['feels_like_c'] > r['temp_c']


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_speci_prefix():
    r = parse_metar("SPECI KJFK 201756Z 18005KT 10SM CLR 20/10 A3010")
    assert r['station'] == 'KJFK'

def test_minimal_metar():
    # No wind, visibility, or sky — just station, time, temp, pressure
    r = parse_metar("KJFK 201756Z 20/10 A3010")
    assert r['station'] == 'KJFK'
    assert r['wind'] is None
    assert r['visibility'] is None
    assert r['sky'] == []
    assert r['weather'] == []

def test_remarks_captured():
    r = parse_metar("METAR KJFK 201756Z 18005KT 10SM CLR 20/10 A3010 RMK AO2 SLP205")
    assert r['remarks'] == 'AO2 SLP205'

def test_remarks_not_parsed_as_weather():
    # Tokens after RMK should not bleed into weather fields
    r = parse_metar("METAR KJFK 201756Z 18005KT 10SM CLR 20/10 A3010 RMK AO2 SLP205")
    assert r['weather'] == []
