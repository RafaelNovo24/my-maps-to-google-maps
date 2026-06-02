from __future__ import annotations

import io
import zipfile
from urllib.parse import unquote

import pytest

from converter import (
    Layer,
    Point,
    _ensure_kml,
    build_route_links,
    kml_from_upload,
    mymaps_export_url,
    parse_layers,
)

# ---------------------------------------------------------------------------
# KML fixtures
# ---------------------------------------------------------------------------

KML_TWO_FOLDERS = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Test Map</name>
    <Folder>
      <name>Alpha</name>
      <Placemark>
        <name>P1</name>
        <Point><coordinates>10.0,20.0,0</coordinates></Point>
      </Placemark>
      <Placemark>
        <name>P2</name>
        <Point><coordinates>11.0,21.0,0</coordinates></Point>
      </Placemark>
    </Folder>
    <Folder>
      <name>Beta</name>
      <Placemark>
        <name>P3</name>
        <Point><coordinates>12.0,22.0,0</coordinates></Point>
      </Placemark>
    </Folder>
  </Document>
</kml>
"""

KML_NO_FOLDER = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Flat Map</name>
    <Placemark>
      <name>A</name>
      <Point><coordinates>1.0,2.0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>B</name>
      <Point><coordinates>3.0,4.0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""

KML_WITH_LINESTRING = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Mixed</name>
    <Placemark>
      <name>Route</name>
      <LineString>
        <coordinates>1.0,2.0 3.0,4.0</coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Stop</name>
      <Point><coordinates>5.0,6.0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""

# ---------------------------------------------------------------------------
# parse_layers
# ---------------------------------------------------------------------------


def test_parse_layers_two_folders_count():
    layers = parse_layers(KML_TWO_FOLDERS)
    assert len(layers) == 2


def test_parse_layers_two_folders_names():
    layers = parse_layers(KML_TWO_FOLDERS)
    assert layers[0].name == "Alpha"
    assert layers[1].name == "Beta"


def test_parse_layers_two_folders_point_counts():
    layers = parse_layers(KML_TWO_FOLDERS)
    assert len(layers[0].points) == 2
    assert len(layers[1].points) == 1


def test_parse_layers_two_folders_coordinates():
    layers = parse_layers(KML_TWO_FOLDERS)
    p1 = layers[0].points[0]
    # coordinates string is "lng,lat" → 10.0 is lng, 20.0 is lat
    assert p1.lat == pytest.approx(20.0)
    assert p1.lng == pytest.approx(10.0)


def test_parse_layers_no_folder_single_layer():
    layers = parse_layers(KML_NO_FOLDER)
    assert len(layers) == 1


def test_parse_layers_no_folder_name():
    layers = parse_layers(KML_NO_FOLDER)
    assert layers[0].name == "Flat Map"


def test_parse_layers_no_folder_point_count():
    layers = parse_layers(KML_NO_FOLDER)
    assert len(layers[0].points) == 2


def test_parse_layers_linestring_skipped():
    layers = parse_layers(KML_WITH_LINESTRING)
    assert len(layers) == 1
    # Only "Stop" has a Point; "Route" is a LineString and must be skipped
    assert len(layers[0].points) == 1
    assert layers[0].points[0].name == "Stop"


# ---------------------------------------------------------------------------
# mymaps_export_url
# ---------------------------------------------------------------------------

EXPECTED_PREFIX = "https://www.google.com/maps/d/kml?mid="
EXPECTED_SUFFIX = "&forcekml=1"
SAMPLE_MID = "1bXyZ_abcDEF123"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.google.com/maps/d/edit?mid={SAMPLE_MID}",
        f"https://www.google.com/maps/d/viewer?mid={SAMPLE_MID}",
        f"https://www.google.com/maps/d/u/0/edit?mid={SAMPLE_MID}",
        f"www.google.com/maps/d/edit?mid={SAMPLE_MID}",
    ],
)
def test_mymaps_export_url_valid(url: str):
    result = mymaps_export_url(url)
    assert result == f"{EXPECTED_PREFIX}{SAMPLE_MID}{EXPECTED_SUFFIX}"


def test_mymaps_export_url_no_mid_raises():
    with pytest.raises(ValueError):
        mymaps_export_url("https://www.google.com/maps/d/edit?foo=bar")


def test_mymaps_export_url_no_params_raises():
    with pytest.raises(ValueError):
        mymaps_export_url("https://www.google.com/maps/d/edit")


# ---------------------------------------------------------------------------
# build_route_links
# ---------------------------------------------------------------------------


def _pts(n: int) -> list[Point]:
    return [Point(name=f"P{i}", lat=float(i), lng=float(i) * 0.1) for i in range(n)]


def test_build_route_links_empty():
    assert build_route_links([]) == []


def test_build_route_links_one_point_empty():
    assert build_route_links([Point("X", 10.0, 20.0)]) == []


def test_build_route_links_two_points_one_link():
    links = build_route_links(_pts(2))
    assert len(links) == 1


def test_build_route_links_two_points_has_waypoint():
    pts = _pts(2)
    links = build_route_links(pts)
    # with no origin, pt0 becomes the sole waypoint and pt1 is the destination
    assert "waypoints=" in links[0]
    assert f"{pts[0].lat}%2C{pts[0].lng}" in links[0]


def test_build_route_links_two_points_no_origin():
    pts = _pts(2)
    links = build_route_links(pts)
    assert "origin=" not in links[0]
    assert f"destination={pts[1].lat}%2C{pts[1].lng}" in links[0]


def test_build_route_links_five_points_one_link():
    links = build_route_links(_pts(5))
    assert len(links) == 1


def test_build_route_links_five_points_four_waypoints():
    pts = _pts(5)
    links = build_route_links(pts)
    # waypoints are pts[0..3] (all but the destination pts[4]) — 4 points
    waypoints_part = [p for p in links[0].split("&") if p.startswith("waypoints=")]
    assert len(waypoints_part) == 1
    wps = waypoints_part[0][len("waypoints="):].split("%7C")
    assert len(wps) == 4


def test_build_route_links_nine_points_one_link():
    assert len(build_route_links(_pts(9))) == 1


def test_build_route_links_ten_points_two_links():
    links = build_route_links(_pts(10))
    assert len(links) == 2


def test_build_route_links_ten_points_two_links_overlap():
    pts = _pts(10)
    links = build_route_links(pts)
    assert len(links) == 2
    # destination of leg 1 == first waypoint of leg 2  (the overlap point)
    leg1_dest_part = [p for p in links[0].split("&") if p.startswith("destination=")]
    assert len(leg1_dest_part) == 1
    leg1_dest = unquote(leg1_dest_part[0][len("destination="):])
    leg2_wps_part = [p for p in links[1].split("&") if p.startswith("waypoints=")]
    assert len(leg2_wps_part) == 1
    leg2_first_wp = unquote(leg2_wps_part[0][len("waypoints="):].split("%7C")[0])
    assert leg1_dest == leg2_first_wp


def test_build_route_links_ten_points_order_preserved():
    pts = _pts(10)
    links = build_route_links(pts)
    # no origin= anywhere
    assert "origin=" not in links[0]
    assert "origin=" not in links[1]
    # leg 1's first waypoint is pts[0]; leg 2's destination is pts[9]
    leg1_wps_part = [p for p in links[0].split("&") if p.startswith("waypoints=")]
    first_wp = unquote(leg1_wps_part[0][len("waypoints="):].split("%7C")[0])
    assert first_wp == f"{pts[0].lat},{pts[0].lng}"
    assert f"destination={pts[9].lat}%2C{pts[9].lng}" in links[1]


def test_build_route_links_twelve_points_two_links():
    links = build_route_links(_pts(12), max_stops=10, overlap=1)
    assert len(links) == 2


def test_build_route_links_no_origin_in_any_link():
    for n in (2, 5, 9):
        for link in build_route_links(_pts(n)):
            assert "origin=" not in link


def test_build_route_links_destination_present():
    for n in (2, 5, 9):
        for link in build_route_links(_pts(n)):
            assert "destination=" in link


def test_build_route_links_waypoints_separator():
    # ≥3-point leg → waypoints joined by %7C
    links = build_route_links(_pts(3))
    assert "waypoints=" in links[0]
    wps_part = [p for p in links[0].split("&") if p.startswith("waypoints=")][0]
    assert "%7C" in wps_part


def test_build_route_links_travelmode_default():
    links = build_route_links(_pts(2))
    assert "travelmode=driving" in links[0]


def test_build_route_links_travelmode_custom():
    links = build_route_links(_pts(2), travel_mode="walking")
    assert "travelmode=walking" in links[0]


# ---------------------------------------------------------------------------
# kml_from_upload
# ---------------------------------------------------------------------------


def test_kml_from_upload_plain_kml():
    kml = "<kml><Document/></kml>"
    result = kml_from_upload("map.kml", kml.encode("utf-8"))
    assert result == kml


def test_kml_from_upload_kmz_with_doc_kml():
    inner_kml = "<kml><Document><name>KMZ Test</name></Document></kml>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", inner_kml)
        zf.writestr("images/icon.png", b"fake")
    result = kml_from_upload("export.kmz", buf.getvalue())
    assert result == inner_kml


def test_kml_from_upload_kmz_first_kml_fallback():
    inner_kml = "<kml><Document><name>Fallback</name></Document></kml>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data/map.kml", inner_kml)
    result = kml_from_upload("export.kmz", buf.getvalue())
    assert result == inner_kml


def test_kml_from_upload_empty_raises():
    with pytest.raises(ValueError):
        kml_from_upload("map.kml", b"")


def test_kml_from_upload_kmz_no_kml_raises():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "nothing here")
    with pytest.raises(ValueError):
        kml_from_upload("export.kmz", buf.getvalue())


# ---------------------------------------------------------------------------
# _ensure_kml
# ---------------------------------------------------------------------------


def test_ensure_kml_xml_declaration_passes():
    text = '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"></kml>'
    assert _ensure_kml(text) == text


def test_ensure_kml_kml_tag_without_declaration_passes():
    text = '<kml xmlns="http://www.opengis.net/kml/2.2"><Document/></kml>'
    assert _ensure_kml(text) == text


def test_ensure_kml_html_error_page_raises():
    html = "<!DOCTYPE html><html><body>This map is private.</body></html>"
    with pytest.raises(ValueError, match="publicly shared"):
        _ensure_kml(html)


def test_ensure_kml_empty_string_raises():
    with pytest.raises(ValueError):
        _ensure_kml("")


def test_ensure_kml_leading_whitespace_handled():
    text = "   \n<?xml version='1.0'?><kml></kml>"
    assert _ensure_kml(text) == text


# ---------------------------------------------------------------------------
# _reject_networklink_stub (via kml_from_upload)
# ---------------------------------------------------------------------------

_KML_NETWORKLINK_STUB = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
  <name>Roteiro</name>
  <NetworkLink><name>link</name>
    <Link><href>https://www.google.com/maps/d/kml?mid=TESTMID</href></Link>
  </NetworkLink>
</Document></kml>
"""

_KML_NETWORKLINK_WITH_PLACEMARK = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
  <name>Mixed</name>
  <NetworkLink><name>link</name>
    <Link><href>https://www.google.com/maps/d/kml?mid=TESTMID</href></Link>
  </NetworkLink>
  <Placemark>
    <name>Stop</name>
    <Point><coordinates>-8.0,42.0,0</coordinates></Point>
  </Placemark>
</Document></kml>
"""


def test_kml_from_upload_networklink_stub_raises():
    with pytest.raises(ValueError) as exc_info:
        kml_from_upload("doc.kml", _KML_NETWORKLINK_STUB.encode("utf-8"))
    msg = str(exc_info.value)
    assert "export" in msg
    assert "KML" in msg


def test_kml_from_upload_networklink_stub_kmz_raises():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", _KML_NETWORKLINK_STUB)
    with pytest.raises(ValueError) as exc_info:
        kml_from_upload("export.kmz", buf.getvalue())
    msg = str(exc_info.value)
    assert "export" in msg
    assert "KML" in msg


def test_kml_from_upload_networklink_with_placemark_ok():
    result = kml_from_upload("doc.kml", _KML_NETWORKLINK_WITH_PLACEMARK.encode("utf-8"))
    assert "NetworkLink" in result


# ---------------------------------------------------------------------------
# has_route detection
# ---------------------------------------------------------------------------

_KML_FOLDER_WITH_LINESTRING = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Folder>
      <name>Route Layer</name>
      <Placemark>
        <name>Segment</name>
        <LineString><coordinates>1.0,2.0 3.0,4.0</coordinates></LineString>
      </Placemark>
      <Placemark>
        <name>Stop</name>
        <Point><coordinates>5.0,6.0,0</coordinates></Point>
      </Placemark>
    </Folder>
  </Document>
</kml>
"""

_KML_FOLDER_POINTS_ONLY = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Folder>
      <name>Points Only</name>
      <Placemark>
        <name>A</name>
        <Point><coordinates>1.0,2.0,0</coordinates></Point>
      </Placemark>
      <Placemark>
        <name>B</name>
        <Point><coordinates>3.0,4.0,0</coordinates></Point>
      </Placemark>
    </Folder>
  </Document>
</kml>
"""

_KML_MULTI_FOLDER_MIXED = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Folder>
      <name>With Route</name>
      <Placemark>
        <name>Segment</name>
        <LineString><coordinates>1.0,2.0 3.0,4.0</coordinates></LineString>
      </Placemark>
    </Folder>
    <Folder>
      <name>No Route</name>
      <Placemark>
        <name>Stop</name>
        <Point><coordinates>5.0,6.0,0</coordinates></Point>
      </Placemark>
    </Folder>
  </Document>
</kml>
"""

_KML_NO_FOLDER_WITH_LINESTRING = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Flat With Route</name>
    <Placemark>
      <name>Segment</name>
      <LineString><coordinates>1.0,2.0 3.0,4.0</coordinates></LineString>
    </Placemark>
    <Placemark>
      <name>Stop</name>
      <Point><coordinates>5.0,6.0,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""

_KML_NO_FOLDER_POINTS_ONLY = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Flat Points Only</name>
    <Placemark>
      <name>A</name>
      <Point><coordinates>1.0,2.0,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""


def test_has_route_folder_with_linestring():
    layers = parse_layers(_KML_FOLDER_WITH_LINESTRING)
    assert layers[0].has_route is True


def test_has_route_folder_points_only():
    layers = parse_layers(_KML_FOLDER_POINTS_ONLY)
    assert layers[0].has_route is False


def test_has_route_multi_folder_correct_per_layer():
    layers = parse_layers(_KML_MULTI_FOLDER_MIXED)
    assert layers[0].has_route is True
    assert layers[1].has_route is False


def test_has_route_no_folder_with_linestring():
    layers = parse_layers(_KML_NO_FOLDER_WITH_LINESTRING)
    assert layers[0].has_route is True


def test_has_route_no_folder_points_only():
    layers = parse_layers(_KML_NO_FOLDER_POINTS_ONLY)
    assert layers[0].has_route is False
