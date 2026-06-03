"""Convert KML documents to GPX format.

Provides a faithful, stdlib-only KML → GPX converter that maps KML
``Point`` placemarks to GPX ``<wpt>`` elements and KML ``LineString``
placemarks to GPX ``<trk>`` elements.  ``Polygon`` and any other
geometry types are silently skipped and counted.
"""
# This module deliberately reuses converter's internal KML helpers
# (_kml_namespace, _tag, _text) to stay byte-for-byte consistent with the
# existing KML parsing. Those helpers are not part of converter's public API
# and must not be promoted to public here, so protected-access is disabled
# module-wide rather than narrowing the catch or duplicating the logic.
# pylint: disable=protected-access
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

import converter as _converter

_GPX_NS = "http://www.topografix.com/GPX/1/1"
_GPX_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
_GPX_SCHEMA_LOC = (
    "http://www.topografix.com/GPX/1/1 "
    "http://www.topografix.com/GPX/1/1/gpx.xsd"
)


@dataclass
class GpxResult:
    """The outcome of a KML-to-GPX conversion.

    Attributes:
        data (bytes): Serialized UTF-8 GPX document (with XML declaration).
        waypoints (int): Number of ``<wpt>`` elements emitted.
        tracks (int): Number of ``<trk>`` elements emitted.
        skipped (int): Number of geometry elements skipped (e.g. Polygons).
    """

    data: bytes
    waypoints: int
    tracks: int
    skipped: int

    @property
    def has_features(self) -> bool:
        """Return True when at least one waypoint or track was emitted.

        Returns:
            bool: True when ``waypoints + tracks > 0``.
        """
        return self.waypoints + self.tracks > 0


def kml_to_gpx(kml_text: str, *, creator: str = "Travel Assistant") -> GpxResult:
    """Convert a KML document string to a GPX document.

    Walks every ``Placemark`` in the KML tree, including those nested inside
    ``Folder`` elements at any depth.  Within each placemark, handles
    geometries nested in ``MultiGeometry`` as well as top-level geometry.

    ``Point`` placemarks become ``<wpt>`` elements; ``LineString`` placemarks
    become ``<trk>/<trkseg>`` elements.  All other geometry types (e.g.
    ``Polygon``) are skipped and counted in the returned ``skipped`` total.

    KML coordinate order is ``lon,lat[,alt]``; this function swaps them to
    the GPX convention of ``lat`` / ``lon`` attributes.

    Args:
        kml_text (str): The KML document text to convert.
        creator (str, optional): The ``creator`` attribute on the GPX root
            element.  Defaults to ``"Travel Assistant"``.

    Returns:
        GpxResult: The serialized GPX document together with conversion
            statistics.

    Raises:
        xml.etree.ElementTree.ParseError: If ``kml_text`` is not valid XML.
        ValueError: If the parsed document does not look like a KML file.
    """
    root = ET.fromstring(kml_text)
    ns = _converter._kml_namespace(root)

    ET.register_namespace("", _GPX_NS)
    ET.register_namespace("xsi", _GPX_XSI_NS)
    gpx_root = ET.Element(
        f"{{{_GPX_NS}}}gpx",
        attrib={
            "version": "1.1",
            "creator": creator,
            f"{{{_GPX_XSI_NS}}}schemaLocation": _GPX_SCHEMA_LOC,
        },
    )

    waypoints = 0
    tracks = 0
    skipped = 0

    for placemark, folder_name in _iter_placemarks(root, ns):
        wpts, trks, skip = _convert_placemark(placemark, folder_name, ns, gpx_root)
        waypoints += wpts
        tracks += trks
        skipped += skip

    data = ET.tostring(gpx_root, encoding="utf-8", xml_declaration=True)
    return GpxResult(data=data, waypoints=waypoints, tracks=tracks, skipped=skipped)


def gpx_filename(kml_name: str) -> str:
    """Derive a GPX download filename from a KML/KMZ filename.

    Strips a trailing ``.kml`` or ``.kmz`` extension (case-insensitive) and
    appends ``.gpx``.  Returns ``"travel.gpx"`` when ``kml_name`` is empty
    or falsy.

    Args:
        kml_name (str): The original uploaded filename.

    Returns:
        str: A filename with the ``.gpx`` extension.
    """
    if not kml_name:
        return "travel.gpx"
    lower = kml_name.lower()
    if lower.endswith(".kml") or lower.endswith(".kmz"):
        return kml_name[:-4] + ".gpx"
    return kml_name + ".gpx"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iter_placemarks(root: ET.Element, ns: str):
    """Yield every Placemark in the tree together with its enclosing Folder name.

    Args:
        root (ET.Element): The root element of the parsed KML document.
        ns (str): The KML namespace URI.

    Yields:
        tuple[ET.Element, str]: Each ``(placemark_element, folder_name)`` pair
            found anywhere in the tree.
    """
    placemark_tag = _converter._tag(ns, "Placemark")
    folder_tag = _converter._tag(ns, "Folder")
    name_tag = _converter._tag(ns, "name")

    def _walk(element: ET.Element, current_folder_name: str):
        for child in element:
            if child.tag == placemark_tag:
                yield child, current_folder_name
            elif child.tag == folder_tag:
                fname = _converter._text(child.find(name_tag)) or current_folder_name
                yield from _walk(child, fname)
            else:
                yield from _walk(child, current_folder_name)

    yield from _walk(root, "")


def _convert_placemark(
    placemark: ET.Element,
    folder_name: str,
    ns: str,
    gpx_root: ET.Element,
) -> tuple[int, int, int]:
    """Convert a single Placemark element into GPX children on gpx_root.

    Args:
        placemark (ET.Element): The ``Placemark`` element to process.
        folder_name (str): The name of the enclosing ``Folder``, used as a
            fallback track name when the placemark itself has no name.
        ns (str): The KML namespace URI.
        gpx_root (ET.Element): The GPX root element to append children to.

    Returns:
        tuple[int, int, int]: ``(waypoints_added, tracks_added, geoms_skipped)``.
    """
    name_tag = _converter._tag(ns, "name")
    desc_tag = _converter._tag(ns, "description")
    multi_tag = _converter._tag(ns, "MultiGeometry")
    point_tag = _converter._tag(ns, "Point")
    line_tag = _converter._tag(ns, "LineString")
    poly_tag = _converter._tag(ns, "Polygon")

    placemark_name = _converter._text(placemark.find(name_tag))
    description = _converter._text(placemark.find(desc_tag))
    track_name = placemark_name or folder_name

    waypoints = 0
    tracks = 0
    skipped = 0

    def _handle_geoms(container: ET.Element) -> None:
        nonlocal waypoints, tracks, skipped
        for child in container:
            if child.tag == point_tag:
                coords_elem = child.find(_converter._tag(ns, "coordinates"))
                coord_text = _converter._text(coords_elem)
                parsed = _parse_single_coord(coord_text)
                if parsed is not None:
                    _add_wpt(gpx_root, parsed, placemark_name, description)
                    waypoints += 1
            elif child.tag == line_tag:
                coords_elem = child.find(_converter._tag(ns, "coordinates"))
                coord_text = _converter._text(coords_elem)
                trkpts = _parse_coord_sequence(coord_text)
                if trkpts:
                    _add_trk(gpx_root, trkpts, track_name)
                    tracks += 1
            elif child.tag == poly_tag:
                skipped += 1
            elif child.tag == multi_tag:
                _handle_geoms(child)

    _handle_geoms(placemark)
    return waypoints, tracks, skipped


def _parse_single_coord(text: str) -> tuple[float, float, float | None] | None:
    """Parse a single KML coordinate tuple (lon,lat[,alt]).

    Args:
        text (str): A single coordinate string such as ``"10.0,20.0,0"``.

    Returns:
        tuple[float, float, float | None] | None: ``(lon, lat, alt)`` where
            ``alt`` is ``None`` when the coordinate has only two values, or
            ``None`` when parsing fails.
    """
    text = text.strip()
    if not text:
        return None
    parts = text.split(",")
    if len(parts) < 2:
        return None
    try:
        lon = float(parts[0].strip())
        lat = float(parts[1].strip())
        alt = float(parts[2].strip()) if len(parts) >= 3 else None
        return lon, lat, alt
    except ValueError:
        return None


def _parse_coord_sequence(text: str) -> list[tuple[float, float, float | None]]:
    """Parse a KML coordinate sequence into a list of (lon, lat, alt) tuples.

    Coordinate tuples are separated by any whitespace; each tuple is
    comma-separated.  Malformed tuples are silently skipped.

    Args:
        text (str): The raw ``<coordinates>`` text, e.g.
            ``"10.0,20.0,0 11.0,21.0,0\\n12.0,22.0"``.

    Returns:
        list[tuple[float, float, float | None]]: The successfully parsed
            coordinate tuples.
    """
    results: list[tuple[float, float, float | None]] = []
    for token in text.split():
        parsed = _parse_single_coord(token)
        if parsed is not None:
            results.append(parsed)
    return results


def _add_wpt(
    gpx_root: ET.Element,
    coord: tuple[float, float, float | None],
    name: str,
    description: str,
) -> None:
    """Append a <wpt> element to gpx_root.

    Args:
        gpx_root (ET.Element): The GPX root element.
        coord (tuple[float, float, float | None]): ``(lon, lat, alt)`` tuple.
        name (str): The placemark name for the ``<name>`` child element.
        description (str): The placemark description for the ``<desc>`` child
            element; omitted when empty.
    """
    lon, lat, alt = coord
    wpt = ET.SubElement(gpx_root, f"{{{_GPX_NS}}}wpt", attrib={"lat": str(lat), "lon": str(lon)})
    if alt is not None:
        _sub_text(wpt, "ele", str(alt))
    if name:
        _sub_text(wpt, "name", name)
    if description:
        _sub_text(wpt, "desc", description)


def _add_trk(
    gpx_root: ET.Element,
    coords: list[tuple[float, float, float | None]],
    name: str,
) -> None:
    """Append a <trk> element containing one <trkseg> to gpx_root.

    Args:
        gpx_root (ET.Element): The GPX root element.
        coords (list[tuple[float, float, float | None]]): The ordered
            coordinate tuples for the track.
        name (str): The track name; used as the ``<name>`` child element
            (even when empty, to keep the element consistent).
    """
    trk = ET.SubElement(gpx_root, f"{{{_GPX_NS}}}trk")
    _sub_text(trk, "name", name)
    trkseg = ET.SubElement(trk, f"{{{_GPX_NS}}}trkseg")
    for lon, lat, alt in coords:
        trkpt = ET.SubElement(
            trkseg, f"{{{_GPX_NS}}}trkpt", attrib={"lat": str(lat), "lon": str(lon)}
        )
        if alt is not None:
            _sub_text(trkpt, "ele", str(alt))


def _sub_text(parent: ET.Element, local: str, text: str) -> ET.Element:
    """Append a child element with a text node to parent.

    Args:
        parent (ET.Element): The parent element.
        local (str): The local tag name (placed in the GPX namespace).
        text (str): The text content.

    Returns:
        ET.Element: The newly created child element.
    """
    child = ET.SubElement(parent, f"{{{_GPX_NS}}}{local}")
    child.text = text
    return child
