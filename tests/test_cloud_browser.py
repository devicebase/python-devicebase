"""The cloud browser lifecycle — create, delete, status, quota.

A different surface from the device actions in ``test_api.py``: these live on
``/v1/browser/*``, none of them addresses an existing device, and the status
codes carry meaning a caller branches on (409 = retrying will not help, 503 =
retry later). Reference: ``devicebase-ts/openapi/src/api/routes/browser.ts``.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from devicebase import (
    CloudBrowserCreateResult,
    CloudBrowserQuota,
    CloudBrowserStatus,
    DeviceBaseError,
    DeviceBaseHttpClient,
    ValidationError,
)

BASE_URL = "http://api.test"


def make_client() -> DeviceBaseHttpClient:
    return DeviceBaseHttpClient(base_url=BASE_URL, api_key="test-key")


@respx.mock
def test_create_sends_only_the_fields_it_was_given() -> None:
    """A field left out stays out: the driver tells false from absent."""
    route = respx.post(f"{BASE_URL}/v1/browser/create").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "message": "success",
                "data": {
                    "serialno": "db-mtabc123",
                    "device_sn": "3f2a",
                    "name": "Browser-3f2a1b4c",
                    "alias_name": "my-browser",
                    "registered": True,
                },
            },
        ),
    )

    with make_client() as client:
        result = client.cloud_browser_create()

    assert route.calls.last.request.content == b"{}"
    assert result == CloudBrowserCreateResult(
        serialno="db-mtabc123",
        device_sn="3f2a",
        # name 是平台的内部身份名；调用方要的是 alias_name（原样、无端口后缀）
        name="Browser-3f2a1b4c",
        alias_name="my-browser",
        registered=True,
    )


@respx.mock
def test_create_forwards_every_field_under_the_wire_names() -> None:
    route = respx.post(f"{BASE_URL}/v1/browser/create").mock(
        return_value=httpx.Response(200, json={"code": 200, "data": {}}),
    )

    with make_client() as client:
        client.cloud_browser_create(name="  my-browser  ", window_size="1366x768", wait_seconds=30)

    assert route.calls.last.request.content == (
        b'{"name":"my-browser","window_size":"1366x768","wait_seconds":30}'
    )


@respx.mock
def test_create_never_sends_a_headless_mode() -> None:
    """A cloud browser is always headless — the field must not exist at all."""
    route = respx.post(f"{BASE_URL}/v1/browser/create").mock(
        return_value=httpx.Response(200, json={"code": 200, "data": {}}),
    )

    with make_client() as client:
        client.cloud_browser_create(name="b")

    assert b"headless" not in route.calls.last.request.content


def test_create_rejects_bad_arguments_before_any_request() -> None:
    """Local validation: a rejected create never reaches placement."""
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(f"{BASE_URL}/v1/browser/create").mock(
            return_value=httpx.Response(200, json={"code": 200, "data": {}}),
        )
        with make_client() as client:
            with pytest.raises(ValidationError, match="name cannot be empty"):
                client.cloud_browser_create(name="   ")
            with pytest.raises(ValidationError, match="name is longer than 100"):
                client.cloud_browser_create(name="x" * 101)
            with pytest.raises(ValidationError, match="must look like 1366x768"):
                client.cloud_browser_create(window_size="1366*768")
            with pytest.raises(ValidationError, match="wait_seconds must be between 0 and 60"):
                client.cloud_browser_create(wait_seconds=61)
        assert not route.called


@respx.mock
def test_delete_uses_the_identifier_and_escapes_it() -> None:
    route = respx.delete(url__regex=rf"{BASE_URL}/v1/browser/.*").mock(
        return_value=httpx.Response(200, json={"code": 200, "message": "success", "data": None}),
    )

    with make_client() as client:
        client.cloud_browser_delete("db-mtabc123")

    request = route.calls.last.request
    assert request.method == "DELETE"
    assert request.url.path == "/v1/browser/db-mtabc123"


@respx.mock
def test_delete_escapes_an_awkward_identifier() -> None:
    """The identifier is caller-supplied, so it cannot be pasted into a path raw."""
    route = respx.delete(url__regex=rf"{BASE_URL}/v1/browser/.*").mock(
        return_value=httpx.Response(200, json={"code": 200, "data": None}),
    )

    with make_client() as client:
        client.cloud_browser_delete("a b/c")

    assert str(route.calls.last.request.url) == f"{BASE_URL}/v1/browser/a%20b%2Fc"


def test_delete_rejects_a_blank_identifier() -> None:
    with (
        make_client() as client,
        pytest.raises(ValidationError, match="identifier cannot be empty"),
    ):
        client.cloud_browser_delete("  ")


@respx.mock
def test_create_reports_not_yet_registered_as_a_success() -> None:
    """A wait that runs out is not a failure — the browser is still starting."""
    respx.post(f"{BASE_URL}/v1/browser/create").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "device_sn": "3f2a",
                    "serialno": None,
                    "name": "Chrome-3f2a",
                    "registered": False,
                },
            },
        ),
    )

    with make_client() as client:
        result = client.cloud_browser_create(wait_seconds=0)

    assert result.registered is False
    assert result.serialno == ""
    # device_sn is still a usable handle for status and delete
    assert result.device_sn == "3f2a"


@respx.mock
def test_status_reports_not_yet_registered_as_a_normal_answer() -> None:
    """Polling must be quiet — "not up yet" is a value, never an exception."""
    respx.get(f"{BASE_URL}/v1/browser/3f2a/status").mock(
        return_value=httpx.Response(200, json={"code": 200, "data": {"registered": False}}),
    )

    with make_client() as client:
        status = client.cloud_browser_status("3f2a")

    assert status.registered is False
    assert status.serialno == ""


@respx.mock
def test_status_returns_the_registered_device() -> None:
    respx.get(f"{BASE_URL}/v1/browser/3f2a/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "registered": True,
                    "device_id": 42,
                    "serialno": "db-mtabc123",
                    "name": "Chrome-3f2a",
                    "state": "free",
                    "server_url": "relay.uusense.com",
                    "is_cloud": True,
                },
            },
        ),
    )

    with make_client() as client:
        status = client.cloud_browser_status("3f2a")

    assert status == CloudBrowserStatus(
        registered=True,
        device_id=42,
        serialno="db-mtabc123",
        name="Chrome-3f2a",
        state="free",
        server_url="relay.uusense.com",
        is_cloud=True,
    )


@respx.mock
def test_quota_decodes_the_three_numbers() -> None:
    respx.get(f"{BASE_URL}/v1/browser/quota").mock(
        return_value=httpx.Response(
            200,
            json={"code": 200, "data": {"limit": 10, "used": 3, "remaining": 7}},
        ),
    )

    with make_client() as client:
        assert client.cloud_browser_quota() == CloudBrowserQuota(limit=10, used=3, remaining=7)


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (409, {"code": 409, "message": "你的浏览器数量已达上限（10 台）。", "trace_id": "t"}),
        (
            502,
            {
                "code": 502,
                "message": "平台与云节点之间的鉴权没有通过，请联系平台处理。",
                "trace_id": "t",
            },
        ),
        (503, {"code": 503, "message": "当前没有可用的集群节点，请稍后重试", "trace_id": "t"}),
    ],
)
@respx.mock
def test_conflicts_surface_with_their_status_code(status: int, body: dict[str, Any]) -> None:
    """Which retry is worth it is decided by the status code, so it must survive."""
    respx.post(f"{BASE_URL}/v1/browser/create").mock(
        return_value=httpx.Response(status, json=body),
    )

    with make_client() as client, pytest.raises(DeviceBaseError) as exc_info:
        client.cloud_browser_create()

    assert exc_info.value.status_code == status
    assert body["message"] in str(exc_info.value)


@respx.mock
def test_delete_of_someone_elses_browser_is_a_not_found() -> None:
    respx.delete(f"{BASE_URL}/v1/browser/db-other").mock(
        return_value=httpx.Response(
            404, json={"code": 404, "message": "设备不存在", "trace_id": "t"}
        ),
    )

    with make_client() as client, pytest.raises(DeviceBaseError) as exc_info:
        client.cloud_browser_delete("db-other")

    assert exc_info.value.status_code == 404
