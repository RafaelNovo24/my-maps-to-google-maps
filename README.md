# My Maps → Google Maps

A small Streamlit web app that converts a Google My Maps map into routable Google Maps links, one layer at a time.

## What it does

- Accepts a `.kml` upload or a public My Maps share link.
- For each layer with at least 2 points, generates ordered Google Maps directions route link(s) through that layer's points.
- Each route link **opens with an empty start** — Google Maps asks for your starting point before the layer's stops, so you can set your own origin.
- Google Maps caps the number of stops per directions URL (up to 9 per link), so layers with more than 9 points are split into multiple "legs" (consecutive legs share one point so they connect), order preserved.
- Layers with fewer than 2 points are listed with a note but no route link.
- A map preview is shown for any layer that has at least 1 point.

## Run with Docker (recommended)

```
docker compose up
```

Then open http://localhost:8501 . Stop with Ctrl+C (or `docker compose down` if started detached with `docker compose up -d`).

## Run locally (without Docker)

Requires [uv](https://docs.astral.sh/uv/).

```
uv run streamlit run app.py
```

Opens at http://localhost:8501 .

## Tests

```
uv run pytest -q                                   # locally
docker compose run --rm app uv run pytest -q       # inside the container
```

## Getting your map out of My Maps

Two options:

1. **Export a file:** In Google My Maps, open the map → the **Menu (⋮)** in the left panel → **Export to KML/KMZ** → choose **KML** format and download the file. The app accepts `.kml` files.
2. **Public share link:** In My Maps, open **Share** and set the map so **anyone with the link can view it** (link sharing / public), then copy the link and paste it into the app. (Link import only works for publicly-shared maps; private maps will show an error.)

## Usage

Pick a travel mode, provide your input (file or link), then per layer click the route link(s) to open Google Maps. Each link opens with no starting point pre-filled — add your own starting point in Google Maps.

## Limitations

- Only **point markers** are converted; lines and polygons are skipped.
- The 9-stop cap on Google Maps directions URLs is why long layers are split into legs.
- My Maps **link** import requires the map to be publicly shared.
- KMZ upload is not supported via the UI; export your map as `.kml` from My Maps.
