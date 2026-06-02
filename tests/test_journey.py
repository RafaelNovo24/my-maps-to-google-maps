from __future__ import annotations

import pytest

from converter import Layer
from directions import RouteEstimate
from journey import (
    format_total_distance,
    format_total_time,
    route_stretches,
    summary_table_markdown,
    total_distance_m,
    total_duration_range_s,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _est(available: bool, distance_m: int = 0, low_s: float = 0, high_s: float = 0) -> RouteEstimate:
    if not available:
        return RouteEstimate(available=False)
    return RouteEstimate(
        available=True,
        distance_m=distance_m,
        distance_text="",
        duration_low_s=low_s,
        duration_high_s=high_s,
        duration_text="",
    )


def _row(num: int, name: str, anchor: str, distance_text: str = "10 km",
         time_text: str = "30m", maps_md: str = "[Open](#)") -> dict:
    return {
        "num": num,
        "name": name,
        "anchor": anchor,
        "distance_text": distance_text,
        "time_text": time_text,
        "maps_md": maps_md,
    }


# ---------------------------------------------------------------------------
# route_stretches
# ---------------------------------------------------------------------------


def test_route_stretches_keeps_has_route_true():
    layers = [Layer(name="Route", has_route=True), Layer(name="Pins", has_route=False)]
    result = route_stretches(layers)
    assert len(result) == 1
    assert result[0].name == "Route"


def test_route_stretches_empty_list():
    assert route_stretches([]) == []


def test_route_stretches_all_with_route():
    layers = [Layer(name=f"L{i}", has_route=True) for i in range(3)]
    assert len(route_stretches(layers)) == 3


def test_route_stretches_none_with_route():
    layers = [Layer(name="Pins", has_route=False)]
    assert route_stretches(layers) == []


def test_route_stretches_mixed_order_preserved():
    layers = [
        Layer(name="A", has_route=False),
        Layer(name="B", has_route=True),
        Layer(name="C", has_route=False),
        Layer(name="D", has_route=True),
    ]
    result = route_stretches(layers)
    assert [r.name for r in result] == ["B", "D"]


# ---------------------------------------------------------------------------
# total_distance_m
# ---------------------------------------------------------------------------


def test_total_distance_m_sums_available():
    estimates = [_est(True, distance_m=10000), _est(True, distance_m=5000)]
    assert total_distance_m(estimates) == 15000


def test_total_distance_m_ignores_unavailable():
    estimates = [_est(True, distance_m=10000), _est(False)]
    assert total_distance_m(estimates) == 10000


def test_total_distance_m_all_unavailable_returns_none():
    estimates = [_est(False), _est(False)]
    assert total_distance_m(estimates) is None


def test_total_distance_m_empty_returns_none():
    assert total_distance_m([]) is None


def test_total_distance_m_single_available():
    assert total_distance_m([_est(True, distance_m=42000)]) == 42000


# ---------------------------------------------------------------------------
# total_duration_range_s
# ---------------------------------------------------------------------------


def test_total_duration_range_s_sums_available():
    estimates = [
        _est(True, low_s=1800, high_s=2400),
        _est(True, low_s=900, high_s=1200),
    ]
    result = total_duration_range_s(estimates)
    assert result == pytest.approx((2700.0, 3600.0))


def test_total_duration_range_s_ignores_unavailable():
    estimates = [_est(True, low_s=1800, high_s=2400), _est(False)]
    result = total_duration_range_s(estimates)
    assert result == pytest.approx((1800.0, 2400.0))


def test_total_duration_range_s_all_unavailable_returns_none():
    assert total_duration_range_s([_est(False), _est(False)]) is None


def test_total_duration_range_s_empty_returns_none():
    assert total_duration_range_s([]) is None


def test_total_duration_range_s_equal_low_high_for_single():
    estimates = [_est(True, low_s=3600, high_s=3600)]
    result = total_duration_range_s(estimates)
    assert result is not None
    low, high = result
    assert low == pytest.approx(high)


# ---------------------------------------------------------------------------
# summary_table_markdown
# ---------------------------------------------------------------------------


def test_summary_table_markdown_contains_pt_headers():
    table = summary_table_markdown([_row(1, "A", "stretch-1")], lang="pt")
    assert "Descrição" in table
    assert "Distância" in table
    assert "Tempo est." in table
    assert "Google Maps" in table


def test_summary_table_markdown_contains_en_headers():
    table = summary_table_markdown([_row(1, "A", "stretch-1")], lang="en")
    assert "Description" in table
    assert "Distance" in table
    assert "Est. time" in table
    assert "Google Maps" in table


def test_summary_table_markdown_anchor_link():
    table = summary_table_markdown([_row(1, "Alpha", "stretch-1")], lang="en")
    assert "[Alpha](#stretch-1)" in table


def test_summary_table_markdown_multiple_rows():
    rows = [_row(i, f"Stretch {i}", f"stretch-{i}") for i in range(1, 4)]
    table = summary_table_markdown(rows, lang="en")
    for i in range(1, 4):
        assert f"[Stretch {i}](#stretch-{i})" in table


def test_summary_table_markdown_distance_cell():
    table = summary_table_markdown([_row(1, "A", "stretch-1", distance_text="123.4 km")], lang="en")
    assert "123.4 km" in table


def test_summary_table_markdown_time_cell():
    table = summary_table_markdown([_row(1, "A", "stretch-1", time_text="1h 30m")], lang="en")
    assert "1h 30m" in table


def test_summary_table_markdown_maps_cell():
    table = summary_table_markdown([_row(1, "A", "stretch-1", maps_md="[Open](https://maps.google.com)")], lang="en")
    assert "[Open](https://maps.google.com)" in table


def test_summary_table_markdown_has_separator_row():
    table = summary_table_markdown([_row(1, "A", "stretch-1")], lang="en")
    assert "|---|" in table


def test_summary_table_markdown_empty_rows():
    table = summary_table_markdown([], lang="en")
    lines = [l for l in table.splitlines() if l.strip()]
    assert len(lines) == 2  # header + separator only


# ---------------------------------------------------------------------------
# format_total_distance
# ---------------------------------------------------------------------------


def test_format_total_distance_none_returns_unavailable_pt():
    result = format_total_distance(None, "pt")
    assert result == "indisponível"


def test_format_total_distance_none_returns_unavailable_en():
    result = format_total_distance(None, "en")
    assert result == "unavailable"


def test_format_total_distance_formats_km():
    result = format_total_distance(50000, "en")
    assert "50 km" == result


def test_format_total_distance_formats_m():
    result = format_total_distance(500, "en")
    assert "500 m" == result


# ---------------------------------------------------------------------------
# format_total_time
# ---------------------------------------------------------------------------


def test_format_total_time_none_returns_unavailable_pt():
    result = format_total_time(None, "pt")
    assert result == "indisponível"


def test_format_total_time_none_returns_unavailable_en():
    result = format_total_time(None, "en")
    assert result == "unavailable"


def test_format_total_time_same_low_high_no_range_marker():
    result = format_total_time((3600.0, 3600.0), "en")
    assert " – " not in result
    assert "1h" in result


def test_format_total_time_different_low_high_has_range_marker():
    result = format_total_time((3600.0, 5400.0), "en")
    assert " – " in result


def test_format_total_time_minutes_only():
    result = format_total_time((1800.0, 1800.0), "en")
    assert "30m" in result
    assert "h" not in result


# ---------------------------------------------------------------------------
# No streamlit import
# ---------------------------------------------------------------------------


def test_journey_does_not_import_streamlit():
    import importlib
    import sys

    for mod_name in list(sys.modules):
        if mod_name == "journey" or mod_name.startswith("journey."):
            del sys.modules[mod_name]

    streamlit_before = set(k for k in sys.modules if k == "streamlit" or k.startswith("streamlit."))
    importlib.import_module("journey")
    streamlit_after = set(k for k in sys.modules if k == "streamlit" or k.startswith("streamlit."))
    newly_imported = streamlit_after - streamlit_before
    assert not newly_imported, f"journey imported streamlit: {newly_imported}"
