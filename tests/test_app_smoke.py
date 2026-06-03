"""Smoke tests for app.py — the Streamlit interface boots and reacts to input."""
from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

import converter

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


def test_url_happy_path(monkeypatch):
    """Pasting a My Maps URL fetches KML and renders the GPX section."""
    kml_str = _KML_POINT_AND_LINE.decode("utf-8")
    monkeypatch.setattr(converter, "kml_from_mymaps_url", lambda url, *a, **k: kml_str)
    st.cache_data.clear()
    at = AppTest.from_file(APP).run()
    at.text_input(key="mymaps_url").set_value(
        "https://www.google.com/maps/d/edit?mid=HAPPYTEST"
    ).run()
    assert not at.exception
    assert len(at.error) == 0
    subheader_values = [s.value for s in at.subheader]
    assert any("GPX" in v for v in subheader_values)


def test_url_error_path(monkeypatch):
    """A ValueError from kml_from_mymaps_url shows an error and no GPX section."""
    def _raise_not_shared(url, *a, **k):
        raise ValueError("map must be publicly shared")

    monkeypatch.setattr(converter, "kml_from_mymaps_url", _raise_not_shared)
    st.cache_data.clear()
    at = AppTest.from_file(APP).run()
    at.text_input(key="mymaps_url").set_value(
        "https://www.google.com/maps/d/edit?mid=ERRORTEST"
    ).run()
    assert not at.exception
    assert len(at.error) > 0
    subheader_values = [s.value for s in at.subheader]
    assert not any("GPX" in v for v in subheader_values)


def test_source_switch_url_then_upload(monkeypatch):
    """Switching from URL source to file upload renders the flow for the file."""
    kml_str = _KML_POINT_AND_LINE.decode("utf-8")
    monkeypatch.setattr(converter, "kml_from_mymaps_url", lambda url, *a, **k: kml_str)
    st.cache_data.clear()
    at = AppTest.from_file(APP).run()
    at.text_input(key="mymaps_url").set_value(
        "https://www.google.com/maps/d/edit?mid=SWITCHTEST"
    ).run()
    assert not at.exception
    # now clear the URL and upload a file instead
    at.text_input(key="mymaps_url").set_value("").run()
    at.get("file_uploader")[0].upload(
        "switch.kml", _KML_POINT_AND_LINE, "application/vnd.google-earth.kml+xml"
    ).run()
    assert not at.exception
    subheader_values = [s.value for s in at.subheader]
    assert any("GPX" in v for v in subheader_values)
