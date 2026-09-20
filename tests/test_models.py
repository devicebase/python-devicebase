"""Tests for the SDK data models."""

from datetime import datetime, timedelta, timezone

import pytest

from devicebase.models import (
    MOUSE_BUTTONS,
    SCROLL_DIRECTIONS,
    AppInfo,
    Bounds,
    Device,
    DeviceInfo,
    HierarchyInfo,
    InputTextRequest,
    LaunchAppRequest,
    OperationResult,
    Point,
    parse_timestamp,
)

#: A row shaped like the one `GET /v1/devices` actually returns.
DEVICE_ROW = {
    "id": 10009,
    "serial": "EDGER9DE2GFD03XH-001",
    "state": "free",
    "name": "V2218A",
    "alias_name": "V2218A",
    "udid": "172.17.0.1:31002",
    "type": "adb",
    "brand": "vivo",
    "model": "V2218A",
    "os_type": "Android",
    "os_version": "13",
    "display": "",
    "location": "广东深圳",
    "operator": "电信",
    "network": "",
    "updated_at": "2026-09-20T16:00:51",
}


class TestPoint:
    """Tests for the Point model."""

    def test_defaults_and_values(self) -> None:
        assert (Point().x, Point().y) == (0, 0)
        point = Point(x=100, y=200)
        assert (point.x, point.y) == (100, 200)

    def test_to_dict_round_trip(self) -> None:
        assert Point(x=50, y=75).to_dict() == {"x": 50, "y": 75}
        assert Point.from_dict({"x": 50, "y": 75}) == Point(x=50, y=75)

    def test_from_dict_missing_and_uncoercible_keys(self) -> None:
        assert Point.from_dict({}) == Point()
        assert Point.from_dict({"x": "nope", "y": None}) == Point()

    def test_immutable(self) -> None:
        with pytest.raises(AttributeError):
            Point(x=10, y=20).x = 30  # type: ignore[misc]


class TestBounds:
    """Tests for the Bounds model."""

    def test_to_dict_round_trip(self) -> None:
        bounds = Bounds(x1=1, y1=2, x2=3, y2=4)
        assert bounds.to_dict() == {"x1": 1, "y1": 2, "x2": 3, "y2": 4}
        assert Bounds.from_dict(bounds.to_dict()) == bounds

    def test_from_dict_missing_keys(self) -> None:
        assert Bounds.from_dict({}) == Bounds()


class TestRequestPayloads:
    """Tests for the request body helpers."""

    def test_launch_app_request(self) -> None:
        assert LaunchAppRequest().app_name == ""
        assert LaunchAppRequest(app_name="com.a").to_dict() == {"app_name": "com.a"}

    def test_input_text_request(self) -> None:
        assert InputTextRequest().text == ""
        assert InputTextRequest(text="hi 世界").to_dict() == {"text": "hi 世界"}


class TestResponseContainers:
    """Tests for the passthrough response models."""

    def test_device_info_keeps_the_serial_and_payload(self) -> None:
        info = DeviceInfo.from_dict("dev-1", {"battery": 85})
        assert info.serial == "dev-1"
        assert info.data == {"battery": 85}

    def test_app_info(self) -> None:
        assert AppInfo.from_dict({"package": "com.a"}).data == {"package": "com.a"}

    def test_hierarchy_info(self) -> None:
        payload = {"nodes": [{"id": 1}]}
        assert HierarchyInfo.from_dict(payload).data == payload


class TestOperationResult:
    """Tests for OperationResult."""

    def test_success_flag_is_kept(self) -> None:
        assert OperationResult.from_dict({"success": False}).success is False
        assert OperationResult.from_dict({"success": True}).success is True

    def test_success_defaults_to_true(self) -> None:
        assert OperationResult.from_dict({"message": "OK"}).success is True

    def test_a_non_boolean_success_falls_back_to_true(self) -> None:
        assert OperationResult.from_dict({"success": "yes"}).success is True

    def test_payload_unwraps_the_envelope(self) -> None:
        result = OperationResult.from_dict({"code": 200, "data": {"exitCode": 1}})
        assert result.payload == {"exitCode": 1}
        assert result.data["code"] == 200

    def test_payload_is_empty_when_absent_or_not_an_object(self) -> None:
        assert OperationResult.from_dict({"code": 200}).payload == {}
        assert OperationResult.from_dict({"code": 200, "data": []}).payload == {}


class TestDevice:
    """Tests for the device row model."""

    def test_parses_a_real_row(self) -> None:
        device = Device.from_dict(DEVICE_ROW)
        assert device.id == 10009
        assert device.serial == "EDGER9DE2GFD03XH-001"
        assert device.state == "free"
        assert device.type == "adb"
        assert device.os_type == "Android"
        assert device.location == "广东深圳"

    def test_serial_falls_back_to_serialno(self) -> None:
        # Some routes name the same column "serialno"; both must resolve, since
        # the value is what every control call takes.
        assert Device.from_dict({"serialno": "db-1"}).serial == "db-1"

    def test_serial_prefers_the_serial_field(self) -> None:
        assert Device.from_dict({"serial": "a", "serialno": "b"}).serial == "a"

    def test_missing_fields_default(self) -> None:
        device = Device.from_dict({})
        assert device.serial == ""
        assert device.id == 0
        assert device.updated_at is None

    def test_uncoercible_fields_default(self) -> None:
        device = Device.from_dict({"id": "10009", "name": 42, "serial": None})
        assert device.id == 0  # a string id does not become an int
        assert device.name == ""
        assert device.serial == ""

    def test_display_name_prefers_alias_then_name_then_serial(self) -> None:
        assert Device.from_dict({"alias_name": "A", "name": "B", "serial": "C"}).display_name == "A"
        assert Device.from_dict({"name": "B", "serial": "C"}).display_name == "B"
        assert Device.from_dict({"serial": "C"}).display_name == "C"

    def test_zero_id_is_not_mistaken_for_absent(self) -> None:
        assert Device.from_dict({"id": 0}).id == 0
        # A boolean is an int subclass, and must not read as an id.
        assert Device.from_dict({"id": True}).id == 0


class TestParseTimestamp:
    """The server is inconsistent about timestamp format."""

    def test_rfc3339_with_offset(self) -> None:
        parsed = parse_timestamp("2026-09-20T15:11:31+08:00")
        assert parsed is not None
        assert parsed.utcoffset() == timedelta(hours=8)
        assert parsed == datetime(2026, 9, 20, 15, 11, 31, tzinfo=timezone(timedelta(hours=8)))

    def test_zulu_suffix(self) -> None:
        parsed = parse_timestamp("2026-09-20T15:11:31Z")
        assert parsed is not None
        assert parsed.tzinfo is not None

    def test_naive_form_the_device_rows_use(self) -> None:
        parsed = parse_timestamp("2026-09-20T16:00:51")
        assert parsed == datetime(2026, 9, 20, 16, 0, 51)
        assert parsed.tzinfo is None

    def test_fractional_seconds(self) -> None:
        assert parse_timestamp("2026-09-20T15:11:31.123") == datetime(
            2026, 9, 20, 15, 11, 31, 123000
        )

    def test_other_layouts(self) -> None:
        assert parse_timestamp("2026-09-20 15:11:31") == datetime(2026, 9, 20, 15, 11, 31)
        assert parse_timestamp("2026-09-20") == datetime(2026, 9, 20)

    @pytest.mark.parametrize("value", ["", "   ", "not a date", None, 42, [], {}])
    def test_unrecognized_values_degrade_to_none(self, value: object) -> None:
        # A display field must never fail the response that carries it.
        assert parse_timestamp(value) is None


class TestConstants:
    """The enumerated argument sets match the API's own documentation."""

    def test_mouse_buttons(self) -> None:
        assert MOUSE_BUTTONS == ("left", "right", "middle")

    def test_scroll_directions(self) -> None:
        assert SCROLL_DIRECTIONS == ("up", "down", "left", "right")
