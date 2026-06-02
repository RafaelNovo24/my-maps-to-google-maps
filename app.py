"""Streamlit UI for converting a Google My Maps into Google Maps links.

Lets the user supply a map by uploading a KML/KMZ file or pasting a My Maps
share link, then renders, per layer, the routable Google Maps links, a point
map, and a CSV download.
"""
from __future__ import annotations

import re

import streamlit as st

import converter

st.set_page_config(page_title="My Maps → Google Maps", page_icon="🗺️")
st.title("My Maps → Google Maps")
st.write("Convert a Google My Maps to routable Google Maps links, layer by layer.")

travel_mode = st.selectbox(
    "Travel mode",
    ["driving", "walking", "bicycling", "two-wheeler", "transit"],
)

input_method = st.radio(
    "Input method",
    ["Upload .kml / .kmz", "My Maps link"],
)


@st.cache_data(show_spinner=False)
def _layers_from_upload(name: str, data: bytes) -> list[converter.Layer]:
    """Parse layers from an uploaded file, caching the result.

    Args:
        name (str): The uploaded file's name, used to detect KML versus KMZ.
        data (bytes): The raw file contents.

    Returns:
        list[converter.Layer]: The layers parsed from the file.
    """
    return converter.parse_layers(converter.kml_from_upload(name, data))


@st.cache_data(show_spinner=False)
def _layers_from_link(url: str) -> list[converter.Layer]:
    """Parse layers from a My Maps share link, caching the result.

    Args:
        url (str): The My Maps share URL to fetch and parse.

    Returns:
        list[converter.Layer]: The layers parsed from the linked map.
    """
    return converter.parse_layers(converter.kml_from_mymaps_url(url))


layers: list[converter.Layer] | None = None

if input_method == "Upload .kml / .kmz":
    uploaded = st.file_uploader("Choose a .kml or .kmz file", type=["kml", "kmz"])
    if uploaded is not None:
        try:
            layers = _layers_from_upload(uploaded.name, uploaded.getvalue())
        except Exception as exc:
            st.error(str(exc))
else:
    url = st.text_input("Paste the My Maps share link")
    if url:
        try:
            layers = _layers_from_link(url)
        except Exception as exc:
            st.error(str(exc))

if layers is not None:
    total_points = sum(len(layer.points) for layer in layers)
    if total_points == 0:
        st.warning("No point markers found. Lines and polygons are not converted.")
    else:
        st.caption(
            "Only point markers are converted; lines and polygons are skipped. "
            "Google Maps caps waypoints per route, so long layers are split into legs."
        )
        for layer_index, layer in enumerate(layers):
            st.subheader(f"{layer.name} ({len(layer.points)} points)")
            if not layer.points:
                st.info(f"Layer '{layer.name}' has no point markers.")
                continue

            links = converter.build_route_links(layer.points, travel_mode=travel_mode)
            n = len(links)
            if n == 1:
                st.link_button(
                    "Open route in Google Maps",
                    links[0],
                    key=f"route_{layer_index}",
                )
            else:
                st.write(f"Split into {n} legs:")
                for i, link in enumerate(links, 1):
                    st.link_button(
                        f"Open leg {i} of {n}",
                        link,
                        key=f"leg_{layer_index}_{i}",
                    )

            st.map({"lat": [p.lat for p in layer.points], "lon": [p.lng for p in layer.points]})

            safe_name = re.sub(r"[^\w\-]+", "_", layer.name) or "layer"
            st.download_button(
                f"Download {layer.name}.csv",
                converter.points_to_csv(layer.points),
                file_name=f"{safe_name}.csv",
                mime="text/csv",
                key=f"csv_{layer_index}",
            )
