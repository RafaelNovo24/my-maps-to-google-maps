from __future__ import annotations

import i18n
from i18n import DEFAULT_LANG, LANGUAGES, TRANSLATIONS, t


# ---------------------------------------------------------------------------
# Basic lookup
# ---------------------------------------------------------------------------


def test_title_pt():
    assert t("title", "pt") == "My Maps → Google Maps"


def test_title_en():
    assert t("title", "en") == "My Maps → Google Maps"


def test_subtitle_pt():
    result = t("subtitle", "pt")
    assert "troço" in result


def test_subtitle_en():
    result = t("subtitle", "en")
    assert "stretch by stretch" in result


def test_default_lang_is_pt():
    assert DEFAULT_LANG == "pt"


def test_languages_list():
    assert "pt" in LANGUAGES
    assert "en" in LANGUAGES


# ---------------------------------------------------------------------------
# Fallback behaviour
# ---------------------------------------------------------------------------


def test_unknown_key_falls_back_to_key_itself():
    result = t("this_key_does_not_exist_anywhere", "pt")
    assert result == "this_key_does_not_exist_anywhere"


def test_unknown_lang_falls_back_to_en():
    result = t("title", "fr")
    assert result == TRANSLATIONS["en"]["title"]


def test_unknown_lang_unknown_key_returns_key():
    result = t("totally_missing", "zz")
    assert result == "totally_missing"


# ---------------------------------------------------------------------------
# Format interpolation
# ---------------------------------------------------------------------------


def test_link_n_of_m_en():
    assert t("link_n_of_m", "en", i=1, n=2) == "link 1 of 2"


def test_link_n_of_m_pt():
    assert t("link_n_of_m", "pt", i=1, n=2) == "ligação 1 de 2"


def test_links_count_en():
    assert t("links_count", "en", n=3) == "3 links"


def test_links_count_pt():
    assert t("links_count", "pt", n=3) == "3 ligações"


# ---------------------------------------------------------------------------
# All expected keys present in both languages
# ---------------------------------------------------------------------------


_REQUIRED_KEYS = [
    "title", "subtitle", "language_label", "travel_mode_label",
    "mode_driving", "mode_walking", "mode_bicycling", "mode_two-wheeler", "mode_transit",
    "upload_label", "no_stretches_warning", "intro_caption",
    "summary_heading",
    "col_num", "col_description", "col_distance", "col_time", "col_maps",
    "open_in_maps", "links_count", "total_distance", "total_time",
    "stretch_word", "link_n_of_m", "eta_unavailable", "eta_needs_key",
]


def test_all_required_keys_in_pt():
    missing = [k for k in _REQUIRED_KEYS if k not in TRANSLATIONS["pt"]]
    assert missing == [], f"Missing PT keys: {missing}"


def test_all_required_keys_in_en():
    missing = [k for k in _REQUIRED_KEYS if k not in TRANSLATIONS["en"]]
    assert missing == [], f"Missing EN keys: {missing}"


# ---------------------------------------------------------------------------
# No streamlit import
# ---------------------------------------------------------------------------


def test_i18n_does_not_import_streamlit():
    import importlib
    import sys

    # Remove from cache and reload to get a fresh import graph.
    for mod_name in list(sys.modules):
        if mod_name == "i18n" or mod_name.startswith("i18n."):
            del sys.modules[mod_name]

    streamlit_before = set(k for k in sys.modules if k == "streamlit" or k.startswith("streamlit."))
    importlib.import_module("i18n")
    streamlit_after = set(k for k in sys.modules if k == "streamlit" or k.startswith("streamlit."))
    newly_imported = streamlit_after - streamlit_before
    assert not newly_imported, f"i18n imported streamlit: {newly_imported}"
