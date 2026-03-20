"""
METAR Reader — Flask web application.

Fetches live METAR weather reports from the Aviation Weather Center and
presents them in plain English. Users can search for airports by name
using the autocomplete field, or enter an ICAO/IATA code directly.
"""

from flask import Flask, jsonify, render_template, request

from airports import search_airports
from metar_parser import fetch_metar, parse_metar

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Render the main page.

    GET  — display the empty search form.
    POST — validate the submitted airport code, fetch the latest METAR
           from aviationweather.gov, parse it into plain English, and
           return the results to the template.
    """
    result = None
    error = None
    airport_code = ''
    airport_name = ''

    if request.method == 'POST':
        airport_code = request.form.get('airport', '').strip().upper()
        airport_name = request.form.get('airport_name', '').strip()

        if not airport_code:
            error = 'Please enter an airport code.'
        elif not airport_code.isalpha() or len(airport_code) not in (3, 4):
            error = 'Enter a 3- or 4-letter ICAO/IATA airport code (e.g. EGLL or LHR).'
        else:
            raw, fetch_error = fetch_metar(airport_code)
            if fetch_error:
                error = fetch_error
            else:
                try:
                    result = parse_metar(raw)
                except Exception:
                    error = 'Could not decode the METAR data. The format may be unusual.'

    return render_template('index.html', result=result, error=error,
                           airport_code=airport_code, airport_name=airport_name)


@app.route('/search')
def search():
    """
    Airport name autocomplete endpoint.

    Accepts a query string parameter ``q`` and returns a JSON array of
    matching airports, each with ``icao``, ``iata``, ``name``, ``city``,
    and ``country`` fields.  Called by the frontend as the user types.
    """
    q = request.args.get('q', '').strip()
    return jsonify(search_airports(q))


if __name__ == '__main__':
    app.run(debug=True)
