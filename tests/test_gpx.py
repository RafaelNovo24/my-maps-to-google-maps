"""Tests for gpx.py — KML-to-GPX conversion."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from gpx import GpxResult, gpx_filename, kml_to_gpx

_GPX_NS = "http://www.topografix.com/GPX/1/1"
_KML_NS = "http://www.opengis.net/kml/2.2"


def _gpx(result: GpxResult) -> ET.Element:
    """Parse the GPX bytes from a GpxResult into an ElementTree root."""
    return ET.fromstring(result.data)


def _findall(root: ET.Element, local: str) -> list[ET.Element]:
    """Find all elements with the given local name in the GPX namespace."""
    return root.findall(f".//{{{_GPX_NS}}}{local}")


# ---------------------------------------------------------------------------
# KML fixtures
# ---------------------------------------------------------------------------

_KML_POINT = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{_KML_NS}">
  <Document>
    <Placemark>
      <name>My Pin</name>
      <Point><coordinates>10.0,20.0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""

_KML_POINT_WITH_ALT = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{_KML_NS}">
  <Document>
    <Placemark>
      <name>High Point</name>
      <Point><coordinates>10.0,20.0,350.5</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""

_KML_POINT_NO_ALT = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{_KML_NS}">
  <Document>
    <Placemark>
      <name>Low Point</name>
      <Point><coordinates>10.0,20.0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""

_KML_LINESTRING = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{_KML_NS}">
  <Document>
    <Placemark>
      <name>My Track</name>
      <LineString>
        <coordinates>1.0,2.0,0 3.0,4.0,0 5.0,6.0,0</coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""

_KML_MIXED = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{_KML_NS}">
  <Document>
    <Placemark>
      <name>Pin A</name>
      <Point><coordinates>10.0,20.0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Pin B</name>
      <Point><coordinates>11.0,21.0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Route 1</name>
      <LineString>
        <coordinates>1.0,2.0 3.0,4.0</coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""

_KML_TWO_FOLDERS = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{_KML_NS}">
  <Document>
    <Folder>
      <name>Folder Alpha</name>
      <Placemark>
        <name>Track A</name>
        <LineString>
          <coordinates>1.0,2.0 3.0,4.0</coordinates>
        </LineString>
      </Placemark>
    </Folder>
    <Folder>
      <name>Folder Beta</name>
      <Placemark>
        <LineString>
          <coordinates>5.0,6.0 7.0,8.0</coordinates>
        </LineString>
      </Placemark>
    </Folder>
  </Document>
</kml>
"""

_KML_POLYGON = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{_KML_NS}">
  <Document>
    <Placemark>
      <name>A Shape</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>0,0 1,0 1,1 0,1 0,0</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""

_KML_PINS_ONLY = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{_KML_NS}">
  <Document>
    <Placemark>
      <name>Stop A</name>
      <Point><coordinates>1.0,2.0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Stop B</name>
      <Point><coordinates>3.0,4.0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""

_KML_EMPTY = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{_KML_NS}">
  <Document>
    <name>Empty Map</name>
  </Document>
</kml>
"""

_KML_POINT_WITH_DESC = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{_KML_NS}">
  <Document>
    <Placemark>
      <name>Named Pin</name>
      <description>A lovely spot.</description>
      <Point><coordinates>10.0,20.0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""

# ---------------------------------------------------------------------------
# 1. Coordinate swap — Point
# ---------------------------------------------------------------------------


def test_point_coord_swap_lat():
    """wpt lat must be the KML 2nd value (20.0), not the 1st (10.0 = lon)."""
    root = _gpx(kml_to_gpx(_KML_POINT))
    wpts = _findall(root, "wpt")
    assert len(wpts) == 1
    assert wpts[0].get("lat") == "20.0"


def test_point_coord_swap_lon():
    """wpt lon must be the KML 1st value (10.0 = lon)."""
    root = _gpx(kml_to_gpx(_KML_POINT))
    wpts = _findall(root, "wpt")
    assert wpts[0].get("lon") == "10.0"


# ---------------------------------------------------------------------------
# 2. LineString → trk/trkseg/trkpt with correct count and coord swap
# ---------------------------------------------------------------------------


def test_linestring_produces_one_trk():
    """A single LineString placemark yields exactly one trk and tracks == 1."""
    result = kml_to_gpx(_KML_LINESTRING)
    root = _gpx(result)
    assert len(_findall(root, "trk")) == 1
    assert result.tracks == 1


def test_linestring_produces_one_trkseg():
    """A single LineString placemark yields exactly one trkseg."""
    root = _gpx(kml_to_gpx(_KML_LINESTRING))
    assert len(_findall(root, "trkseg")) == 1


def test_linestring_trkpt_count():
    """A three-coordinate LineString yields three trkpt elements."""
    root = _gpx(kml_to_gpx(_KML_LINESTRING))
    assert len(_findall(root, "trkpt")) == 3


def test_linestring_trkpt_coord_swap():
    """trkpt lat/lon must be swapped from KML lon,lat."""
    root = _gpx(kml_to_gpx(_KML_LINESTRING))
    trkpts = _findall(root, "trkpt")
    # First coord in KML is "1.0,2.0,0" → lon=1.0, lat=2.0
    assert trkpts[0].get("lat") == "2.0"
    assert trkpts[0].get("lon") == "1.0"


# ---------------------------------------------------------------------------
# 3. Mixed KML — both wpt and trk present; counts correct
# ---------------------------------------------------------------------------


def test_mixed_kml_wpt_count():
    """Mixed KML with two points reports waypoints == 2."""
    result = kml_to_gpx(_KML_MIXED)
    assert result.waypoints == 2


def test_mixed_kml_trk_count():
    """Mixed KML with one LineString reports tracks == 1."""
    result = kml_to_gpx(_KML_MIXED)
    assert result.tracks == 1


def test_mixed_kml_has_both_wpt_and_trk():
    """Mixed KML emits both two wpt elements and one trk element."""
    root = _gpx(kml_to_gpx(_KML_MIXED))
    assert len(_findall(root, "wpt")) == 2
    assert len(_findall(root, "trk")) == 1


# ---------------------------------------------------------------------------
# 4. Two folders each with a linestring → two trk; track names from placemark/folder
# ---------------------------------------------------------------------------


def test_two_folders_two_trks():
    """Two folders each with a LineString produce two trk elements."""
    result = kml_to_gpx(_KML_TWO_FOLDERS)
    assert result.tracks == 2
    assert len(_findall(_gpx(result), "trk")) == 2


def test_two_folders_trk_name_from_placemark():
    """'Track A' is the placemark name — it should appear as the trk name."""
    root = _gpx(kml_to_gpx(_KML_TWO_FOLDERS))
    trks = _findall(root, "trk")
    names = [trk.find(f"{{{_GPX_NS}}}name").text for trk in trks]
    assert "Track A" in names


def test_two_folders_trk_name_fallback_to_folder():
    """Second placemark has no name → falls back to 'Folder Beta'."""
    root = _gpx(kml_to_gpx(_KML_TWO_FOLDERS))
    trks = _findall(root, "trk")
    names = [trk.find(f"{{{_GPX_NS}}}name").text for trk in trks]
    assert "Folder Beta" in names


# ---------------------------------------------------------------------------
# 5. Polygon → skipped
# ---------------------------------------------------------------------------


def test_polygon_skipped_count():
    """A Polygon placemark increments the skipped count."""
    result = kml_to_gpx(_KML_POLYGON)
    assert result.skipped >= 1


def test_polygon_no_wpt_or_trk():
    """A Polygon placemark produces no wpt or trk elements."""
    result = kml_to_gpx(_KML_POLYGON)
    root = _gpx(result)
    assert _findall(root, "wpt") == []
    assert _findall(root, "trk") == []


# ---------------------------------------------------------------------------
# 6. Elevation: present only when altitude is in the coordinate
# ---------------------------------------------------------------------------


def test_elevation_present_when_alt_given():
    """A point with altitude emits an ele element holding that altitude."""
    root = _gpx(kml_to_gpx(_KML_POINT_WITH_ALT))
    wpts = _findall(root, "wpt")
    ele = wpts[0].find(f"{{{_GPX_NS}}}ele")
    assert ele is not None
    assert ele.text == "350.5"


def test_elevation_absent_when_no_alt():
    """A point without altitude emits no ele element."""
    root = _gpx(kml_to_gpx(_KML_POINT_NO_ALT))
    wpts = _findall(root, "wpt")
    ele = wpts[0].find(f"{{{_GPX_NS}}}ele")
    assert ele is None


def test_linestring_trkpt_elevation_present():
    """Coords with alt='0' → <ele>0.0</ele> present."""
    root = _gpx(kml_to_gpx(_KML_LINESTRING))
    trkpts = _findall(root, "trkpt")
    for trkpt in trkpts:
        ele = trkpt.find(f"{{{_GPX_NS}}}ele")
        assert ele is not None


# ---------------------------------------------------------------------------
# 7. Name and description on wpt
# ---------------------------------------------------------------------------


def test_wpt_name():
    """A named point emits a wpt name element holding that name."""
    root = _gpx(kml_to_gpx(_KML_POINT_WITH_DESC))
    wpts = _findall(root, "wpt")
    name_el = wpts[0].find(f"{{{_GPX_NS}}}name")
    assert name_el is not None
    assert name_el.text == "Named Pin"


def test_wpt_description():
    """A point with a description emits a wpt desc element holding that text."""
    root = _gpx(kml_to_gpx(_KML_POINT_WITH_DESC))
    wpts = _findall(root, "wpt")
    desc_el = wpts[0].find(f"{{{_GPX_NS}}}desc")
    assert desc_el is not None
    assert desc_el.text == "A lovely spot."


def test_wpt_no_desc_when_empty():
    """Point without a description element → no <desc> in output."""
    root = _gpx(kml_to_gpx(_KML_POINT))
    wpts = _findall(root, "wpt")
    assert wpts[0].find(f"{{{_GPX_NS}}}desc") is None


# ---------------------------------------------------------------------------
# 8. GPX 1.1 namespace, version, creator — well-formed output
# ---------------------------------------------------------------------------


def test_gpx_root_tag_namespace():
    """The GPX root element is 'gpx' in the GPX 1.1 namespace."""
    result = kml_to_gpx(_KML_POINT)
    root = ET.fromstring(result.data)
    assert root.tag == f"{{{_GPX_NS}}}gpx"


def test_gpx_version():
    """The GPX root carries version '1.1'."""
    result = kml_to_gpx(_KML_POINT)
    root = ET.fromstring(result.data)
    assert root.get("version") == "1.1"


def test_gpx_creator_default():
    """The GPX root defaults its creator attribute to 'Travel Assistant'."""
    result = kml_to_gpx(_KML_POINT)
    root = ET.fromstring(result.data)
    assert root.get("creator") == "Travel Assistant"


def test_gpx_creator_custom():
    """A custom creator argument is written to the GPX root creator attribute."""
    result = kml_to_gpx(_KML_POINT, creator="MyApp")
    root = ET.fromstring(result.data)
    assert root.get("creator") == "MyApp"


def test_gpx_output_is_bytes():
    """The serialized GPX document is returned as bytes."""
    result = kml_to_gpx(_KML_POINT)
    assert isinstance(result.data, bytes)


def test_gpx_output_has_xml_declaration():
    """The serialized GPX document begins with an XML declaration."""
    result = kml_to_gpx(_KML_POINT)
    assert result.data.startswith(b"<?xml")


# ---------------------------------------------------------------------------
# 9. Pins-only KML → only wpt, zero trk, has_features True
# ---------------------------------------------------------------------------


def test_pins_only_no_trk():
    """A pins-only KML produces zero tracks."""
    result = kml_to_gpx(_KML_PINS_ONLY)
    assert result.tracks == 0


def test_pins_only_has_wpts():
    """A pins-only KML with two points reports waypoints == 2."""
    result = kml_to_gpx(_KML_PINS_ONLY)
    assert result.waypoints == 2


def test_pins_only_has_features_true():
    """A pins-only KML reports has_features as True."""
    result = kml_to_gpx(_KML_PINS_ONLY)
    assert result.has_features is True


# ---------------------------------------------------------------------------
# 10. Empty/zero-geometry KML → has_features False
# ---------------------------------------------------------------------------


def test_empty_kml_has_features_false():
    """A geometry-free KML reports has_features as False."""
    result = kml_to_gpx(_KML_EMPTY)
    assert result.has_features is False


def test_empty_kml_zero_waypoints():
    """A geometry-free KML reports zero waypoints."""
    result = kml_to_gpx(_KML_EMPTY)
    assert result.waypoints == 0


def test_empty_kml_zero_tracks():
    """A geometry-free KML reports zero tracks."""
    result = kml_to_gpx(_KML_EMPTY)
    assert result.tracks == 0


# ---------------------------------------------------------------------------
# 11. Invalid/garbage KML → raises
# ---------------------------------------------------------------------------


def test_garbage_kml_raises():
    """Non-XML input raises an exception."""
    with pytest.raises(Exception):
        kml_to_gpx("this is not xml at all <<<")


def test_empty_string_raises():
    """An empty input string raises an exception."""
    with pytest.raises(Exception):
        kml_to_gpx("")


# ---------------------------------------------------------------------------
# 12. gpx_filename
# ---------------------------------------------------------------------------


def test_gpx_filename_kml():
    """A .kml filename becomes the same stem with a .gpx extension."""
    assert gpx_filename("Trip.kml") == "Trip.gpx"


def test_gpx_filename_kml_uppercase():
    """An uppercase .KML extension is matched case-insensitively."""
    assert gpx_filename("a.KML") == "a.gpx"


def test_gpx_filename_kmz():
    """A .kmz filename becomes the same stem with a .gpx extension."""
    assert gpx_filename("x.kmz") == "x.gpx"


def test_gpx_filename_empty_string():
    """An empty filename falls back to 'travel.gpx'."""
    assert gpx_filename("") == "travel.gpx"


def test_gpx_filename_none_like():
    """A falsy (None) filename falls back to 'travel.gpx'."""
    assert gpx_filename(None) == "travel.gpx"


def test_gpx_filename_no_extension():
    """A filename with no extension simply gains a .gpx suffix."""
    assert gpx_filename("myfile") == "myfile.gpx"
