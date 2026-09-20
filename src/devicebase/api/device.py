"""Device discovery — ``GET /v1/devices``.

This is how a ``serialno`` is found before any other call: every platform method
needs one, and nothing else in the API hands them out.

Filtering is resolved server-side, and the ``type`` value is forwarded verbatim.
It accepts either a **category** (``mobile`` / ``browser`` / ``computer``) or a
**system type** (``android`` / ``harmonyos`` / ``ios`` / ``macos`` / ``windows``
/ ``linux`` / ``chrome`` / ``chromium`` / ``edge`` / ``other``). A system type
resolves against a device's ``os_type``, because a device row only carries the
coarse ``type`` — a Chrome browser is ``type=browser`` with ``os_type=Chrome``.
"""

from __future__ import annotations

from typing import Any

from devicebase.models import Device
from devicebase.transport import HttpTransport, reject


class DeviceApi(HttpTransport):
    """Device listing."""

    def list_devices(
        self,
        keyword: str | None = None,
        state: str | None = None,
        device_type: str | None = None,
        limit: int | None = None,
    ) -> list[Device]:
        """List the devices accessible to the current API key.

        Args:
            keyword: Free-text match against the device name and serialno.
            state: Connection state — ``"busy"``, ``"free"`` or ``"offline"``.
            device_type: A category (``mobile`` / ``browser`` / ``computer``) or
                a system type — see the module docstring. Named
                ``device_type`` because it becomes the ``type`` query parameter.
            limit: Cap on the number of rows. Omitted, the server applies its
                own default (10, clamped to 1-100).

        Returns:
            The device rows. The response carries no pagination metadata, so
            ``limit`` is the only bound on the result size.

        Raises:
            ValidationError: If ``limit`` is not positive. Raised locally,
                before any request. Go omits a non-positive limit instead and
                Node sends it — this SDK rejects it, because 0 is clamped
                server-side in a way the caller did not ask for.
        """
        if limit is not None and limit <= 0:
            raise reject(f"limit must be greater than 0, got {limit}")

        params: dict[str, Any] = {
            "keyword": keyword,
            "state": state,
            "type": device_type,
            "limit": limit,
        }
        data = self.request_json("GET", "/v1/devices", params=params)

        rows = data.get("data")
        if not isinstance(rows, list):
            return []
        return [Device.from_dict(row) for row in rows if isinstance(row, dict)]
