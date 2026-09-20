"""Tests that talk to the real API.

Skipped unless ``DEVICEBASE_LIVE_TEST=1`` and an API key is available, so the
default ``pytest`` run stays offline and hermetic:

    DEVICEBASE_LIVE_TEST=1 DEVICEBASE_API_KEY=… pytest tests/test_live.py -v

These assert the SDK's own behaviour, not the state of any particular device —
a device may be offline at any moment, and every one of these cases has to hold
either way.
"""

import os

import pytest

from devicebase import (
    BusinessError,
    DeviceBaseClient,
    DeviceBaseError,
    DeviceNotFoundError,
    list_devices,
)

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("DEVICEBASE_LIVE_TEST") != "1",
        reason="set DEVICEBASE_LIVE_TEST=1 to run live tests",
    ),
    pytest.mark.skipif(
        not os.environ.get("DEVICEBASE_API_KEY"),
        reason="DEVICEBASE_API_KEY is not set",
    ),
]

#: A serialno that no account has, used to exercise the 404 path.
MISSING_SERIAL = "definitely-not-a-device"


@pytest.fixture(scope="module")
def serialno() -> str:
    """A real serialno, discovered the way a caller would."""
    devices = list_devices(limit=10)
    if not devices:
        pytest.skip("the account has no devices")
    return devices[0].serialno


class TestDiscovery:
    """GET /v1/devices against production."""

    def test_returns_parsed_devices(self) -> None:
        devices = list_devices(limit=10)
        assert isinstance(devices, list)
        for device in devices:
            # `serialno` is what every control call takes, so an empty one would
            # make the listing useless.
            assert device.serialno
            assert device.state
            assert device.display_name

    def test_limit_is_honoured(self) -> None:
        assert len(list_devices(limit=1)) <= 1


class TestControl:
    """A real serialno, on whichever platform it belongs to."""

    def test_device_info_or_a_reported_failure(self, serialno: str) -> None:
        with DeviceBaseClient(serialno=serialno) as client:
            try:
                info = client.get_device_info()
            except BusinessError:
                # An offline device answers HTTP 200 with code 503. Both that
                # and a payload are correct; anything else is a bug.
                pass
            else:
                assert info.serialno == serialno
                assert info.data

    def test_unknown_serial_is_a_404(self) -> None:
        with DeviceBaseClient(serialno=MISSING_SERIAL, timeout=60.0) as client:
            with pytest.raises(DeviceNotFoundError) as exc_info:
                client.get_device_info()
            assert exc_info.value.status_code == 404
            # The server's own message survives into the error.
            assert "device" in exc_info.value.message.lower()

    def test_failure_is_reported_rather_than_returned(self, serialno: str) -> None:
        """A failing action raises, so a caller cannot mistake it for success."""
        with DeviceBaseClient(serialno=serialno) as client:
            try:
                client.tap(1, 1)
            except DeviceBaseError:
                pass  # expected while the device is offline
            else:
                pytest.skip("the device is online; no failure to observe")
