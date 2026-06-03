"""Smoke tests for app.py — the Streamlit interface boots and reacts to input."""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")

_KML_POINT_AND_LINE = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Smoke Test Map</name>
    <Placemark>
      <name>Pin</name>
      <Point><coordinates>10.0,20.0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Route</name>
      <LineString>
        <coordinates>1.0,2.0 3.0,4.0</coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""


def test_app_loads():
    """App runs without exception and shows the 'My Maps' title."""
    at = AppTest.from_file(APP).run()
    assert not at.exception
    assert "My Maps" in at.title[0].value


def test_language_switch_no_crash():
    """Clicking the English language button reruns the app without crashing."""
    at = AppTest.from_file(APP).run()
    at.button(key="lang_en").click().run()
    assert not at.exception


def test_gpx_section_appears_after_upload():
    """Uploading a KML file reveals a GPX section heading without error."""
    at = AppTest.from_file(APP).run()
    at.get("file_uploader")[0].upload("test.kml", _KML_POINT_AND_LINE,
                                      "application/vnd.google-earth.kml+xml").run()
    assert not at.exception
    subheader_values = [s.value for s in at.subheader]
    assert any("GPX" in v for v in subheader_values)


def test_gpx_convert_button_produces_download():
    """Clicking the GPX convert button yields a download button without error."""
    at = AppTest.from_file(APP).run()
    at.get("file_uploader")[0].upload("test.kml", _KML_POINT_AND_LINE,
                                      "application/vnd.google-earth.kml+xml").run()
    assert not at.exception
    at.button(key="gpx_convert").click().run()
    assert not at.exception
    assert len(at.get("download_button")) > 0


def test_gpx_jump_button_anchors_to_section():
    """An in-page anchor styled as a button links to #gpx in the same tab after upload."""
    at = AppTest.from_file(APP).run()
    at.get("file_uploader")[0].upload("test.kml", _KML_POINT_AND_LINE,
                                      "application/vnd.google-earth.kml+xml").run()
    assert not at.exception
    md_values = [m.value for m in at.markdown]
    assert any('href="#gpx"' in v for v in md_values)
    assert any('target="_self"' in v for v in md_values)
