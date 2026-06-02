"""Convert Google My Maps exports into routable Google Maps links.

Provides helpers to load KML/KMZ data (from an uploaded file or a My Maps
share link), parse it into layers of point markers, and build Google Maps
directions URLs that respect the platform's per-route waypoint cap.
"""
from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from urllib.parse import parse_qs, quote, urlparse

import requests

MAX_STOPS_PER_LINK = 9
LEG_OVERLAP = 1
DEFAULT_TRAVEL_MODE = "driving"


@dataclass
class Point:
    """A single point marker extracted from a KML placemark.

    Attributes:
        name (str): The placemark's display name.
        lat (float): Latitude in decimal degrees.
        lng (float): Longitude in decimal degrees.
        description (str): The placemark's description text, if any.
    """

    name: str
    lat: float
    lng: float
    description: str = ""


@dataclass
class Layer:
    """A named group of point markers, mirroring a My Maps layer or folder.

    Attributes:
        name (str): The layer's display name.
        points (list[Point]): The point markers contained in the layer.
        has_route (bool): True when the layer contains at least one LineString.
    """

    name: str
    points: list[Point] = field(default_factory=list)
    has_route: bool = False


def kml_from_upload(filename: str, data: bytes) -> str:
    """Return the KML text contained in uploaded file bytes.

    Args:
        filename (str): The uploaded file's name; a ``.kmz`` suffix selects
            KMZ archive extraction, otherwise the bytes are treated as KML.
        data (bytes): The raw file contents.

    Returns:
        str: The decoded KML document text.

    Raises:
        ValueError: If ``data`` is empty, or if a ``.kmz`` archive contains
            no KML entry.
    """
    if not data:
        raise ValueError("data is empty")
    if filename.lower().endswith(".kmz"):
        text = _extract_kml_from_kmz(data)
    else:
        text = data.decode("utf-8")
    _reject_networklink_stub(text)
    return text


def _extract_kml_from_kmz(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        if "doc.kml" in names:
            return zf.read("doc.kml").decode("utf-8")
        kml_entries = [n for n in names if n.lower().endswith(".kml")]
        if not kml_entries:
            raise ValueError("No KML found in KMZ archive")
        return zf.read(kml_entries[0]).decode("utf-8")


def _reject_networklink_stub(text: str) -> None:
    if "<NetworkLink" not in text:
        return
    if "<Placemark" in text:
        return
    raise ValueError(
        "This file only links to an online My Maps map and contains no points. "
        "In My Maps, export the map as KML (with its data) and upload that file."
    )


def mymaps_export_url(url: str) -> str:
    """Build the KML export URL for a My Maps share link.

    Args:
        url (str): A My Maps URL containing a ``mid`` query parameter.

    Returns:
        str: The corresponding ``maps/d/kml`` export URL with ``forcekml=1``.

    Raises:
        ValueError: If no ``mid`` parameter can be found in ``url``.
    """
    mid = _extract_mid(url)
    return f"https://www.google.com/maps/d/kml?mid={mid}&forcekml=1"


def _extract_mid(url: str) -> str:
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "mid" in qs:
        return qs["mid"][0]
    # treat the whole input as a bare mid value if it looks like one
    # (no host, no path that matches a maps URL)
    raise ValueError(f"No 'mid' parameter found in URL: {url!r}")


def _ensure_kml(text: str) -> str:
    head = text.lstrip()[:1000]
    if head.startswith("<?xml") or "<kml" in head:
        return text
    raise ValueError(
        "The My Maps response was not KML. The map must be publicly shared "
        "(set link sharing to 'Anyone with the link can view')."
    )


def kml_from_mymaps_url(url: str, timeout: int = 30) -> str:
    """Fetch and return the KML text for a My Maps share link.

    Args:
        url (str): A My Maps share URL containing a ``mid`` parameter.
        timeout (int, optional): Per-request timeout in seconds. Defaults to 30.

    Returns:
        str: The KML document text, decoding a KMZ response if one is returned.

    Raises:
        ValueError: If no ``mid`` parameter is found or the response is not KML.
        requests.HTTPError: If the export request returns an error status.
    """
    export = mymaps_export_url(url)
    resp = requests.get(export, timeout=timeout)
    resp.raise_for_status()
    if resp.content.startswith(b"PK"):
        return kml_from_upload("doc.kmz", resp.content)
    return _ensure_kml(resp.text)


def parse_layers(kml_text: str) -> list[Layer]:
    """Parse KML text into layers of point markers.

    Each KML ``Folder`` becomes one layer; if the document has no folders,
    all placemarks are collected into a single layer named after the document.

    Args:
        kml_text (str): The KML document text to parse.

    Returns:
        list[Layer]: One layer per folder, or a single fallback layer when the
            document contains no folders.
    """
    root = ET.fromstring(kml_text)
    ns = _kml_namespace(root)
    document = root.find(_tag(ns, "Document"))
    if document is None:
        document = root

    folders = document.findall(_tag(ns, "Folder"))
    if folders:
        return [_layer_from_folder(folder, ns, index) for index, folder in enumerate(folders, 1)]

    doc_name = _text(document.find(_tag(ns, "name"))) or "Layer 1"
    points = _placemarks_to_points(document, ns)
    has_route = document.find(".//" + _tag(ns, "LineString")) is not None
    return [Layer(name=doc_name, points=points, has_route=has_route)]


def _kml_namespace(root: ET.Element) -> str:
    tag = root.tag
    if tag.startswith("{"):
        return tag[1: tag.index("}")]
    return ""


def _tag(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}" if ns else local


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return (element.text or "").strip()


def _layer_from_folder(folder: ET.Element, ns: str, index: int) -> Layer:
    name = _text(folder.find(_tag(ns, "name"))) or f"Layer {index}"
    points = _placemarks_to_points(folder, ns)
    has_route = folder.find(".//" + _tag(ns, "LineString")) is not None
    return Layer(name=name, points=points, has_route=has_route)


def _placemarks_to_points(parent: ET.Element, ns: str) -> list[Point]:
    points: list[Point] = []
    for placemark in parent.findall(_tag(ns, "Placemark")):
        point = _point_from_placemark(placemark, ns)
        if point is not None:
            points.append(point)
    return points


def _point_from_placemark(placemark: ET.Element, ns: str) -> Point | None:
    point_elem = placemark.find(_tag(ns, "Point"))
    if point_elem is None:
        return None
    coords_elem = point_elem.find(_tag(ns, "coordinates"))
    if coords_elem is None:
        return None
    coord_text = _text(coords_elem)
    if not coord_text:
        return None
    parts = coord_text.split(",")
    if len(parts) < 2:
        return None
    try:
        lng = float(parts[0].strip())
        lat = float(parts[1].strip())
    except ValueError:
        return None
    name = _text(placemark.find(_tag(ns, "name")))
    description = _text(placemark.find(_tag(ns, "description")))
    return Point(name=name, lat=lat, lng=lng, description=description)


def build_route_links(
    points: list[Point],
    max_stops: int = MAX_STOPS_PER_LINK,
    overlap: int = LEG_OVERLAP,
    travel_mode: str = DEFAULT_TRAVEL_MODE,
) -> list[str]:
    """Build Google Maps links covering an ordered sequence of points.

    Fewer than two points yields an empty list. Otherwise the points are split
    into overlapping legs (because Google Maps caps waypoints per route) and
    each leg becomes one directions link with no origin, so the user can supply
    their own starting point in Google Maps.

    Args:
        points (list[Point]): The ordered points to route through.
        max_stops (int, optional): Maximum points per directions link.
            Defaults to MAX_STOPS_PER_LINK.
        overlap (int, optional): Number of points shared between consecutive
            legs so routes join up. Defaults to LEG_OVERLAP.
        travel_mode (str, optional): Google Maps travel mode. Defaults to
            DEFAULT_TRAVEL_MODE.

    Returns:
        list[str]: One Google Maps URL per leg, or an empty list when
            ``points`` has fewer than two entries.
    """
    if len(points) < 2:
        return []

    legs = _split_into_legs(points, max_stops, overlap)
    return [_leg_url(leg, travel_mode) for leg in legs]


def _split_into_legs(
    points: list[Point], max_stops: int, overlap: int
) -> list[list[Point]]:
    if len(points) <= max_stops:
        return [points]
    step = max_stops - overlap
    legs: list[list[Point]] = []
    start = 0
    while start < len(points):
        end = start + max_stops
        leg = points[start:end]
        legs.append(leg)
        if end >= len(points):
            break
        start += step
    return legs


def _coord(p: Point) -> str:
    return quote(f"{p.lat},{p.lng}")


def _leg_url(leg: list[Point], travel_mode: str) -> str:
    destination = _coord(leg[-1])
    base = f"https://www.google.com/maps/dir/?api=1&destination={destination}"
    waypoints_points = leg[:-1]
    if waypoints_points:
        waypoints = "%7C".join(_coord(p) for p in waypoints_points)
        base += f"&waypoints={waypoints}"
    base += f"&travelmode={travel_mode}"
    return base
