from __future__ import annotations

import pytest

import directions
from directions import (
    RouteEstimate,
    _parse_duration_seconds,
    api_key_present,
    estimate_route,
    format_distance,
    format_duration,
    format_range,
)

# Aliases kept so the existing test bodies that reference the old names continue to work.
_format_distance = format_distance
_format_duration = format_duration
_format_range = format_range

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TWO_COORDS = [(38.7, -9.1), (41.1, -8.6)]
THREE_COORDS = [(38.7, -9.1), (40.0, -8.8), (41.1, -8.6)]


class _FakeResponse:
    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self._data = data

    def json(self) -> dict:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _drive_response(distance_m: int, duration_str: str) -> dict:
    return {"routes": [{"distanceMeters": distance_m, "duration": duration_str}]}


# ---------------------------------------------------------------------------
# api_key_present
# ---------------------------------------------------------------------------


def test_api_key_present_false_when_unset(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    assert api_key_present() is False


def test_api_key_present_true_when_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    assert api_key_present() is True


def test_api_key_present_false_for_empty_string(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "")
    assert api_key_present() is False


# ---------------------------------------------------------------------------
# estimate_route — guard conditions (no HTTP call)
# ---------------------------------------------------------------------------


def test_no_key_returns_unavailable_no_post(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    call_count = 0

    def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _FakeResponse(200, {})

    monkeypatch.setattr(directions.requests, "post", fake_post)
    result = estimate_route(TWO_COORDS)

    assert result.available is False
    assert call_count == 0


def test_no_key_error_message(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    result = estimate_route(TWO_COORDS)
    assert "GOOGLE_MAPS_API_KEY" in result.error


def test_too_few_coords_returns_unavailable(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    call_count = 0

    def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _FakeResponse(200, {})

    monkeypatch.setattr(directions.requests, "post", fake_post)
    result = estimate_route([(38.7, -9.1)])

    assert result.available is False
    assert call_count == 0


def test_too_few_coords_empty_list(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    result = estimate_route([])
    assert result.available is False
    assert "2 points" in result.error


# ---------------------------------------------------------------------------
# estimate_route — driving (two POST calls)
# ---------------------------------------------------------------------------


def test_driving_makes_two_post_calls(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    call_count = 0

    def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _FakeResponse(200, _drive_response(50000, "3600s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    estimate_route(TWO_COORDS, travel_mode="driving")

    assert call_count == 2


def test_driving_optimistic_pessimistic_durations(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    responses = [
        _FakeResponse(200, _drive_response(50000, "3600s")),   # optimistic
        _FakeResponse(200, _drive_response(50000, "4500s")),   # pessimistic
    ]
    call_index = 0

    def fake_post(*args, **kwargs):
        nonlocal call_index
        resp = responses[call_index]
        call_index += 1
        return resp

    monkeypatch.setattr(directions.requests, "post", fake_post)
    result = estimate_route(TWO_COORDS, travel_mode="driving")

    assert result.available is True
    assert result.duration_low_s == pytest.approx(3600.0)
    assert result.duration_high_s == pytest.approx(4500.0)


def test_driving_duration_text_shows_range(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    responses = [
        _FakeResponse(200, _drive_response(50000, "3600s")),
        _FakeResponse(200, _drive_response(50000, "4500s")),
    ]
    call_index = 0

    def fake_post(*args, **kwargs):
        nonlocal call_index
        resp = responses[call_index]
        call_index += 1
        return resp

    monkeypatch.setattr(directions.requests, "post", fake_post)
    result = estimate_route(TWO_COORDS, travel_mode="driving")

    assert " – " in result.duration_text


def test_driving_distance_parsed(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")

    def fake_post(*args, **kwargs):
        return _FakeResponse(200, _drive_response(123456, "3600s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    result = estimate_route(TWO_COORDS, travel_mode="driving")

    assert result.distance_m == 123456


def test_driving_trafficmodel_in_body(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    bodies = []

    def fake_post(url, *, json, **kwargs):
        bodies.append(json)
        return _FakeResponse(200, _drive_response(50000, "3600s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    estimate_route(TWO_COORDS, travel_mode="driving")

    assert len(bodies) == 2
    traffic_models = [b["trafficModel"] for b in bodies]
    assert "OPTIMISTIC" in traffic_models
    assert "PESSIMISTIC" in traffic_models


def test_driving_routing_preference_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    bodies = []

    def fake_post(url, *, json, **kwargs):
        bodies.append(json)
        return _FakeResponse(200, _drive_response(50000, "3600s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    estimate_route(TWO_COORDS, travel_mode="driving")

    for body in bodies:
        assert body.get("routingPreference") == "TRAFFIC_AWARE_OPTIMAL"


# ---------------------------------------------------------------------------
# estimate_route — walking (one POST call, single duration)
# ---------------------------------------------------------------------------


def test_walking_makes_one_post_call(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    call_count = 0

    def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _FakeResponse(200, _drive_response(5000, "1800s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    estimate_route(TWO_COORDS, travel_mode="walking")

    assert call_count == 1


def test_walking_low_equals_high(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")

    def fake_post(*args, **kwargs):
        return _FakeResponse(200, _drive_response(5000, "1800s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    result = estimate_route(TWO_COORDS, travel_mode="walking")

    assert result.available is True
    assert result.duration_low_s == result.duration_high_s


def test_walking_no_range_in_text(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")

    def fake_post(*args, **kwargs):
        return _FakeResponse(200, _drive_response(5000, "1800s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    result = estimate_route(TWO_COORDS, travel_mode="walking")

    assert " – " not in result.duration_text


# ---------------------------------------------------------------------------
# estimate_route — bicycling / transit (one call each)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["bicycling", "transit", "two-wheeler"])
def test_non_drive_modes_make_one_call(monkeypatch, mode):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    call_count = 0

    def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _FakeResponse(200, _drive_response(5000, "900s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    estimate_route(TWO_COORDS, travel_mode=mode)

    assert call_count == 1


# ---------------------------------------------------------------------------
# estimate_route — error handling
# ---------------------------------------------------------------------------


def test_non_200_returns_unavailable(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")

    def fake_post(*args, **kwargs):
        return _FakeResponse(403, {})

    monkeypatch.setattr(directions.requests, "post", fake_post)
    result = estimate_route(TWO_COORDS, travel_mode="walking")

    assert result.available is False
    assert "403" in result.error


def test_non_200_does_not_raise(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")

    def fake_post(*args, **kwargs):
        return _FakeResponse(500, {})

    monkeypatch.setattr(directions.requests, "post", fake_post)
    result = estimate_route(TWO_COORDS, travel_mode="walking")

    assert isinstance(result, RouteEstimate)


def test_exception_from_post_returns_unavailable(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")

    def fake_post(*args, **kwargs):
        raise ConnectionError("network down")

    monkeypatch.setattr(directions.requests, "post", fake_post)
    result = estimate_route(TWO_COORDS, travel_mode="walking")

    assert result.available is False
    assert result.error != ""


def test_exception_from_post_does_not_raise(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")

    def fake_post(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(directions.requests, "post", fake_post)
    result = estimate_route(TWO_COORDS)

    assert isinstance(result, RouteEstimate)


def test_drive_second_call_error_returns_unavailable(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    call_count = 0

    def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return _FakeResponse(500, {})
        return _FakeResponse(200, _drive_response(50000, "3600s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    result = estimate_route(TWO_COORDS, travel_mode="driving")

    assert result.available is False


# ---------------------------------------------------------------------------
# estimate_route — API body structure
# ---------------------------------------------------------------------------


def test_request_uses_x_goog_api_key_header(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "my-secret-key")
    captured_headers = []

    def fake_post(url, *, headers, **kwargs):
        captured_headers.append(headers)
        return _FakeResponse(200, _drive_response(5000, "900s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    estimate_route(TWO_COORDS, travel_mode="walking")

    assert captured_headers[0]["X-Goog-Api-Key"] == "my-secret-key"


def test_request_field_mask_header(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    captured_headers = []

    def fake_post(url, *, headers, **kwargs):
        captured_headers.append(headers)
        return _FakeResponse(200, _drive_response(5000, "900s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    estimate_route(TWO_COORDS, travel_mode="walking")

    assert "routes.distanceMeters" in captured_headers[0]["X-Goog-FieldMask"]
    assert "routes.duration" in captured_headers[0]["X-Goog-FieldMask"]


def test_request_endpoint_url(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    called_urls = []

    def fake_post(url, **kwargs):
        called_urls.append(url)
        return _FakeResponse(200, _drive_response(5000, "900s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    estimate_route(TWO_COORDS, travel_mode="walking")

    assert called_urls[0] == directions.ROUTES_ENDPOINT


def test_intermediates_included_in_body(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    bodies = []

    def fake_post(url, *, json, **kwargs):
        bodies.append(json)
        return _FakeResponse(200, _drive_response(5000, "900s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    estimate_route(THREE_COORDS, travel_mode="walking")

    assert "intermediates" in bodies[0]
    assert len(bodies[0]["intermediates"]) == 1


def test_two_coords_no_intermediates_in_body(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    bodies = []

    def fake_post(url, *, json, **kwargs):
        bodies.append(json)
        return _FakeResponse(200, _drive_response(5000, "900s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    estimate_route(TWO_COORDS, travel_mode="walking")

    assert "intermediates" not in bodies[0]


# ---------------------------------------------------------------------------
# Travel mode mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("input_mode", "expected_api_mode"),
    [
        ("driving", "DRIVE"),
        ("walking", "WALK"),
        ("bicycling", "BICYCLE"),
        ("two-wheeler", "TWO_WHEELER"),
        ("transit", "TRANSIT"),
    ],
)
def test_travel_mode_mapping(monkeypatch, input_mode, expected_api_mode):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    bodies = []

    def fake_post(url, *, json, **kwargs):
        bodies.append(json)
        return _FakeResponse(200, _drive_response(5000, "900s"))

    monkeypatch.setattr(directions.requests, "post", fake_post)
    estimate_route(TWO_COORDS, travel_mode=input_mode)

    assert bodies[0]["travelMode"] == expected_api_mode


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def test_parse_duration_seconds_basic():
    assert _parse_duration_seconds("8580s") == pytest.approx(8580.0)


def test_parse_duration_seconds_short():
    assert _parse_duration_seconds("60s") == pytest.approx(60.0)


def test_parse_duration_seconds_fractional():
    assert _parse_duration_seconds("3600s") == pytest.approx(3600.0)


def test_format_distance_under_1km():
    assert _format_distance(850) == "850 m"


def test_format_distance_exactly_1km():
    assert _format_distance(1000) == "1 km"


def test_format_distance_over_1km():
    text = _format_distance(123456)
    assert "km" in text
    assert "123" in text


def test_format_distance_fractional_km():
    text = _format_distance(1500)
    assert "1.5 km" == text


def test_format_duration_contains_hours_for_8580s():
    text = _format_duration(8580.0)
    assert "2h" in text


def test_format_duration_minutes_only():
    text = _format_duration(600.0)
    assert "10m" in text
    assert "h" not in text


def test_format_duration_zero_minutes():
    text = _format_duration(3600.0)
    assert "1h" in text


def test_format_range_same_low_high():
    result = _format_range(3600.0, 3600.0)
    assert " – " not in result


def test_format_range_different_low_high():
    result = _format_range(3600.0, 4500.0)
    assert " – " in result


def test_format_range_low_before_high():
    result = _format_range(3600.0, 4500.0)
    parts = result.split(" – ")
    assert len(parts) == 2
    assert "1h" in parts[0]
    assert "1h" in parts[1]
