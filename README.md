# My Maps → Google Maps

A small Streamlit web app that turns a Google **My Maps** route into routable
**Google Maps** links — stretch by stretch — with distances and estimated travel
times. The interface is available in **Portuguese** (default) and **English**.

## What it does

- Upload a `.kml` file exported from Google My Maps.
- Each route **stretch** (a My Maps *Directions* layer that has a drawn path)
  becomes ordered Google Maps directions link(s). Pin-only layers (no route) are
  hidden.
- Each link **opens with an empty start**, so you add your own starting point and
  Google Maps routes through the stretch's stops. Google caps stops per link (up
  to 9 here), so long stretches are split into several links.
- A **journey summary table** lists every stretch with its description,
  **distance**, **estimated time range**, and a Google Maps link. Click a
  stretch's description to jump to its detail section (links + map preview).
- **Total distance and time** for the whole journey are shown.

## Distance & time — Google API key

Distances and times come from the **Google Routes API**, which needs an API key
from a **billing-enabled** Google Cloud project (enable the *Routes API*).

- Provide it via the environment variable **`GOOGLE_MAPS_API_KEY`**.
- **Without a key the app still works** — it shows the stretches, the summary
  table, and the Google Maps links — but the distance/time cells read
  "unavailable".
- Driving uses an optimistic–pessimistic *range* (two API calls per stretch);
  other travel modes show a single estimate. Routes API calls are billed per
  request (traffic-aware calls cost more) — check current Google pricing.

## Run with Docker (recommended)

```
# bash:        export GOOGLE_MAPS_API_KEY="your-key"
# PowerShell:  $env:GOOGLE_MAPS_API_KEY = "your-key"
docker compose up
```

Then open http://localhost:8501 . Compose passes `GOOGLE_MAPS_API_KEY` from your
environment into the container (omit it to run without ETAs). Stop with Ctrl+C
(or `docker compose down`).

## Run locally (without Docker)

Requires [uv](https://docs.astral.sh/uv/).

```
GOOGLE_MAPS_API_KEY="your-key" uv run streamlit run app.py     # or omit the key
```

Opens at http://localhost:8501 .

## Tests

```
uv run pytest -q                                   # locally
docker compose run --rm app uv run pytest -q       # inside the container
```

## Getting your map out of My Maps

In Google My Maps, open the map → the **Menu (⋮)** in the left panel →
**Export to KML/KMZ** → choose **KML** → download the file, then upload it here.
(KMZ upload isn't supported via the UI yet — export as KML.)

## Languages

Use the selector at the top to switch between **Português** (default) and
**English**. Your map's own labels (layer names, etc.) are shown as they appear
in the KML.

## Limitations

- Only route **stretches** are converted; pin-only layers are hidden, and lines /
  polygons aren't drawn.
- The 9-stop cap on Google Maps directions URLs is why long stretches split into
  multiple links.
- Distance/time need a `GOOGLE_MAPS_API_KEY` (billed Routes API); without it the
  app still produces links.
- KMZ upload and pasting a My Maps share link aren't available (KML upload only).
