# Plan: My Maps → Google Maps converter

A small **Streamlit** app where a user supplies a Google My Maps map (as a `.kml`
upload, `.kmz` upload, or a public My Maps share link), and the app produces,
**per layer**, ordered Google Maps directions route link(s) through that layer's
points — splitting into multiple chunked links when a layer has more than 10
stops (Google's directions cap), preserving order. Runs in Docker, with tests.

## Requirements (confirmed)

| Topic                | Decision                                                                                            |
| -------------------- | --------------------------------------------------------------------------------------------------- |
| **Input**            | All three: `.kml` upload, `.kmz` upload, and a public My Maps share link.                            |
| **Geometry**         | Points / markers only. Lines & polygons are skipped with a warning.                                 |
| **Output**           | One Google Maps `dir` route link per layer. If a layer has >10 points, split into legs (see below). |
| **Chunking**         | Legs of up to 10 stops, in order, with a **1-point overlap** so consecutive legs connect.           |
| **Interface**        | Streamlit web app (`st.map` preview, no folium).                                                    |
| **Bonus**            | Per-layer CSV download, so all points are recoverable.                                              |
| **Conventions**      | Standard **PEP 8** (snake_case incl. arguments; lowercase filenames). Lobito-hardcoded agents overridden. |
| **Orchestration**    | Main session is the single orchestrator, running the cycle **autonomously** (see `WORKFLOW.md`).    |
| **Containerization** | **Docker**: `Dockerfile` + `docker-compose.yml`, uv-based, port 8501.                               |
| **Testing**          | `pytest` on `converter.py` + a Streamlit `AppTest` smoke test, run in Docker.                       |

## Key constraint

Google Maps (the consumer app) has **no public API to import a custom map or
bulk-add pins**. The closest Google product for custom maps *is* My Maps. So a
directions route link is the practical way to get a layer's waypoints into the
real Google Maps app — and those URLs are capped at ~10 stops, which is why
layers are split into chunked legs.

## Files

### Application
- **`converter.py`** — pure logic, no UI:
  - `kml_from_upload(filename, data: bytes) -> str` — decode `.kml`, or unzip
    `.kmz` (`zipfile`) and read its `doc.kml`.
  - `mymaps_export_url(url: str) -> str` — **pure**: extract the `mid=` param and
    build `https://www.google.com/maps/d/kml?mid={mid}&forcekml=1`. (Split out
    from the fetch so it is testable without network.)
  - `kml_from_mymaps_url(url: str) -> str` — call `mymaps_export_url` then fetch
    via `requests` (public maps only; clear error otherwise).
  - `parse_layers(kml_text: str) -> list[Layer]` — `xml.etree.ElementTree` with
    the KML namespace; each `<Folder>` is a layer; fall back to a single layer if
    none. Each point = `{name, lat, lng, description}`. Non-point geometry skipped.
  - `build_route_links(points, max_stops=10, overlap=1) -> list[str]` — chunk in
    order, build `https://www.google.com/maps/dir/?api=1&origin=…&destination=…&waypoints=…|…&travelmode=…`.
  - `points_to_csv(points) -> str` — columns `name,latitude,longitude,description`.
  - Module-level constants for the stop limit, overlap, and travel mode.
- **`app.py`** — Streamlit UI: input-method radio; `.kml`/`.kmz` uploader; link
  text box; per-layer route link(s); `st.map` preview; per-layer CSV download;
  travel-mode dropdown; warnings for skipped geometry and non-public links.

### Tests
- **`tests/test_converter.py`** — parsing (multi-folder / single / non-point
  skipped), `mymaps_export_url` derivation (no network), chunking + overlap +
  order, `dir` URL format, `.kmz` unzip (built in-memory with `zipfile`), CSV.
- **`tests/test_app_smoke.py`** — `streamlit.testing.v1.AppTest`: load `app.py`,
  `.run()`, assert no exception; minimal interaction to confirm UI ↔ converter.

### Container
- **`Dockerfile`** — uv-based image (`ghcr.io/astral-sh/uv:python3.12-bookworm-slim`),
  `uv sync --frozen`, `EXPOSE 8501`,
  `CMD streamlit run app.py --server.port=8501 --server.address=0.0.0.0`.
  *(Note: local `.python-version` is 3.14; Docker pins 3.12 for wheel stability —
  align later if desired.)*
- **`docker-compose.yml`** — one service, `build: .`, `ports: ["8501:8501"]`.
- **`.dockerignore`** — `.git`, `.venv`, `__pycache__`, etc.

### Config / tooling / docs
- **`pyproject.toml`** — add deps `streamlit`, `requests`; dev dep `pytest`; add a
  `[tool.pylint]` block configuring **snake_case argument & module naming** so the
  sanitizer keeps PEP 8.
- **`template.mustache`** — project-local docstring template (PEP 8 style) so
  `code-sanitizer`/`docstring-filler` don't fall back to defaults or prompt.
- **`README.md`** — run via `docker compose up`, how to export a `.kml` / get a
  share link from My Maps, how to run the tests, and the limitations.
- Remove the placeholder **`main.py`**.

## Build sequence

Each step is **one `python-implementer` run** (with the override briefing in
`WORKFLOW.md`) → **one `Doublecheck`** → the **orchestrator runs tests/Docker**.
The orchestrator runs the whole sequence autonomously, looping back to planning
only on a failed step.

### Step 1 — Setup & tooling
- **Files:** `pyproject.toml` (deps + dev `pytest` + `[tool.pylint]` PEP 8),
  `template.mustache`, `.dockerignore`; delete `main.py`.
- **Done when:** `uv sync` resolves; deps present.
- **Doublecheck:** dependency names valid; pylint config actually allows snake_case args.

### Step 2 — `converter.py` + `tests/test_converter.py`
- Implement all converter functions and their unit tests; run `uv run pytest -q`.
- **Done when:** tests pass; ≤10 points → 1 link; >10 → chunked legs of 10 with
  1-point overlap, order preserved; `.kmz` unzips; `mymaps_export_url` correct.
- **Doublecheck (riskiest external assumptions):** My Maps KML export URL, Google
  Maps `dir` URL format + stop cap, KML Folder/Placemark/Point structure;
  adversarial review of chunking/overlap/order.
- **Doublecheck outcome (2026-06-02):** `dir`/`search` URL formats verified;
  waypoint cap is 9 (our 8 is safe); KML `lng,lat` order — converter swaps
  correctly. **Refinements applied:** (a) percent-encode coordinates and the `|`
  separator in generated URLs (`%2C` / `%7C`); (b) guard `kml_from_mymaps_url`
  to reject non-KML (HTML) responses with a clear "map must be publicly shared"
  error, since the export endpoint is undocumented.

### Step 3 — `app.py` + `tests/test_app_smoke.py`
- Implement the UI and the `AppTest` smoke test; run `uv run pytest -q`.
- **Done when:** all three input paths flow through `converter.py`; smoke test
  passes (no exception).
- **Doublecheck:** UI ↔ converter wiring, error handling, and the `AppTest` API usage.

### Step 4 — Docker
- **Files:** `Dockerfile`, `docker-compose.yml`.
- **Orchestrator verifies:** `docker compose build`, run tests in the container
  (`docker compose run --rm app uv run pytest -q`), and `docker compose up` →
  confirm Streamlit serves on 8501.
- **Doublecheck:** uv-in-Docker pattern, `uv sync --frozen`, Streamlit server flags.

### Step 5 — `README.md`
- Run command, My Maps export instructions, test command, limitations.
- **Doublecheck:** instructions match the actual files/commands.

### Final — `code-sanitizer` (overridden) + regression check
- Run with the `WORKFLOW.md` sanitizer briefing (PEP 8; no camelCase args; no
  file renames). Then the orchestrator **re-runs the tests** and confirms no
  argument/file renames slipped in.

## Limitations surfaced in the UI
- Google Maps directions URLs are capped (~10 stops) — hence chunked legs.
- My Maps link import only works for **publicly shared** maps.
- Lines/polygons are ignored (points only).

## Verification
- `pytest` (in Docker) covers parsing, layer split, chunking/overlap/order, URL
  format, `.kmz`, and CSV; `AppTest` smoke-tests `app.py`.
- `docker compose up` serves the app on 8501; manual check: upload a `.kml`,
  import a share link, and confirm generated links open correctly in Google Maps.

## Post-build enhancements

### NetworkLink-stub KMZ handling (2026-06-02)
My Maps KMZ exports are frequently a `<NetworkLink>` stub: the inner `doc.kml`
just links to the online map's `maps/d/kml?mid=...` URL and contains **no
placemarks** (confirmed against a real sample). Decision (per user): for now,
**show a helpful message** — `kml_from_upload` detects the stub and raises a
`ValueError` that directs the user to paste the embedded map link into the link
box (or export as KML); the app already surfaces it via `st.error`. Fast-path
string check so normal/large KML isn't double-parsed.
**Deferred:** actually following the NetworkLink to fetch the linked KML
("opening KMZ") — future work.

### Change request #2 (2026-06-02): empty start, 9 slots, KML-only UI, no CSV
- **Route vs. mention:** a layer with **≥2 points** gets Google Maps route
  link(s); a layer with **0–1 points** is just mentioned, no link (per user:
  "2+ points = route"). No `<LineString>` parsing needed.
- **Empty starting slot:** each route link leaves the **origin empty** so the
  user adds their own start; the layer's points fill up to **9 slots**
  (waypoints + destination). `MAX_STOPS_PER_LINK` 10 → **9**; layers over 9
  points split into legs of 9 (1-pt overlap). The single-point search-link
  branch is removed. Exact empty-origin URL form is Doublecheck-verified.
- **Remove CSV:** delete the per-layer CSV download button and `points_to_csv`
  (+ its tests).
- **KML-only UI:** the file uploader accepts **`.kml` only** (drop `.kmz`). The
  converter's KMZ code stays for the deferred "open KMZ" work. The My Maps
  **link input and travel-mode dropdown are kept**.
