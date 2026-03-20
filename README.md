# METAR Reader

A Flask web application that fetches live METAR weather reports and translates them from their cryptic encoded format into plain English.

METAR (Meteorological Aerodrome Report) is the international standard format for weather observations at airports. A raw METAR looks like this:

```
METAR EGLL 201020Z AUTO 04006KT 9999 NCD 10/04 Q1023 NOSIG
```

METAR Reader turns that into a friendly summary:

> **Clear skies and cool**
> From the north-east (40°) at 6.9 mph · Visibility: more than 10 km · 10°C (50°F) · 1023 hPa

## Features

- **Airport search** — start typing an airport name, city, or code and select from a live autocomplete dropdown (backed by the [OurAirports](https://ourairports.com) dataset of 17,000+ airports)
- **Full METAR decoding** — wind direction and speed, gusts, visibility, sky conditions, cloud layers, weather phenomena (rain, snow, fog, thunderstorms, etc.), temperature, dew point, and pressure
- **Wind chill and heat index** — calculated automatically where conditions apply
- **Plain-English headline** — a one-line summary of current conditions
- **Raw METAR** — shown in a collapsible section for reference

## Requirements

- Python 3.12+
- An internet connection (to fetch live METAR data and download the airport dataset on first run)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/metar.git
cd metar
```

### 2. Create a virtual environment and install dependencies

Using [uv](https://github.com/astral-sh/uv) (recommended):

```bash
uv venv
uv pip install -r requirements.txt
```

Or with the standard library:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the application

```bash
flask run
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

> **Note:** On first run, the app downloads the OurAirports airport dataset (~6 MB) and caches it locally as `.airports_cache.json`. This is a one-off download; the cache is refreshed automatically once a week.

## Data sources

| Source | Purpose |
|---|---|
| [Aviation Weather Center](https://aviationweather.gov) | Live METAR reports |
| [OurAirports](https://ourairports.com) | Airport name and code database |

## Deployment

For production use, run the app with a WSGI server such as [Gunicorn](https://gunicorn.org):

```bash
pip install gunicorn
gunicorn app:app
```

## Licence

This project is released into the public domain under the [Unlicence](https://unlicense.org). Do whatever you want with it.
