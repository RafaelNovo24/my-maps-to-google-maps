"""Streamlit UI for converting a Google My Maps into Google Maps links.

Lets the user supply a map by uploading a KML file or pasting a My Maps
share link, then renders, per layer, the routable Google Maps links and a
point map preview.
"""
from __future__ import annotations

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
    ["Upload .kml", "My Maps link"],
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

if input_method == "Upload .kml":
    uploaded = st.file_uploader("Choose a .kml file", type=["kml"])
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
            "Each route link opens with an empty start so you can add your own starting point — "
            "Google Maps will prepend it before the layer's stops. "
            "Long layers are split into legs (up to 9 stops per link)."
        )
        for layer_index, layer in enumerate(layers):
            st.subheader(f"{layer.name} ({len(layer.points)} points)")
            if len(layer.points) >= 2:
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
            else:
                st.info(
                    f"{len(layer.points)} point(s) of interest — no route link (needs at least 2 points)."
                )

            if layer.points:
                st.map({"lat": [p.lat for p in layer.points], "lon": [p.lng for p in layer.points]})
