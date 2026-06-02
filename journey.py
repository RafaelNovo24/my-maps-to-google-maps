"""Aggregate and present per-stretch route estimates for a whole journey.

Builds on :mod:`directions` and :mod:`i18n` to total distances and durations
across the stretches of a journey and render a localized Markdown summary table.
"""
from __future__ import annotations

from directions import RouteEstimate, format_distance, format_range
from i18n import t


def route_stretches(layers: list) -> list:
    """Select the layers that represent routable stretches.

    Args:
        layers (list): The parsed layers to filter.

    Returns:
        list: The layers whose ``has_route`` flag is set.
    """
    return [layer for layer in layers if layer.has_route]


def total_distance_m(estimates: list[RouteEstimate]) -> int | None:
    """Sum the distances of the available estimates.

    Args:
        estimates (list[RouteEstimate]): The per-stretch estimates to total.

    Returns:
        int | None: The combined distance in meters, or None when no estimate
            carries a distance.
    """
    available = [e.distance_m for e in estimates if e.available and e.distance_m is not None]
    if not available:
        return None
    return sum(available)


def total_duration_range_s(
    estimates: list[RouteEstimate],
) -> tuple[float, float] | None:
    """Sum the duration bounds of the available estimates.

    Args:
        estimates (list[RouteEstimate]): The per-stretch estimates to total.

    Returns:
        tuple[float, float] | None: The combined (low, high) duration in
            seconds, or None when no estimate is available.
    """
    available = [e for e in estimates if e.available]
    if not available:
        return None
    low = sum(e.duration_low_s for e in available if e.duration_low_s is not None)
    high = sum(e.duration_high_s for e in available if e.duration_high_s is not None)
    return (low, high)


def summary_table_markdown(rows: list[dict], lang: str) -> str:
    """Render the journey summary rows as a localized Markdown table.

    Args:
        rows (list[dict]): Per-stretch rows, each with ``num``, ``name``,
            ``anchor``, ``distance_text``, ``time_text``, and ``maps_md`` keys.
        lang (str): The language code used to localize the column headers.

    Returns:
        str: The Markdown table, including its header and separator rows.
    """
    col_num = t("col_num", lang)
    col_description = t("col_description", lang)
    col_distance = t("col_distance", lang)
    col_time = t("col_time", lang)
    col_maps = t("col_maps", lang)

    header = f"| {col_num} | {col_description} | {col_distance} | {col_time} | {col_maps} |"
    separator = "|---|---|---|---|---|"

    lines = [header, separator]
    for row in rows:
        num = row["num"]
        name = row["name"]
        anchor = row["anchor"]
        distance_text = row["distance_text"]
        time_text = row["time_text"]
        maps_md = row["maps_md"]
        description_cell = f"[{name}](#{anchor})"
        lines.append(f"| {num} | {description_cell} | {distance_text} | {time_text} | {maps_md} |")

    return "\n".join(lines)


def format_total_distance(meters: int | None, lang: str) -> str:
    """Format the journey's total distance for display.

    Args:
        meters (int | None): The total distance in meters, or None when
            unavailable.
        lang (str): The language code used for the unavailable label.

    Returns:
        str: The formatted distance, or a localized "unavailable" label when
            ``meters`` is None.
    """
    if meters is None:
        return t("eta_unavailable", lang)
    return format_distance(meters)


def format_total_time(rng: tuple[float, float] | None, lang: str) -> str:
    """Format the journey's total estimated time for display.

    Args:
        rng (tuple[float, float] | None): The total (low, high) duration in
            seconds, or None when unavailable.
        lang (str): The language code used for the unavailable label.

    Returns:
        str: The formatted duration range, or a localized "unavailable" label
            when ``rng`` is None.
    """
    if rng is None:
        return t("eta_unavailable", lang)
    low_s, high_s = rng
    return format_range(low_s, high_s)
