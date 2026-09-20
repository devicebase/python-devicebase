"""Tests for the transport: envelope inspection, error mapping, deadlines."""

import json
import os
from unittest.mock import patch

import httpx
import pytest
import respx

from devicebase.api import BrowserApi, ComputerApi, DeviceApi, MobileApi
from devicebase.api.computer import bash_timeout, wait_timeout
from devicebase.errors import (
    AuthenticationError,
    BusinessError,
    DeviceBaseError,
    DeviceNotFoundError,
    ValidationError,
    truncate,
)
from devicebase.http_client import DeviceBaseHttpClient
from devicebase.models import Point
from devicebase.transport import (
    DEFAULT_BASH_TIMEOUT_SECONDS,
    ENVELOPE_SNIFF_BYTES,
    check_envelope,
    error_for_status,
    escape_path_segment,
    sniff_json_prefix,
)

BASE_URL = "http://api.test"
SERIAL = "dev-1"


def make_client(**kwargs: object) -> DeviceBaseHttpClient:
    """Build a client pointed at the fake API host."""
    return DeviceBaseHttpClient(base_url=BASE_URL, api_key="test-key", **kwargs)  # type: ignore[arg-type]


class TestInit:
    """Client construction and credential resolution."""

    def test_explicit_params(self) -> None:
        client = make_client()
        assert client._base_url == BASE_URL
        assert client._api_key == "test-key"
        client.close()

    def test_trailing_slash_is_trimmed(self) -> None:
        client = DeviceBaseHttpClient(base_url=f"{BASE_URL}/", api_key="k")
        assert client._base_url == BASE_URL
        client.close()

    def test_env_vars(self) -> None:
        with patch.dict(
            os.environ,
            {"DEVICEBASE_BASE_URL": BASE_URL, "DEVICEBASE_API_KEY": "env-key"},
        ):
            client = DeviceBaseHttpClient()
            assert client._base_url == BASE_URL
            assert client._api_key == "env-key"
            client.close()

    def test_default_base_url(self) -> None:
        with patch.dict(os.environ, {"DEVICEBASE_API_KEY": "k"}, clear=True):
            client = DeviceBaseHttpClient()
            assert client._base_url == "https://api.devicebase.cn"
            client.close()

    def test_missing_api_key_raises(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AuthenticationError) as exc_info:
                DeviceBaseHttpClient(base_url=BASE_URL)
            assert "API key is required" in str(exc_info.value)

    def test_context_manager_closes(self) -> None:
        with make_client() as client:
            assert isinstance(client, DeviceBaseHttpClient)


class TestErrorForStatus:
    """Each HTTP status maps onto the matching error class."""

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (401, AuthenticationError),
            (404, DeviceNotFoundError),
            (400, ValidationError),
            (422, ValidationError),
            (500, DeviceBaseError),
            (503, DeviceBaseError),
        ],
    )
    def test_mapping(self, status: int, expected: type[DeviceBaseError]) -> None:
        error = error_for_status(status, "boom")
        assert type(error) is expected
        assert error.status_code == status
        assert f"HTTP {status}" in error.message

    @respx.mock
    def test_server_message_is_preserved(self) -> None:
        respx.post(f"{BASE_URL}/v1/tap/{SERIAL}").mock(
            return_value=httpx.Response(404, text="设备不存在: dev-1")
        )
        with make_client() as client:
            with pytest.raises(DeviceNotFoundError) as exc_info:
                client.tap(SERIAL, Point(x=1, y=2))
            assert "设备不存在" in str(exc_info.value)
            assert exc_info.value.status_code == 404

    @respx.mock
    def test_empty_body_falls_back_to_reason_phrase(self) -> None:
        respx.post(f"{BASE_URL}/v1/tap/{SERIAL}").mock(return_value=httpx.Response(500, text=""))
        with make_client() as client:
            with pytest.raises(DeviceBaseError) as exc_info:
                client.tap(SERIAL, Point(x=1, y=2))
            assert "Internal Server Error" in str(exc_info.value)

    @respx.mock
    def test_unauthorized(self) -> None:
        respx.get(f"{BASE_URL}/v1/devices").mock(
            return_value=httpx.Response(401, json={"message": "invalid key"})
        )
        with make_client() as client, pytest.raises(AuthenticationError):
            client.list_devices()


class TestEnvelope:
    """The second failure layer: HTTP 200 carrying a non-2xx code."""

    @pytest.mark.parametrize(
        "code",
        [300, 400, 404, 500, 502, 503, -1],
    )
    def test_non_2xx_code_raises(self, code: int) -> None:
        with pytest.raises(BusinessError) as exc_info:
            check_envelope(json.dumps({"code": code, "message": "nope"}))
        assert exc_info.value.code == code
        assert exc_info.value.status_code is None

    @pytest.mark.parametrize("code", [200, 201, 204, 299])
    def test_2xx_code_passes(self, code: int) -> None:
        check_envelope(json.dumps({"code": code, "data": {}}))

    @pytest.mark.parametrize(
        "body",
        [
            "",
            "   ",
            "not json",
            "[]",
            "[1, 2, 3]",
            '{"data": {}}',
            '{"code": "200"}',
            '{"code": null}',
            '{"code": true}',
            '{"code": 200.5}',
            # Starts like an envelope but is not valid JSON — a truncated body,
            # say. It must not be mistaken for a failure code.
            '{"code": 502,',
            "{not json at all}",
        ],
    )
    def test_non_envelopes_are_left_alone(self, body: str) -> None:
        check_envelope(body)

    @respx.mock
    def test_business_error_from_a_200(self) -> None:
        respx.post(f"{BASE_URL}/api/browser/{SERIAL}/click").mock(
            return_value=httpx.Response(
                200,
                json={"code": 502, "message": "-32602: Invalid parameters"},
            )
        )
        with make_client() as client:
            with pytest.raises(BusinessError) as exc_info:
                client.browser_click(SERIAL, "#missing")
            assert exc_info.value.code == 502
            assert exc_info.value.body == ('{"code":502,"message":"-32602: Invalid parameters"}')
            assert "code 502" in str(exc_info.value)

    @respx.mock
    def test_business_error_beats_the_status_check(self) -> None:
        """A 200 with a failing envelope must not be reported as success."""
        respx.post(f"{BASE_URL}/v1/tap/{SERIAL}").mock(
            return_value=httpx.Response(200, json={"code": 503, "message": "offline"})
        )
        with make_client() as client, pytest.raises(BusinessError):
            client.tap(SERIAL, Point(x=1, y=2))


class TestBinaryEnvelope:
    """request_bytes sniffs the envelope without decoding an image."""

    @respx.mock
    def test_json_error_is_not_returned_as_image_data(self) -> None:
        respx.post(f"{BASE_URL}/v1/screen/{SERIAL}").mock(
            return_value=httpx.Response(200, json={"code": 503, "message": "offline"})
        )
        with make_client() as client:
            with pytest.raises(BusinessError) as exc_info:
                client.get_screenshot(SERIAL)
            assert exc_info.value.code == 503

    @respx.mock
    def test_image_bytes_pass_through(self) -> None:
        jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 64
        respx.post(f"{BASE_URL}/v1/screen/{SERIAL}").mock(
            return_value=httpx.Response(200, content=jpeg)
        )
        with make_client() as client:
            assert client.get_screenshot(SERIAL) == jpeg

    def test_sniff_rejects_oversized_and_binary_bodies(self) -> None:
        assert sniff_json_prefix(b"") == ""
        # A JPEG magic number: the common case this guard exists for.
        assert sniff_json_prefix(b"\xff\xd8\xff\xe0") == ""
        assert sniff_json_prefix(b"[]") == ""
        assert sniff_json_prefix(b'  {"code": 502}') != ""
        huge = b"{" + b" " * ENVELOPE_SNIFF_BYTES
        assert sniff_json_prefix(huge) == ""

    def test_sniff_rejects_a_binary_body_that_starts_like_json(self) -> None:
        # Leading "{" then bytes that are not UTF-8: decoding would raise, and
        # the body must be treated as binary rather than crashing the read.
        assert sniff_json_prefix(b"{\xff\xfe\x00binary") == ""

    @respx.mock
    def test_http_error_on_a_binary_route(self) -> None:
        # The cross-family screen route answers a failure with a plain status
        # rather than an envelope, unlike the JSON actions.
        respx.post(f"{BASE_URL}/v1/screen/{SERIAL}").mock(
            return_value=httpx.Response(503, json={"error": "device offline"})
        )
        with make_client() as client:
            with pytest.raises(DeviceBaseError) as exc_info:
                client.get_screenshot(SERIAL)
            assert exc_info.value.status_code == 503
            assert "device offline" in str(exc_info.value)


class TestTimeouts:
    """Blocking actions widen the deadline; ordinary ones do not."""

    def test_bash_timeout_uses_the_server_default_when_unset(self) -> None:
        assert bash_timeout(0) == DEFAULT_BASH_TIMEOUT_SECONDS + 15
        assert bash_timeout(-5) == DEFAULT_BASH_TIMEOUT_SECONDS + 15

    def test_bash_timeout_covers_the_requested_budget(self) -> None:
        assert bash_timeout(300) == 315
        assert bash_timeout(300) > 300

    def test_wait_timeout_uses_milliseconds(self) -> None:
        assert wait_timeout(60_000) == 75.0
        assert wait_timeout(-100) == 15.0

    @respx.mock
    def test_wait_widens_the_request_deadline(self) -> None:
        route = respx.post(f"{BASE_URL}/api/computer/{SERIAL}/wait").mock(
            return_value=httpx.Response(200, json={"code": 200, "data": {}})
        )
        with make_client() as client:
            client.computer_wait(SERIAL, 90_000)
        assert _timeout_of(route) == 105.0

    @respx.mock
    def test_bash_widens_the_request_deadline(self) -> None:
        route = respx.post(f"{BASE_URL}/api/computer/{SERIAL}/bash").mock(
            return_value=httpx.Response(200, json={"code": 200, "data": {}})
        )
        with make_client() as client:
            client.computer_bash(SERIAL, "sleep 60", timeout_seconds=60)
        assert _timeout_of(route) == 75.0

    @respx.mock
    def test_ordinary_actions_keep_the_default(self) -> None:
        route = respx.post(f"{BASE_URL}/v1/tap/{SERIAL}").mock(
            return_value=httpx.Response(200, json={"code": 200, "data": {}})
        )
        with make_client() as client:
            client.tap(SERIAL, Point(x=1, y=2))
        assert _timeout_of(route) == 30.0


class TestParamHandling:
    """Query values are escaped and unset ones are dropped."""

    @respx.mock
    def test_serial_is_url_escaped(self) -> None:
        route = respx.get(f"{BASE_URL}/api/browser/a%2Fb%20c/state").mock(
            return_value=httpx.Response(200, json={"code": 200, "data": {}})
        )
        with make_client() as client:
            client.browser_state("a/b c")
        assert route.called
        # raw_path is bytes, and undecoded — which is the point: an unescaped
        # serial would change the route rather than just the value.
        assert route.calls.last.request.url.raw_path == b"/api/browser/a%2Fb%20c/state"

    @respx.mock
    def test_selector_is_escaped_and_sent_as_a_query_param(self) -> None:
        route = respx.get(f"{BASE_URL}/api/browser/{SERIAL}/text").mock(
            return_value=httpx.Response(200, json={"code": 200, "data": {}})
        )
        with make_client() as client:
            client.browser_text(SERIAL, 'div[data-x="a b"]')
        params = route.calls.last.request.url.params
        assert params["selector"] == 'div[data-x="a b"]'

    @respx.mock
    def test_unset_filters_are_dropped_from_the_device_list(self) -> None:
        route = respx.get(f"{BASE_URL}/v1/devices").mock(
            return_value=httpx.Response(200, json={"code": 200, "data": []})
        )
        with make_client() as client:
            client.list_devices()
        assert route.calls.last.request.url.query == b""

    @respx.mock
    def test_limit_is_rendered_as_a_number(self) -> None:
        route = respx.get(f"{BASE_URL}/v1/devices").mock(
            return_value=httpx.Response(200, json={"code": 200, "data": []})
        )
        with make_client() as client:
            client.list_devices(limit=5)
        assert route.calls.last.request.url.params["limit"] == "5"

    def test_escape_path_segment(self) -> None:
        assert escape_path_segment("a/b") == "a%2Fb"
        assert escape_path_segment("db-mttul4i41di8") == "db-mttul4i41di8"


class TestBadResponses:
    """A body that is not JSON at all is reported, not swallowed."""

    @respx.mock
    def test_invalid_json(self) -> None:
        respx.post(f"{BASE_URL}/v1/tap/{SERIAL}").mock(
            return_value=httpx.Response(200, text="<html>oops</html>")
        )
        with make_client() as client:
            with pytest.raises(DeviceBaseError) as exc_info:
                client.tap(SERIAL, Point(x=1, y=2))
            assert "Invalid JSON response" in str(exc_info.value)

    @respx.mock
    def test_empty_body_decodes_to_an_empty_mapping(self) -> None:
        respx.post(f"{BASE_URL}/v1/back/{SERIAL}").mock(return_value=httpx.Response(204))
        with make_client() as client:
            result = client.back(SERIAL)
        assert result.success is True
        assert result.data == {}

    @respx.mock
    def test_a_bare_list_is_wrapped(self) -> None:
        respx.get(f"{BASE_URL}/v1/devices").mock(
            return_value=httpx.Response(200, json=[{"serial": "a"}])
        )
        with make_client() as client:
            devices = client.list_devices()
        assert [d.serial for d in devices] == ["a"]


class TestTruncate:
    """Error bodies are bounded."""

    def test_short_body_untouched(self) -> None:
        assert truncate("short") == "short"

    def test_long_body_truncated(self) -> None:
        result = truncate("x" * 5000)
        assert result.endswith("… (truncated)")
        assert len(result) < 5000


def _timeout_of(route: respx.Route) -> float | None:
    """Read the deadline httpx recorded for a request."""
    timeout = route.calls.last.request.extensions.get("timeout")
    if not isinstance(timeout, dict):
        return None
    connect = timeout.get("connect")
    return float(connect) if isinstance(connect, (int, float)) else None


class TestRedirects:
    """A redirect body is never the action's result."""

    @respx.mock
    def test_a_followed_redirect_returns_the_final_body(self) -> None:
        respx.post(f"{BASE_URL}/v1/tap/{SERIAL}").mock(
            return_value=httpx.Response(307, headers={"Location": f"{BASE_URL}/api/tap/{SERIAL}"})
        )
        respx.post(f"{BASE_URL}/api/tap/{SERIAL}").mock(
            return_value=httpx.Response(200, json={"code": 200, "data": {"ok": True}})
        )
        with make_client() as client:
            result = client.tap(SERIAL, Point(x=1, y=2))
        assert result.payload == {"ok": True}

    @respx.mock
    def test_an_unfollowed_redirect_raises(self) -> None:
        # A redirect the client did not follow must not be decoded as the
        # action's result — that would report an action that never ran as a
        # success. 300 is not followed by any client.
        respx.post(f"{BASE_URL}/v1/tap/{SERIAL}").mock(
            return_value=httpx.Response(300, headers={"Location": "/api/tap/x"}, json={"code": 200})
        )
        with make_client() as client:
            with pytest.raises(DeviceBaseError) as exc_info:
                client.tap(SERIAL, Point(x=1, y=2))
            assert exc_info.value.status_code == 300

    @respx.mock
    def test_a_redirect_is_not_returned_as_image_data(self) -> None:
        respx.post(f"{BASE_URL}/v1/screen/{SERIAL}").mock(
            return_value=httpx.Response(300, headers={"Location": "/x"})
        )
        with make_client() as client, pytest.raises(DeviceBaseError):
            client.get_screenshot(SERIAL)


class TestTransportErrors:
    """A request that never completed still raises the SDK's own error."""

    @respx.mock
    def test_a_timeout_is_wrapped(self) -> None:
        respx.post(f"{BASE_URL}/v1/tap/{SERIAL}").mock(side_effect=httpx.ReadTimeout("slow"))
        with make_client() as client:
            with pytest.raises(DeviceBaseError) as exc_info:
                client.tap(SERIAL, Point(x=1, y=2))
            assert "Request failed" in str(exc_info.value)
            assert exc_info.value.status_code is None

    @respx.mock
    def test_a_connection_failure_is_wrapped(self) -> None:
        respx.post(f"{BASE_URL}/v1/tap/{SERIAL}").mock(side_effect=httpx.ConnectError("refused"))
        with (
            make_client() as client,
            pytest.raises(DeviceBaseError, match="Request failed"),
        ):
            client.tap(SERIAL, Point(x=1, y=2))

    @respx.mock
    def test_the_original_exception_is_chained(self) -> None:
        respx.post(f"{BASE_URL}/v1/tap/{SERIAL}").mock(side_effect=httpx.ReadTimeout("slow"))
        with make_client() as client:
            with pytest.raises(DeviceBaseError) as exc_info:
                client.tap(SERIAL, Point(x=1, y=2))
            assert isinstance(exc_info.value.__cause__, httpx.HTTPError)


class TestBackwardCompatibleSurface:
    """Names earlier releases exposed are still reachable."""

    def test_default_base_url_is_a_class_attribute(self) -> None:
        assert DeviceBaseHttpClient.DEFAULT_BASE_URL == "https://api.devicebase.cn"
        assert make_client().DEFAULT_BASE_URL == "https://api.devicebase.cn"

    def test_authentication_error_is_importable_from_http_client(self) -> None:
        from devicebase.http_client import AuthenticationError as FromHttpClient

        assert FromHttpClient is AuthenticationError


class TestMixinComposition:
    """The four platform mixins must not collide through the MRO."""

    def test_no_platform_method_is_defined_twice(self) -> None:
        # DeviceBaseHttpClient is BrowserApi -> ComputerApi -> DeviceApi ->
        # MobileApi -> HttpTransport. A name defined on two mixins would be
        # silently shadowed by whichever comes first, with no test failing.
        mixins = [BrowserApi, ComputerApi, DeviceApi, MobileApi]
        seen: dict[str, str] = {}
        for mixin in mixins:
            for name in vars(mixin):
                if name.startswith("__"):
                    continue
                assert name not in seen, (
                    f"{name!r} is defined on both {seen[name]} and {mixin.__name__}; "
                    "the one earlier in the MRO would silently win"
                )
                seen[name] = mixin.__name__

    def test_every_mixin_contributes_methods(self) -> None:
        for mixin in (BrowserApi, ComputerApi, DeviceApi, MobileApi):
            assert any(not n.startswith("_") for n in vars(mixin)), mixin.__name__

    def test_the_client_reaches_all_four_mixins(self) -> None:
        assert issubclass(DeviceBaseHttpClient, (BrowserApi, ComputerApi, DeviceApi, MobileApi))
