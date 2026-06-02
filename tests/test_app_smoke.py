from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_loads():
    at = AppTest.from_file(APP).run()
    assert not at.exception
    assert "My Maps" in at.title[0].value


def test_bad_link_is_handled():
    at = AppTest.from_file(APP).run()
    at.radio[0].set_value("My Maps link").run()
    at.text_input[0].set_value("http://example.com/no-mid").run()
    assert not at.exception
    assert len(at.error) >= 1


def test_render_path_renders_layers(monkeypatch):
    import streamlit as st
    import converter
    placemarks = "".join(
        f'<Placemark><name>P{i}</name>'
        f'<Point><coordinates>{i}.0,{i}.0,0</coordinates></Point></Placemark>'
        for i in range(12)
    )
    sample_kml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Map</name>'
        f'<Folder><name>Trip</name>{placemarks}</Folder>'
        '</Document></kml>'
    )
    # bypass the network entirely
    monkeypatch.setattr(converter, "kml_from_mymaps_url", lambda url, **kw: sample_kml)
    st.cache_data.clear()  # avoid a stale cached result from another test

    at = AppTest.from_file(APP).run()
    at.radio[0].set_value("My Maps link").run()
    at.text_input[0].set_value("https://www.google.com/maps/d/edit?mid=RENDERTEST").run(timeout=10)

    assert not at.exception                       # proves every render call ran (link_button/map/download_button)
    assert any("Trip" in s.value for s in at.subheader)   # the per-layer block was reached
