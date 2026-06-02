"""Streamlit app turning a Google My Maps KML export into Google Maps links.

Lets the user upload a ``.kml`` file, splits each routable layer into Google
Maps directions links, and shows a per-stretch summary with distance and
estimated-time totals in the selected language.
"""
from __future__ import annotations

import streamlit as st

import converter
import directions
import i18n
import journey
from i18n import t

st.set_page_config(page_title="My Maps → Google Maps", page_icon="🗺️")

lang = st.selectbox(
    i18n.t("language_label", "pt"),
    i18n.LANGUAGES,
    format_func=lambda c: {"pt": "Português", "en": "English"}[c],
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


if uploaded is not None:
    try:
        layers = _layers_from_upload(uploaded.name, uploaded.getvalue())
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    stretches = journey.route_stretches(layers)

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
