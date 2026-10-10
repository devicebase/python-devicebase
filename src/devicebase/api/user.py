"""The account itself — ``GET /v1/user/info`` and ``POST /v1/user/checkin``.

The third account-level group, next to
:class:`~devicebase.api.device.DeviceApi` and
:class:`~devicebase.api.cloud_browser.CloudBrowserApi`: none of them addresses a
device, so none takes a serialno. This one answers "whose key is this, and what
does the account have" — the name, phone, points balance and registration date,
plus the daily check-in that earns more points.

Only ever your own account: the API key decides whose record this is, and there
is no argument for pointing it at somebody else.

The contract lives in ``devicebase-ts/openapi/src/api/routes/user.ts``; the
console carries the same two capabilities behind session auth.
"""

from __future__ import annotations

from typing import Any

from devicebase.models import UserCheckin, UserInfo
from devicebase.transport import HttpTransport


def _data_object(data: dict[str, Any]) -> dict[str, Any]:
    """The ``data`` object of an envelope, or an empty mapping."""
    inner = data.get("data")
    if not isinstance(inner, dict):
        return {}
    return inner


class UserApi(HttpTransport):
    """The account behind the API key, none of it addressing a device."""

    def user_info(self) -> UserInfo:
        """Return the account behind the API key.

        The name (``username``), phone (``mobile``), points balance
        (``credits``), registration time and ``can_checkin`` — whether today's
        reward is still unclaimed.

        Returns:
            The account record.

        Raises:
            AuthenticationError: If the key is missing or unrecognised.
            DeviceNotFoundError: If the key is valid but its account is gone.
        """
        data = self.request_json("GET", "/v1/user/info")
        return UserInfo.from_dict(_data_object(data))

    def user_checkin(self) -> UserCheckin:
        """Claim the daily points: 25 on the first day, +10 per consecutive
        day, up to 95 a day.

        Claiming twice in one day is **not** an error — the second call returns
        ``already_checked`` true and grants nothing. That is deliberate: it
        makes this call safe to put in a daily scheduled task that may fire
        more than once, without the task having to ask ``can_checkin`` first.

        An empty JSON object is sent rather than no body at all: the call has
        no parameters either way, and ``{}`` is what a deployment predating the
        server's body-less-POST tolerance also accepts.

        Returns:
            The claim result: points earned, streak, and the platform's own
            ``message`` for display.

        Raises:
            DeviceBaseError: If the request fails.
        """
        data = self.request_json("POST", "/v1/user/checkin", body={})
        return UserCheckin.from_dict(_data_object(data))
