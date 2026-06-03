"""Streamlit app turning a Google My Maps KML export into Google Maps links.

Lets the user upload a ``.kml`` file, splits each routable layer into Google
Maps directions links, and shows a per-stretch summary with distance and
estimated-time totals in the selected language.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

import streamlit as st

import converter
import directions
import gpx
import i18n
import journey
from i18n import t


def _load_dotenv() -> None:
    """Load ``KEY=VALUE`` pairs from a local ``.env`` file into the environment.

    Reads a ``.env`` file beside this module, if present, and sets each pair in
    ``os.environ`` without overwriting variables already set, so shell- or
    container-provided values take precedence. This lets local runs pick up
    ``GOOGLE_MAPS_API_KEY`` without exporting it by hand. Blank lines, comment
    lines, and lines without an ``=`` are ignored.
    """
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


_load_dotenv()

st.set_page_config(page_title="Travel Assistant", page_icon=None)


def _flag_data_uri(filename: str) -> str:
    """Read an SVG flag from ``assets`` and return it as a base64 data URI.

    Args:
        filename (str): The SVG file name within the ``assets`` directory.

    Returns:
        str: A ``data:image/svg+xml;base64`` URI embedding the file contents,
            suitable for use as a CSS ``background-image``.
    """
    svg_bytes = (Path(__file__).parent / "assets" / filename).read_bytes()
    encoded = base64.b64encode(svg_bytes).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


if "lang" not in st.session_state:
    st.session_state["lang"] = i18n.DEFAULT_LANG

_col_main, _col_pt, _col_en = st.columns([8, 1, 1])
with _col_pt:
    if st.button(" ", key="lang_pt", help="Português"):
        st.session_state["lang"] = "pt"
with _col_en:
    if st.button(" ", key="lang_en", help="English"):
        st.session_state["lang"] = "en"

lang = st.session_state["lang"]

_pt_uri = _flag_data_uri("pt.svg")
_en_uri = _flag_data_uri("gb.svg")
_active_border = "2px solid #1a73e8"
_inactive_border = "2px solid transparent"
_pt_border = _active_border if lang == "pt" else _inactive_border
_en_border = _active_border if lang == "en" else _inactive_border
_pt_opacity = "1.0" if lang == "pt" else "0.45"
_en_opacity = "1.0" if lang == "en" else "0.45"

st.markdown(
    f"""<style>
.st-key-lang_pt button {{
    background-image: url('{_pt_uri}');
    background-size: cover;
    background-position: center;
    color: transparent !important;
    width: 48px;
    height: 32px;
    min-height: 32px;
    padding: 0;
    border: {_pt_border};
    border-radius: 3px;
    opacity: {_pt_opacity};
}}
.st-key-lang_en button {{
    background-image: url('{_en_uri}');
    background-size: cover;
    background-position: center;
    color: transparent !important;
    width: 48px;
    height: 32px;
    min-height: 32px;
    padding: 0;
    border: {_en_border};
    border-radius: 3px;
    opacity: {_en_opacity};
}}
</style>""",
    unsafe_allow_html=True,
)

st.title(t("title", lang))
st.write(t("subtitle", lang))

MODES = ["driving", "walking", "bicycling", "two-wheeler", "transit"]
travel_mode = st.selectbox(
    t("travel_mode_label", lang),
    MODES,
    format_func=lambda m: t(f"mode_{m}", lang),
)

uploaded = st.file_uploader(t("upload_label", lang), type=["kml"])


@st.cache_data(show_spinner=False)
def _layers_from_upload(name: str, data: bytes) -> list[converter.Layer]:
    """Parse uploaded KML/KMZ bytes into layers, caching by name and data.

    Args:
        name (str): The uploaded file's name, used to detect a KMZ archive.
        data (bytes): The raw uploaded file contents.

    Returns:
        list[converter.Layer]: The layers parsed from the file.
    """
    return converter.parse_layers(converter.kml_from_upload(name, data))


@st.cache_data(show_spinner=False)
def _estimate(coords: tuple, mode: str) -> directions.RouteEstimate:
    """Estimate a route for cached coordinates, keyed by coords and mode.

    Args:
        coords (tuple): The (latitude, longitude) pairs to route through, as a
            hashable tuple so the result can be cached.
        mode (str): The travel mode to estimate.

    Returns:
        directions.RouteEstimate: The estimate for the given coordinates.
    """
    return directions.estimate_route(list(coords), mode)


@st.cache_data(show_spinner=False)
def _convert_to_gpx(name: str, data: bytes) -> gpx.GpxResult:
    """Convert uploaded KML/KMZ bytes to a GPX result, cached by name and data."""
    return gpx.kml_to_gpx(converter.kml_from_upload(name, data))


if uploaded is not None:
    try:
        layers = _layers_from_upload(uploaded.name, uploaded.getvalue())
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    stretches = journey.route_stretches(layers)

    st.markdown(
        """<style>
a.gpx-jump-link {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border: 1px solid rgba(49,51,63,0.2);
    border-radius: 0.5rem;
    text-decoration: none;
    color: inherit;
    font-weight: 600;
}
a.gpx-jump-link:hover {
    border-color: #ff4b4b;
    color: #ff4b4b;
}
</style>""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<a class="gpx-jump-link" href="#gpx" target="_self">'
        f"{t('gpx_jump_button', lang)}</a>",
        unsafe_allow_html=True,
    )

    if not stretches:
        st.warning(t("no_stretches_warning", lang))
    else:
        st.caption(t("intro_caption", lang))

        ests: list[directions.RouteEstimate] = []
        links_per_stretch: list[list[str]] = []

        for s in stretches:
            coords = tuple((p.lat, p.lng) for p in s.points)
            est = _estimate(coords, travel_mode)
            links = converter.build_route_links(s.points, travel_mode=travel_mode)
            ests.append(est)
            links_per_stretch.append(links)

        rows = []
        for i, (s, est, links) in enumerate(zip(stretches, ests, links_per_stretch), 1):
            name_escaped = s.name.replace("|", r"\|")
            anchor = f"stretch-{i}"

            distance_text = est.distance_text if est.available else t("eta_unavailable", lang)
            time_text = est.duration_text if est.available else t("eta_unavailable", lang)

            if len(links) == 1:
                maps_md = f"[{t('open_in_maps', lang)}]({links[0]})"
            elif len(links) > 1:
                maps_md = f"[{t('links_count', lang, n=len(links))}](#{anchor})"
            else:
                maps_md = "—"

            rows.append(
                {
                    "num": i,
                    "name": name_escaped,
                    "anchor": anchor,
                    "distance_text": distance_text,
                    "time_text": time_text,
                    "maps_md": maps_md,
                }
            )

        st.subheader(t("summary_heading", lang))
        st.markdown(journey.summary_table_markdown(rows, lang))

        td = journey.total_distance_m(ests)
        tt = journey.total_duration_range_s(ests)
        col_dist, col_time = st.columns(2)
        col_dist.metric(t("total_distance", lang), journey.format_total_distance(td, lang))
        col_time.metric(t("total_time", lang), journey.format_total_time(tt, lang))

        if not directions.api_key_present():
            st.info(t("eta_needs_key", lang))

        for i, (s, est, links) in enumerate(zip(stretches, ests, links_per_stretch), 1):
            st.subheader(
                f"{t('stretch_word', lang)} {i}: {s.name}",
                anchor=f"stretch-{i}",
            )

            if est.available:
                st.write(f"{est.distance_text} · {est.duration_text}")

            if len(links) == 1:
                st.link_button(t("open_in_maps", lang), links[0], key=f"m_{i}")
            elif len(links) > 1:
                for j, link in enumerate(links, 1):
                    st.link_button(
                        t("link_n_of_m", lang, i=j, n=len(links)),
                        link,
                        key=f"m_{i}_{j}",
                    )

            if s.points:
                st.map({"lat": [p.lat for p in s.points], "lon": [p.lng for p in s.points]})

    st.divider()
    st.subheader(t("gpx_section_header", lang), anchor="gpx")
    _upload_token = f"{uploaded.name}:{len(uploaded.getvalue())}"
    if st.session_state.get("gpx_token") != _upload_token:
        st.session_state.pop("gpx_result", None)
        st.session_state["gpx_token"] = _upload_token
    if st.button(t("gpx_convert_button", lang), key="gpx_convert"):
        with st.spinner(t("gpx_converting", lang)):
            try:
                st.session_state["gpx_result"] = _convert_to_gpx(uploaded.name, uploaded.getvalue())
            # Any KML parse/convert failure must surface as a friendly UI error,
            # mirroring the existing broad catch above; narrowing it would change
            # behavior. pylint: disable=broad-exception-caught
            except Exception:
                st.session_state["gpx_result"] = None
                st.error(t("gpx_error", lang))
    _gpx_result = st.session_state.get("gpx_result")
    if _gpx_result is not None:
        if not _gpx_result.has_features:
            st.info(t("gpx_no_data", lang))
        else:
            if _gpx_result.skipped:
                st.caption(t("gpx_skipped", lang, n=_gpx_result.skipped))
            st.download_button(
                t("gpx_download_button", lang),
                data=_gpx_result.data,
                file_name=gpx.gpx_filename(uploaded.name),
                mime="application/gpx+xml",
                key="gpx_download",
            )
