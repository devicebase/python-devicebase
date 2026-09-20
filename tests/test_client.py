"""Tests for the serialno-bound facade, DeviceBaseClient."""

import json
import os
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import httpx
import pytest
import respx

from devicebase.client import DeviceBaseClient, list_devices
from devicebase.errors import (
    AuthenticationError,
    BusinessError,
    DeviceBaseError,
    DeviceNotFoundError,
    ValidationError,
)
from devicebase.models import Bounds, Point

BASE_URL = "http://api.test"
SERIAL = "mob-1"


@pytest.fixture
def route() -> Any:
    """Capture every request and answer with a successful envelope."""
    with respx.mock:
        yield respx.route().mock(return_value=httpx.Response(200, json={"code": 200, "data": {}}))


def make_client(serialno: str | None = SERIAL, **kwargs: Any) -> DeviceBaseClient:
    """Build a facade pointed at the fake API host."""
    return DeviceBaseClient(
        serialno=serialno,
        base_url=BASE_URL,
        api_key="test-key",
        **kwargs,
    )


class TestConstruction:
    """Construction, configuration and lifecycle."""

    def test_explicit_params(self) -> None:
        client = make_client()
        assert client.serialno == SERIAL
        assert client._base_url == BASE_URL  # noqa: SLF001
        client.close()

    def test_env_vars(self) -> None:
        with patch.dict(
            os.environ,
            {"DEVICEBASE_BASE_URL": BASE_URL, "DEVICEBASE_API_KEY": "env-key"},
        ):
            client = DeviceBaseClient(serialno=SERIAL)
            assert client._base_url == BASE_URL  # noqa: SLF001
            client.close()

    def test_missing_api_key_raises(self) -> None:
        with patch.dict(os.environ, {}, clear=True), pytest.raises(AuthenticationError):
            DeviceBaseClient(serialno=SERIAL, base_url=BASE_URL)

    def test_serial_is_optional(self) -> None:
        client = make_client(serialno=None)
        assert client.serialno is None
        client.close()

    def test_context_manager(self) -> None:
        with make_client() as client:
            assert isinstance(client, DeviceBaseClient)

    def test_http_property_exposes_the_full_surface(self) -> None:
        with make_client() as client:
            assert hasattr(client.http, "browser_click")
            assert hasattr(client.http, "computer_bash")


class TestDeprecatedSerialAlias:
    """`serial` still works, warns, and loses to `serialno`."""

    def test_serial_keyword_still_binds(self) -> None:
        with pytest.warns(DeprecationWarning, match="serialno"):
            client = DeviceBaseClient(serial=SERIAL, base_url=BASE_URL, api_key="k")
        assert client.serialno == SERIAL
        client.close()

    def test_serial_property_still_reads(self) -> None:
        with make_client() as client, pytest.warns(DeprecationWarning, match="serialno"):
            assert client.serial == SERIAL

    def test_passing_both_is_rejected(self) -> None:
        # Silently picking one would hide a caller's mistake.
        with pytest.raises(ValidationError):
            DeviceBaseClient(
                serialno=SERIAL,
                serial="other",
                base_url=BASE_URL,
                api_key="k",
            )

    def test_serialno_alone_does_not_warn(self) -> None:
        import warnings as warnings_module

        with warnings_module.catch_warnings():
            warnings_module.simplefilter("error", DeprecationWarning)
            with make_client() as client:
                assert client.serialno == SERIAL


SERIAL_BOUND_CALLS: list[tuple[str, Callable[[DeviceBaseClient], Any], str]] = [
    ("get_device_info", lambda c: c.get_device_info(), "/v1/deviceinfo/mob-1"),
    ("tap", lambda c: c.tap(1, 2), "/v1/tap/mob-1"),
    ("double_tap", lambda c: c.double_tap(1, 2), "/v1/double_tap/mob-1"),
    ("long_press", lambda c: c.long_press(1, 2), "/v1/long_press/mob-1"),
    ("swipe", lambda c: c.swipe(1, 2, 3, 4), "/v1/swipe/mob-1"),
    ("back", lambda c: c.back(), "/v1/back/mob-1"),
    ("home", lambda c: c.home(), "/v1/home/mob-1"),
    ("launch_app", lambda c: c.launch_app("com.a"), "/v1/launch_app/mob-1"),
    ("stop_app", lambda c: c.stop_app("com.a"), "/v1/stop_app/mob-1"),
    ("stop_current_app", lambda c: c.stop_current_app(), "/v1/stop_current_app/mob-1"),
    ("get_current_app", lambda c: c.get_current_app(), "/v1/current_app/mob-1"),
    ("input_text", lambda c: c.input_text("hi"), "/v1/input/mob-1"),
    ("clear_text", lambda c: c.clear_text(), "/v1/clear_text/mob-1"),
    ("bash", lambda c: c.bash("ls"), "/v1/bash/mob-1"),
    ("dump_hierarchy", lambda c: c.dump_hierarchy(), "/v1/dump_hierarchy/mob-1"),
    ("install_app", lambda c: c.install_app("/tmp/a.apk"), "/v1/install_app/mob-1"),
    ("install_status", lambda c: c.install_status("t1"), "/v1/install_status/mob-1"),
    ("get_screenshot", lambda c: c.get_screenshot(), "/v1/screen/mob-1"),
    ("download_screenshot", lambda c: c.download_screenshot(), "/v1/screenshot/mob-1"),
]

SERIAL_BOUND_METHODS = {
    "get_device_info": "POST",
    "install_status": "GET",
    "download_screenshot": "GET",
}


class TestSerialBinding:
    """Every mobile action fills in the bound serialno."""

    @pytest.mark.parametrize(
        ("name", "call", "path"),
        SERIAL_BOUND_CALLS,
        ids=[name for name, _, _ in SERIAL_BOUND_CALLS],
    )
    def test_binds_the_serial(
        self,
        name: str,
        call: Callable[[DeviceBaseClient], Any],
        path: str,
        route: Any,
    ) -> None:
        with make_client() as client:
            call(client)
        request = route.calls.last.request
        assert request.url.path == path
        assert request.method == SERIAL_BOUND_METHODS.get(name, "POST")

    def test_touch_helpers_build_the_right_bodies(self, route: Any) -> None:
        with make_client() as client:
            client.tap(10, 20)
            assert json.loads(route.calls[-1].request.content) == {"x": 10, "y": 20}
            client.swipe(1, 2, 3, 4)
            assert json.loads(route.calls[-1].request.content) == {
                "x1": 1,
                "y1": 2,
                "x2": 3,
                "y2": 4,
            }

    def test_the_http_layer_takes_point_and_bounds_objects(self, route: Any) -> None:
        with make_client() as client:
            client.http.tap(SERIAL, Point(x=1, y=2))
            client.http.swipe(SERIAL, Bounds(x1=1, y1=2, x2=3, y2=4))
            assert json.loads(route.calls[-1].request.content) == {
                "x1": 1,
                "y1": 2,
                "x2": 3,
                "y2": 4,
            }


class TestUnboundSerial:
    """A client with no serialno bound can still discover devices."""

    def test_mobile_action_explains_what_to_do(self) -> None:
        with (
            make_client(serialno=None) as client,
            pytest.raises(DeviceBaseError, match="No device serialno is bound") as exc_info,
        ):
            client.tap(1, 2)
        assert "list_devices" in str(exc_info.value)

    def test_list_devices_works_without_a_serial(self, route: Any) -> None:
        with make_client(serialno=None) as client:
            assert client.list_devices() == []
        assert route.calls.last.request.url.path == "/v1/devices"

    def test_websocket_clients_need_a_serial(self) -> None:
        with make_client(serialno=None) as client:
            with pytest.raises(DeviceBaseError, match="No device serialno is bound"):
                client.minicap_client()
            with pytest.raises(DeviceBaseError, match="No device serialno is bound"):
                client.minitouch_client()

    def test_browser_actions_need_no_bound_serial(self, route: Any) -> None:
        with make_client(serialno=None) as client:
            client.http.browser_refresh("br-1")
        assert route.calls.last.request.url.path == "/api/browser/br-1/refresh"


class TestWebSocketClients:
    """The streaming clients are built from the bound configuration."""

    def test_minicap_client_uses_the_bound_serial(self) -> None:
        with make_client() as client:
            minicap = client.minicap_client()
        # An http base URL maps onto ws://, an https one onto wss://.
        assert minicap._url == f"ws://api.test/v1/minicap/{SERIAL}"  # noqa: SLF001

    def test_https_base_url_upgrades_to_wss(self) -> None:
        with DeviceBaseClient(serialno=SERIAL, base_url="https://api.test", api_key="k") as c:
            assert c.minicap_client()._url.startswith("wss://")  # noqa: SLF001

    def test_minitouch_client_uses_the_bound_serial(self) -> None:
        with make_client() as client:
            minitouch = client.minitouch_client()
        assert minitouch._url == f"ws://api.test/v1/minitouch/{SERIAL}"  # noqa: SLF001

    def test_stream_minicap_wraps_the_client(self) -> None:
        with make_client() as client:
            frames = client.stream_minicap()
        assert hasattr(frames, "__anext__")


class TestDeviceListing:
    """The facade forwards the filters."""

    @respx.mock
    def test_filters_reach_the_query_string(self) -> None:
        route = respx.get(f"{BASE_URL}/v1/devices").mock(
            return_value=httpx.Response(
                200,
                json={"code": 200, "data": [{"serial": "br-1", "type": "browser"}]},
            )
        )
        with make_client() as client:
            devices = client.list_devices(device_type="browser", limit=5, state="free")
        assert [d.serialno for d in devices] == ["br-1"]
        params = route.calls.last.request.url.params
        assert params["type"] == "browser"
        assert params["limit"] == "5"
        assert params["state"] == "free"


class TestModuleLevelListDevices:
    """The discovery convenience function."""

    @respx.mock
    def test_returns_devices(self) -> None:
        respx.get(f"{BASE_URL}/v1/devices").mock(
            return_value=httpx.Response(200, json={"code": 200, "data": [{"serial": "a"}]})
        )
        devices = list_devices(base_url=BASE_URL, api_key="k")
        assert [d.serialno for d in devices] == ["a"]

    @respx.mock
    def test_uses_the_environment_when_unconfigured(self) -> None:
        respx.get(f"{BASE_URL}/v1/devices").mock(
            return_value=httpx.Response(200, json={"code": 200, "data": []})
        )
        with patch.dict(
            os.environ,
            {"DEVICEBASE_BASE_URL": BASE_URL, "DEVICEBASE_API_KEY": "env-key"},
        ):
            assert list_devices(device_type="mobile") == []


class TestErrorPropagation:
    """Both failure layers reach the caller through the facade."""

    @respx.mock
    def test_http_error(self) -> None:
        respx.post(f"{BASE_URL}/v1/deviceinfo/{SERIAL}").mock(
            return_value=httpx.Response(404, json={"message": "设备不存在"})
        )
        with make_client() as client, pytest.raises(DeviceNotFoundError):
            client.get_device_info()

    @respx.mock
    def test_business_error(self) -> None:
        respx.post(f"{BASE_URL}/v1/tap/{SERIAL}").mock(
            return_value=httpx.Response(200, json={"code": 503, "message": "服务暂不可用"})
        )
        with make_client() as client:
            with pytest.raises(BusinessError) as exc_info:
                client.tap(1, 2)
            assert exc_info.value.code == 503
