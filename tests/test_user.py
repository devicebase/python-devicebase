"""The account surface — ``GET /v1/user/info`` and ``POST /v1/user/checkin``.

Like the cloud browser lifecycle in ``test_cloud_browser.py``, none of these
addresses a device; unlike it, they take no arguments at all — the API key
decides whose account this is. Reference:
``devicebase-ts/openapi/src/api/routes/user.ts``.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from devicebase import (
    AuthenticationError,
    DeviceBaseHttpClient,
    UserCheckin,
    UserInfo,
)

BASE_URL = "http://api.test"


def make_client() -> DeviceBaseHttpClient:
    return DeviceBaseHttpClient(base_url=BASE_URL, api_key="test-key")


@respx.mock
def test_info_reads_the_account_with_no_arguments() -> None:
    route = respx.get(f"{BASE_URL}/v1/user/info").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "message": "success",
                "data": {
                    "id": 42,
                    "username": "richie",
                    "mobile": "13800138000",
                    "credits": 1259,
                    "registered_at": "2026-01-02T03:04:05",
                    "can_checkin": True,
                },
            },
        ),
    )

    with make_client() as client:
        info = client.user_info()

    assert route.calls.last.request.content == b""
    assert info == UserInfo(
        id=42,
        username="richie",
        mobile="13800138000",
        credits=1259,
        registered_at="2026-01-02T03:04:05",
        can_checkin=True,
    )


@respx.mock
def test_checkin_posts_an_empty_object() -> None:
    """空对象而不是没有请求体：签到没有参数，而 {} 在还没有「空体容忍」的部署上也照样被接受。"""
    route = respx.post(f"{BASE_URL}/v1/user/checkin").mock(
        return_value=httpx.Response(200, json={"code": 200, "data": {}}),
    )

    with make_client() as client:
        client.user_checkin()

    assert route.calls.last.request.content == b"{}"


@respx.mock
def test_checkin_decodes_the_reward() -> None:
    respx.post(f"{BASE_URL}/v1/user/checkin").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "success": True,
                    "credits_earned": 35,
                    "consecutive_days": 2,
                    "already_checked": False,
                    "message": "签到成功！获得35积分",
                    "credits": 1294,
                },
            },
        ),
    )

    with make_client() as client:
        reward = client.user_checkin()

    assert reward == UserCheckin(
        success=True,
        credits_earned=35,
        consecutive_days=2,
        already_checked=False,
        message="签到成功！获得35积分",
        credits=1294,
    )


@respx.mock
def test_already_checked_is_a_normal_answer_not_an_error() -> None:
    """「已领过」是正常回答：每日定时任务可以无脑重复执行它。"""
    respx.post(f"{BASE_URL}/v1/user/checkin").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "success": False,
                    "credits_earned": 0,
                    "consecutive_days": 2,
                    "already_checked": True,
                    "message": "今日已签到",
                    "credits": 1294,
                },
            },
        ),
    )

    with make_client() as client:
        reward = client.user_checkin()

    assert reward.already_checked is True
    assert reward.success is False
    assert reward.credits_earned == 0
    assert reward.message == "今日已签到"
    assert reward.credits == 1294


@respx.mock
def test_missing_key_surfaces_as_authentication_error() -> None:
    respx.get(f"{BASE_URL}/v1/user/info").mock(
        return_value=httpx.Response(
            401,
            json={"code": 401, "message": "缺少 API Key", "trace_id": "t"},
        ),
    )

    with make_client() as client, pytest.raises(AuthenticationError) as exc_info:
        client.user_info()

    assert exc_info.value.status_code == 401
