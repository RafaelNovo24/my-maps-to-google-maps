from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_loads():
    at = AppTest.from_file(APP).run()
    assert not at.exception
    assert "My Maps" in at.title[0].value


def test_language_switch_no_crash():
    at = AppTest.from_file(APP).run()
    at.button(key="lang_en").click().run()
    assert not at.exception
