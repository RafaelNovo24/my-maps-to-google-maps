# My Maps → Google Maps

A small Streamlit web app that converts a Google My Maps map into routable Google Maps links, one layer at a time.

## What it does

- Accepts a `.kml` upload, a `.kmz` upload, or a public My Maps share link.
- For each layer, generates ordered Google Maps directions route link(s) through that layer's points.
- Google Maps caps the number of stops per directions URL (~10), so layers with more than 10 points are split into multiple "legs" (consecutive legs share one point so they connect), order preserved.
- Also offers a per-layer CSV download and a map preview.

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
uv run pytest -q                                   # locally (43 tests)
docker compose run --rm app uv run pytest -q       # inside the container
```

## Getting your map out of My Maps

Two options:

1. **Export a file:** In Google My Maps, open the map → the **Menu (⋮)** in the left panel → **Export to KML/KMZ** → download the file. The app accepts **both `.kml` and `.kmz`**, so either format works.
2. **Public share link:** In My Maps, open **Share** and set the map so **anyone with the link can view it** (link sharing / public), then copy the link and paste it into the app. (Link import only works for publicly-shared maps; private maps will show an error.)

## Usage

Pick a travel mode, provide your input (file or link), then per layer click the route link(s) to open Google Maps, or download the CSV.

## Limitations

- Only **point markers** are converted; lines and polygons are skipped.
- The ~10-stop cap on Google Maps directions URLs is why long layers are split into legs.
- My Maps **link** import requires the map to be publicly shared.
