"""Estimate route distance and travel time via the Google Routes API.

Wraps the ``directions/v2:computeRoutes`` endpoint to turn an ordered list of
coordinates into a :class:`RouteEstimate`, and provides helpers to format the
resulting distances and durations as human-readable text.
"""
from __future__ import annotations

import datetime
import os
from dataclasses import dataclass

import requests

ROUTES_ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"
API_KEY_ENV = "GOOGLE_MAPS_API_KEY"
_TRAVEL_MODES = {
    "driving": "DRIVE",
    "walking": "WALK",
    "bicycling": "BICYCLE",
    "two-wheeler": "TWO_WHEELER",
    "transit": "TRANSIT",
}


@dataclass
class RouteEstimate:
    """The outcome of a route distance and duration estimate.

    Attributes:
        available (bool): True when a distance and duration were obtained.
        distance_m (int | None): Route distance in meters, or None when
            unavailable.
        distance_text (str): The distance formatted for display.
        duration_low_s (float | None): Optimistic travel time in seconds, or
            None when unavailable.
        duration_high_s (float | None): Pessimistic travel time in seconds, or
            None when unavailable.
        duration_text (str): The duration (or duration range) formatted for
            display.
        error (str): A human-readable reason the estimate is unavailable, if any.
    """

    available: bool
    distance_m: int | None = None
    distance_text: str = ""
    duration_low_s: float | None = None
    duration_high_s: float | None = None
    duration_text: str = ""
    error: str = ""


def api_key_present() -> bool:
    """Report whether a Google Maps API key is configured.

    Returns:
        bool: True when the ``GOOGLE_MAPS_API_KEY`` environment variable is set
            to a non-empty value.
    """
    return bool(os.environ.get(API_KEY_ENV, "").strip())


def estimate_route(
    coords: list[tuple[float, float]],
    travel_mode: str = "driving",
    timeout: int = 15,
) -> RouteEstimate:
    """Estimate the distance and travel time across an ordered list of points.

    The first and last coordinates become the origin and destination; any
    points in between are sent as intermediates. Driving requests query both
    optimistic and pessimistic traffic models to produce a duration range.

    Args:
        coords (list[tuple[float, float]]): Ordered (latitude, longitude) pairs
            to route through.
        travel_mode (str, optional): One of the supported travel modes
            ("driving", "walking", "bicycling", "two-wheeler", "transit");
            unknown values fall back to driving. Defaults to "driving".
        timeout (int, optional): Per-request timeout in seconds. Defaults to 15.

    Returns:
        RouteEstimate: The estimate, or an unavailable estimate carrying an
            error message when no API key is set, fewer than two points are
            given, or the API request fails.
    """
    if not api_key_present():
        return RouteEstimate(available=False, error="No GOOGLE_MAPS_API_KEY set")
    if len(coords) < 2:
        return RouteEstimate(available=False, error="need at least 2 points")

    api_key = os.environ[API_KEY_ENV]
    api_mode = _TRAVEL_MODES.get(travel_mode, "DRIVE")

    origin = _latlng_body(coords[0])
    destination = _latlng_body(coords[-1])
    intermediates = [_latlng_body(c) for c in coords[1:-1]]

    base_body: dict = {
        "origin": origin,
        "destination": destination,
        "travelMode": api_mode,
    }
    if intermediates:
        base_body["intermediates"] = intermediates

    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration",
        "Content-Type": "application/json",
    }

    if api_mode == "DRIVE":
        return _estimate_drive(base_body, headers, timeout)
    return _estimate_single(base_body, headers, timeout)


def _latlng_body(coord: tuple[float, float]) -> dict:
    """Build the Routes API waypoint body for a coordinate.

    Args:
        coord (tuple[float, float]): A (latitude, longitude) pair.

    Returns:
        dict: The nested ``location.latLng`` structure expected by the API.
    """
    lat, lng = coord
    return {"location": {"latLng": {"latitude": lat, "longitude": lng}}}


def _departure_time() -> str:
    """Return a near-future UTC time formatted for the Routes API.

    The Routes API rejects a ``departureTime`` that is not strictly in the
    future, so a small buffer is added to absorb second-level truncation,
    request latency, and minor client/server clock skew.

    Returns:
        str: An RFC 3339 timestamp in UTC, a couple of minutes ahead of now.
    """
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=120)
    return future.strftime("%Y-%m-%dT%H:%M:%SZ")


def _estimate_drive(
    base_body: dict,
    headers: dict,
    timeout: int,
) -> RouteEstimate:
    """Estimate a driving route, querying optimistic and pessimistic traffic.

    Args:
        base_body (dict): The shared request body with origin, destination, and
            travel mode already set.
        headers (dict): The request headers, including the API key and field
            mask.
        timeout (int): Per-request timeout in seconds.

    Returns:
        RouteEstimate: A populated estimate with a duration range, or an
            unavailable estimate carrying an error message when a request fails
            or returns a non-200 status.
    """
    dep_time = _departure_time()

    optimistic_body = {
        **base_body,
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "departureTime": dep_time,
        "trafficModel": "OPTIMISTIC",
    }
    pessimistic_body = {
        **base_body,
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "departureTime": dep_time,
        "trafficModel": "PESSIMISTIC",
    }

    try:
        opt_resp = requests.post(ROUTES_ENDPOINT, json=optimistic_body,
                                 headers=headers, timeout=timeout)
        pess_resp = requests.post(ROUTES_ENDPOINT, json=pessimistic_body,
                                  headers=headers, timeout=timeout)
    except Exception as exc:
        return RouteEstimate(available=False, error=str(exc))

    if opt_resp.status_code != 200:
        return RouteEstimate(available=False, error=f"API error {opt_resp.status_code}")
    if pess_resp.status_code != 200:
        return RouteEstimate(available=False, error=f"API error {pess_resp.status_code}")

    return _parse_drive_responses(opt_resp.json(), pess_resp.json())


def _parse_drive_responses(opt_data: dict, pess_data: dict) -> RouteEstimate:
    """Combine optimistic and pessimistic drive responses into an estimate.

    Args:
        opt_data (dict): The parsed JSON body from the optimistic request.
        pess_data (dict): The parsed JSON body from the pessimistic request.

    Returns:
        RouteEstimate: A populated estimate, or an unavailable estimate carrying
            an error message when the responses lack the expected fields.
    """
    try:
        opt_route = opt_data["routes"][0]
        pess_route = pess_data["routes"][0]
        distance_m = int(opt_route["distanceMeters"])
        low_s = _parse_duration_seconds(opt_route["duration"])
        high_s = _parse_duration_seconds(pess_route["duration"])
    except (KeyError, IndexError, ValueError) as exc:
        return RouteEstimate(available=False, error=f"Unexpected API response: {exc}")

    return RouteEstimate(
        available=True,
        distance_m=distance_m,
        distance_text=format_distance(distance_m),
        duration_low_s=low_s,
        duration_high_s=high_s,
        duration_text=format_range(low_s, high_s),
    )


def _estimate_single(
    base_body: dict,
    headers: dict,
    timeout: int,
) -> RouteEstimate:
    """Estimate a route for a single (non-driving) travel mode.

    Args:
        base_body (dict): The shared request body with origin, destination, and
            travel mode already set.
        headers (dict): The request headers, including the API key and field
            mask.
        timeout (int): Per-request timeout in seconds.

    Returns:
        RouteEstimate: A populated estimate, or an unavailable estimate carrying
            an error message when the request fails or returns a non-200 status.
    """
    try:
        resp = requests.post(ROUTES_ENDPOINT, json=base_body, headers=headers, timeout=timeout)
    except Exception as exc:
        return RouteEstimate(available=False, error=str(exc))

    if resp.status_code != 200:
        return RouteEstimate(available=False, error=f"API error {resp.status_code}")

    return _parse_single_response(resp.json())


def _parse_single_response(data: dict) -> RouteEstimate:
    """Build an estimate from a single-route API response.

    Args:
        data (dict): The parsed JSON body from the request.

    Returns:
        RouteEstimate: A populated estimate whose low and high durations are
            equal, or an unavailable estimate carrying an error message when the
            response lacks the expected fields.
    """
    try:
        route = data["routes"][0]
        distance_m = int(route["distanceMeters"])
        duration_s = _parse_duration_seconds(route["duration"])
    except (KeyError, IndexError, ValueError) as exc:
        return RouteEstimate(available=False, error=f"Unexpected API response: {exc}")

    return RouteEstimate(
        available=True,
        distance_m=distance_m,
        distance_text=format_distance(distance_m),
        duration_low_s=duration_s,
        duration_high_s=duration_s,
        duration_text=format_range(duration_s, duration_s),
    )


def _parse_duration_seconds(value: str) -> float:
    """Parse a Routes API duration string into seconds.

    Args:
        value (str): A duration such as ``"123s"`` as returned by the API.

    Returns:
        float: The duration in seconds.
    """
    return float(value.rstrip("s"))


def format_distance(meters: int) -> str:
    """Format a distance in meters as human-readable text.

    Args:
        meters (int): The distance in meters.

    Returns:
        str: The distance in meters below 1 km, otherwise in kilometers with up
            to one decimal place.
    """
    if meters < 1000:
        return f"{meters} m"
    km = meters / 1000
    if km == int(km):
        return f"{int(km)} km"
    return f"{km:.1f} km"


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as human-readable text.

    Args:
        seconds (float): The duration in seconds.

    Returns:
        str: The duration as ``"Xh YYm"`` when at least an hour, otherwise as
            ``"Ym"``.
    """
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes = remainder // 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def format_range(low_s: float, high_s: float) -> str:
    """Format a duration range as human-readable text.

    Args:
        low_s (float): The lower-bound duration in seconds.
        high_s (float): The upper-bound duration in seconds.

    Returns:
        str: A single formatted duration when both bounds render identically,
            otherwise the two formatted bounds joined by an en dash.
    """
    low_text = format_duration(low_s)
    high_text = format_duration(high_s)
    if low_text == high_text:
        return low_text
    return f"{low_text} – {high_text}"


# Keep private aliases so existing callers that used the underscore names keep working.
_format_distance = format_distance
_format_duration = format_duration
_format_range = format_range
