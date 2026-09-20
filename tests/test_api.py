"""Table-driven coverage of every leaf action's method, path and body.

The contract under test is the route table itself. Each case asserts the HTTP
method, the path and the exact request body or query string for one action, so a
renamed action, a swapped verb or a dropped field fails here rather than on a
real device.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
import respx

from devicebase.errors import DeviceBaseError, ValidationError
from devicebase.http_client import DeviceBaseHttpClient
from devicebase.models import Bounds, Point

BASE_URL = "http://api.test"
MOBILE = "mob-1"
BROWSER = "br-1"
COMPUTER = "pc-1"


@dataclass(frozen=True)
class Action:
    """One API action and the request it is expected to produce."""

    name: str
    call: Callable[[DeviceBaseHttpClient], Any]
    method: str
    path: str
    body: dict[str, Any] | None = None
    params: dict[str, str] = field(default_factory=dict)


MOBILE_ACTIONS = [
    Action(
        "mobile get_device_info",
        lambda c: c.get_device_info(MOBILE),
        "POST",
        f"/v1/deviceinfo/{MOBILE}",
    ),
    Action(
        "mobile tap",
        lambda c: c.tap(MOBILE, Point(x=10, y=20)),
        "POST",
        f"/v1/tap/{MOBILE}",
        {"x": 10, "y": 20},
    ),
    Action(
        "mobile double_tap",
        lambda c: c.double_tap(MOBILE, Point(x=10, y=20)),
        "POST",
        f"/v1/double_tap/{MOBILE}",
        {"x": 10, "y": 20},
    ),
    Action(
        "mobile long_press",
        lambda c: c.long_press(MOBILE, Point(x=10, y=20)),
        "POST",
        f"/v1/long_press/{MOBILE}",
        {"x": 10, "y": 20},
    ),
    Action(
        "mobile swipe",
        lambda c: c.swipe(MOBILE, Bounds(x1=1, y1=2, x2=3, y2=4)),
        "POST",
        f"/v1/swipe/{MOBILE}",
        {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
    ),
    Action("mobile back", lambda c: c.back(MOBILE), "POST", f"/v1/back/{MOBILE}"),
    Action("mobile home", lambda c: c.home(MOBILE), "POST", f"/v1/home/{MOBILE}"),
    Action(
        "mobile launch_app",
        lambda c: c.launch_app(MOBILE, "com.example.app"),
        "POST",
        f"/v1/launch_app/{MOBILE}",
        {"app_name": "com.example.app"},
    ),
    Action(
        "mobile stop_app",
        lambda c: c.stop_app(MOBILE, "com.example.app"),
        "POST",
        f"/v1/stop_app/{MOBILE}",
        {"app_name": "com.example.app"},
    ),
    Action(
        "mobile stop_current_app",
        lambda c: c.stop_current_app(MOBILE),
        "POST",
        f"/v1/stop_current_app/{MOBILE}",
    ),
    Action(
        "mobile get_current_app",
        lambda c: c.get_current_app(MOBILE),
        "POST",
        f"/v1/current_app/{MOBILE}",
    ),
    Action(
        "mobile input_text",
        lambda c: c.input_text(MOBILE, "hello"),
        "POST",
        f"/v1/input/{MOBILE}",
        {"text": "hello"},
    ),
    Action("mobile clear_text", lambda c: c.clear_text(MOBILE), "POST", f"/v1/clear_text/{MOBILE}"),
    Action(
        "mobile bash",
        lambda c: c.bash(MOBILE, "ls -la"),
        "POST",
        f"/v1/bash/{MOBILE}",
        {"command": "ls -la"},
    ),
    Action(
        "mobile dump_hierarchy",
        lambda c: c.dump_hierarchy(MOBILE),
        "POST",
        f"/v1/dump_hierarchy/{MOBILE}",
    ),
    Action(
        "mobile install_app",
        lambda c: c.install_app(MOBILE, "/sdcard/a.apk"),
        "POST",
        f"/v1/install_app/{MOBILE}",
        {"app_path": "/sdcard/a.apk"},
    ),
    Action(
        "mobile install_status",
        lambda c: c.install_status(MOBILE, "task-7"),
        "GET",
        f"/v1/install_status/{MOBILE}",
        None,
        {"install_id": "task-7"},
    ),
    Action(
        "cross-family screenshot",
        lambda c: c.get_screenshot(MOBILE),
        "POST",
        f"/v1/screen/{MOBILE}",
    ),
    Action(
        "cross-family download_screenshot",
        lambda c: c.download_screenshot(MOBILE),
        "GET",
        f"/v1/screenshot/{MOBILE}",
    ),
]

BROWSER_ACTIONS = [
    Action(
        "browser navigate",
        lambda c: c.browser_navigate(BROWSER, "https://example.com"),
        "POST",
        f"/api/browser/{BROWSER}/navigate",
        {"url": "https://example.com"},
    ),
    Action(
        "browser refresh",
        lambda c: c.browser_refresh(BROWSER),
        "POST",
        f"/api/browser/{BROWSER}/refresh",
    ),
    Action(
        "browser go_back",
        lambda c: c.browser_go_back(BROWSER),
        "POST",
        f"/api/browser/{BROWSER}/go_back",
    ),
    Action(
        "browser go_forward",
        lambda c: c.browser_go_forward(BROWSER),
        "POST",
        f"/api/browser/{BROWSER}/go_forward",
    ),
    Action(
        "browser input",
        lambda c: c.browser_input(BROWSER, "hello"),
        "POST",
        f"/api/browser/{BROWSER}/input",
        {"text": "hello"},
    ),
    Action(
        "browser click",
        lambda c: c.browser_click(BROWSER, "#go"),
        "POST",
        f"/api/browser/{BROWSER}/click",
        {"selector": "#go"},
    ),
    Action(
        "browser fill",
        lambda c: c.browser_fill(BROWSER, "#q", "v"),
        "POST",
        f"/api/browser/{BROWSER}/fill",
        {"selector": "#q", "value": "v"},
    ),
    Action(
        "browser select",
        lambda c: c.browser_select(BROWSER, "#s", "v"),
        "POST",
        f"/api/browser/{BROWSER}/select",
        {"selector": "#s", "value": "v"},
    ),
    Action(
        "browser text",
        lambda c: c.browser_text(BROWSER, "#t"),
        "GET",
        f"/api/browser/{BROWSER}/text",
        None,
        {"selector": "#t"},
    ),
    Action(
        "browser attribute",
        lambda c: c.browser_attribute(BROWSER, "#a", "href"),
        "GET",
        f"/api/browser/{BROWSER}/attribute",
        None,
        {"selector": "#a", "attribute": "href"},
    ),
    Action(
        "browser exists",
        lambda c: c.browser_exists(BROWSER, "#e"),
        "GET",
        f"/api/browser/{BROWSER}/exists",
        None,
        {"selector": "#e"},
    ),
    Action(
        "browser execute",
        lambda c: c.browser_execute(BROWSER, "1+1"),
        "POST",
        f"/api/browser/{BROWSER}/execute",
        {"script": "1+1"},
    ),
    Action(
        "browser hotkey",
        lambda c: c.browser_hotkey(BROWSER, ["Meta", "a"]),
        "POST",
        f"/api/browser/{BROWSER}/hotkey",
        {"keys": ["Meta", "a"]},
    ),
    Action(
        "browser state", lambda c: c.browser_state(BROWSER), "GET", f"/api/browser/{BROWSER}/state"
    ),
    Action(
        "browser tabs", lambda c: c.browser_tabs(BROWSER), "GET", f"/api/browser/{BROWSER}/tabs"
    ),
    Action(
        "browser tab_open",
        lambda c: c.browser_tab_open(BROWSER, "https://example.com"),
        "POST",
        f"/api/browser/{BROWSER}/tab/open",
        {"url": "https://example.com"},
    ),
    Action(
        "browser tab_close",
        lambda c: c.browser_tab_close(BROWSER, "T1"),
        "POST",
        f"/api/browser/{BROWSER}/tab/close",
        {"tab_id": "T1"},
    ),
    Action(
        "browser tab_close_all",
        lambda c: c.browser_tab_close_all(BROWSER),
        "POST",
        f"/api/browser/{BROWSER}/tab/close_all",
    ),
    Action(
        "browser tab_switch",
        lambda c: c.browser_tab_switch(BROWSER, "T1"),
        "POST",
        f"/api/browser/{BROWSER}/tab/switch",
        {"tab_id": "T1"},
    ),
    Action(
        "browser launch",
        lambda c: c.browser_launch(BROWSER),
        "POST",
        f"/api/browser/{BROWSER}/launch",
    ),
    Action(
        "browser close", lambda c: c.browser_close(BROWSER), "POST", f"/api/browser/{BROWSER}/close"
    ),
]

COMPUTER_ACTIONS = [
    Action(
        "computer click",
        lambda c: c.computer_click(COMPUTER, 5, 6),
        "POST",
        f"/api/computer/{COMPUTER}/click",
        {"x": 5, "y": 6},
    ),
    Action(
        "computer click with button",
        lambda c: c.computer_click(COMPUTER, 5, 6, button="right"),
        "POST",
        f"/api/computer/{COMPUTER}/click",
        {"x": 5, "y": 6, "button": "right"},
    ),
    Action(
        "computer double_click",
        lambda c: c.computer_double_click(COMPUTER, 5, 6),
        "POST",
        f"/api/computer/{COMPUTER}/double_click",
        {"x": 5, "y": 6},
    ),
    Action(
        "computer long_click",
        lambda c: c.computer_long_click(COMPUTER, 5, 6),
        "POST",
        f"/api/computer/{COMPUTER}/long_click",
        {"x": 5, "y": 6},
    ),
    Action(
        "computer long_click with duration",
        lambda c: c.computer_long_click(COMPUTER, 5, 6, duration=2),
        "POST",
        f"/api/computer/{COMPUTER}/long_click",
        {"x": 5, "y": 6, "duration": 2},
    ),
    Action(
        "computer move",
        lambda c: c.computer_move(COMPUTER, 5, 6),
        "POST",
        f"/api/computer/{COMPUTER}/move",
        {"x": 5, "y": 6},
    ),
    Action(
        "computer drag",
        lambda c: c.computer_drag(COMPUTER, 1, 2, 3, 4),
        "POST",
        f"/api/computer/{COMPUTER}/drag",
        {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
    ),
    Action(
        "computer scroll",
        lambda c: c.computer_scroll(COMPUTER, "down"),
        "POST",
        f"/api/computer/{COMPUTER}/scroll",
        {"direction": "down"},
    ),
    Action(
        "computer scroll with amount",
        lambda c: c.computer_scroll(COMPUTER, "down", amount=3),
        "POST",
        f"/api/computer/{COMPUTER}/scroll",
        {"direction": "down", "amount": 3},
    ),
    Action(
        "computer type_text",
        lambda c: c.computer_type_text(COMPUTER, "hi"),
        "POST",
        f"/api/computer/{COMPUTER}/type_text",
        {"text": "hi"},
    ),
    Action(
        "computer press",
        lambda c: c.computer_press(COMPUTER, "Enter"),
        "POST",
        f"/api/computer/{COMPUTER}/press",
        {"key": "Enter"},
    ),
    Action(
        "computer hotkey",
        lambda c: c.computer_hotkey(COMPUTER, ["Meta", "c"]),
        "POST",
        f"/api/computer/{COMPUTER}/hotkey",
        {"keys": ["Meta", "c"]},
    ),
    Action(
        "computer position",
        lambda c: c.computer_position(COMPUTER),
        "GET",
        f"/api/computer/{COMPUTER}/position",
    ),
    Action(
        "computer screen_size",
        lambda c: c.computer_screen_size(COMPUTER),
        "GET",
        f"/api/computer/{COMPUTER}/screen_size",
    ),
    Action(
        "computer permissions",
        lambda c: c.computer_permissions(COMPUTER),
        "GET",
        f"/api/computer/{COMPUTER}/permissions",
    ),
    Action(
        "computer launch_app",
        lambda c: c.computer_launch_app(COMPUTER, "Safari"),
        "POST",
        f"/api/computer/{COMPUTER}/launch_app",
        {"app_name": "Safari"},
    ),
    Action(
        "computer wait",
        lambda c: c.computer_wait(COMPUTER, 1500),
        "POST",
        f"/api/computer/{COMPUTER}/wait",
        {"seconds": 1.5},
    ),
    Action(
        "computer wait never goes negative",
        lambda c: c.computer_wait(COMPUTER, -500),
        "POST",
        f"/api/computer/{COMPUTER}/wait",
        {"seconds": 0},
    ),
    Action(
        "computer bash",
        lambda c: c.computer_bash(COMPUTER, "whoami"),
        "POST",
        f"/api/computer/{COMPUTER}/bash",
        {"command": "whoami"},
    ),
    Action(
        "computer bash with timeout",
        lambda c: c.computer_bash(COMPUTER, "whoami", timeout_seconds=30),
        "POST",
        f"/api/computer/{COMPUTER}/bash",
        {"command": "whoami", "timeout": 30},
    ),
]

DEVICE_ACTIONS = [
    Action("list_devices", lambda c: c.list_devices(), "GET", "/v1/devices"),
    Action(
        "list_devices with filters",
        lambda c: c.list_devices(keyword="pixel", state="free", device_type="browser", limit=5),
        "GET",
        "/v1/devices",
        None,
        {"keyword": "pixel", "state": "free", "type": "browser", "limit": "5"},
    ),
]

ALL_ACTIONS = MOBILE_ACTIONS + BROWSER_ACTIONS + COMPUTER_ACTIONS + DEVICE_ACTIONS


def make_client() -> DeviceBaseHttpClient:
    """Build a client pointed at the fake API host."""
    return DeviceBaseHttpClient(base_url=BASE_URL, api_key="test-key")


@pytest.fixture
def route() -> Any:
    """Capture every request and answer with a successful envelope."""
    with respx.mock:
        yield respx.route().mock(return_value=httpx.Response(200, json={"code": 200, "data": {}}))


@pytest.mark.parametrize("action", ALL_ACTIONS, ids=lambda a: a.name)
def test_leaf_action(action: Action, route: Any) -> None:
    """Every action sends the documented method, path, body and query."""
    with make_client() as client:
        action.call(client)

    request = route.calls.last.request
    assert request.method == action.method
    assert request.url.path == action.path

    if action.body is None:
        assert request.content == b"", "expected no request body"
    else:
        assert json.loads(request.content) == action.body

    assert dict(request.url.params) == action.params


def test_every_action_is_covered() -> None:
    """The route table stays the documented size."""
    assert len(ALL_ACTIONS) == 62
    assert len(MOBILE_ACTIONS) == 19
    assert len(BROWSER_ACTIONS) == 21
    assert len(COMPUTER_ACTIONS) == 20


def test_action_names_are_unique() -> None:
    names = [action.name for action in ALL_ACTIONS]
    assert len(names) == len(set(names))


class TestValidation:
    """Enumerated arguments are rejected locally, before the network.

    The rejection uses the SDK's own ValidationError rather than a bare
    ValueError, so one ``except DeviceBaseError`` covers a bad argument and a
    rejected request alike.
    """

    def test_local_rejections_are_devicebase_errors(self) -> None:
        with make_client() as client:
            with pytest.raises(DeviceBaseError) as exc_info:
                client.computer_scroll(COMPUTER, "diagonal")  # type: ignore[arg-type]
            # Nothing was sent, so there is no HTTP status to report.
            assert exc_info.value.status_code is None

    def test_unknown_mouse_button(self) -> None:
        with (
            make_client() as client,
            pytest.raises(ValidationError, match="button must be one of left, right, middle"),
        ):
            client.computer_click(COMPUTER, 1, 2, button="sideways")  # type: ignore[arg-type]

    def test_unknown_scroll_direction(self) -> None:
        with (
            make_client() as client,
            pytest.raises(ValidationError, match="direction must be one of up, down, left, right"),
        ):
            client.computer_scroll(COMPUTER, "diagonal")  # type: ignore[arg-type]

    @pytest.mark.parametrize("button", ["left", "right", "middle"])
    def test_accepted_buttons(self, button: str, route: Any) -> None:
        with make_client() as client:
            client.computer_click(COMPUTER, 1, 2, button=button)  # type: ignore[arg-type]
        assert json.loads(route.calls.last.request.content)["button"] == button

    @pytest.mark.parametrize("direction", ["up", "down", "left", "right"])
    def test_accepted_directions(self, direction: str, route: Any) -> None:
        with make_client() as client:
            client.computer_scroll(COMPUTER, direction)  # type: ignore[arg-type]
        assert json.loads(route.calls.last.request.content)["direction"] == direction


class TestResults:
    """The return values carry the payload through."""

    def test_operation_result_success_defaults_true(self, route: Any) -> None:
        with make_client() as client:
            result = client.browser_refresh(BROWSER)
        assert result.success is True

    def test_operation_result_reports_a_false_success(self) -> None:
        with respx.mock:
            respx.route().mock(
                return_value=httpx.Response(200, json={"code": 200, "success": False})
            )
            with make_client() as client:
                result = client.browser_refresh(BROWSER)
        assert result.success is False

    def test_non_zero_exit_code_is_not_an_error(self, route: Any) -> None:
        with respx.mock:
            respx.route().mock(
                return_value=httpx.Response(
                    200,
                    json={"code": 200, "data": {"exitCode": 1, "stdout": ""}},
                )
            )
            with make_client() as client:
                result = client.computer_bash(COMPUTER, "exit 1")
        assert result.payload["exitCode"] == 1
        assert result.data["code"] == 200

    def test_payload_is_empty_without_a_data_object(self, route: Any) -> None:
        with make_client() as client:
            result = client.browser_refresh(BROWSER)
        assert result.payload == {}

    def test_device_info_keeps_the_payload(self, route: Any) -> None:
        with respx.mock:
            respx.route().mock(return_value=httpx.Response(200, json={"code": 200, "battery": 85}))
            with make_client() as client:
                info = client.get_device_info(MOBILE)
        assert info.serialno == MOBILE
        assert info.data["battery"] == 85


class TestListDevices:
    """Discovery parses the rows into typed Devices."""

    @pytest.mark.parametrize("limit", [0, -1])
    def test_non_positive_limit_is_rejected(self, limit: int, route: Any) -> None:
        # Omitted rather than sent as 0, so the server applies its own default.
        with (
            make_client() as client,
            pytest.raises(ValidationError, match="limit must be greater than 0"),
        ):
            client.list_devices(limit=limit)

    def test_parses_rows(self, route: Any) -> None:
        payload = {
            "code": 200,
            "data": [
                {
                    "id": 10009,
                    "serial": "EDGER9DE2GFD03XH-001",
                    "state": "free",
                    "name": "V2218A",
                    "alias_name": "My Phone",
                    "type": "adb",
                    "os_type": "Android",
                    "updated_at": "2026-09-20T16:00:51",
                },
                {"id": 2, "serial": "br-1", "type": "browser"},
            ],
        }
        with respx.mock:
            respx.route().mock(return_value=httpx.Response(200, json=payload))
            with make_client() as client:
                devices = client.list_devices(device_type="mobile")

        assert [d.serialno for d in devices] == ["EDGER9DE2GFD03XH-001", "br-1"]
        assert devices[0].display_name == "My Phone"
        assert devices[1].display_name == "br-1"

    def test_missing_data_key_is_an_empty_list(self) -> None:
        with respx.mock:
            respx.route().mock(return_value=httpx.Response(200, json={"code": 200}))
            with make_client() as client:
                assert client.list_devices() == []

    def test_non_list_data_is_an_empty_list(self) -> None:
        with respx.mock:
            respx.route().mock(return_value=httpx.Response(200, json={"code": 200, "data": "nope"}))
            with make_client() as client:
                assert client.list_devices() == []

    def test_non_object_rows_are_skipped(self) -> None:
        with respx.mock:
            respx.route().mock(
                return_value=httpx.Response(
                    200, json={"code": 200, "data": [{"serial": "a"}, "junk", 7]}
                )
            )
            with make_client() as client:
                assert [d.serialno for d in client.list_devices()] == ["a"]
