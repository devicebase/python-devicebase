"""A serialno-bound facade over the HTTP client, for one device.

Every mobile action here fills in the serialno, so an Android / HarmonyOS / iOS
automation script never repeats it. The facade is platform-agnostic about the
serialno it holds — binding a browser or computer serialno works exactly as
well — but the *browser* and *computer* action families stay on
:class:`~devicebase.http_client.DeviceBaseHttpClient`, reached through
:attr:`DeviceBaseClient.http`, because those actions all take a serialno per
call and one client is meant to drive many devices.
"""

from __future__ import annotations

import os
import warnings
from collections.abc import AsyncIterator
from typing import Any

# AuthenticationError is re-exported: earlier versions of this module raised it
# from here, so `from devicebase.client import AuthenticationError` has to keep
# working.
from devicebase.errors import (  # noqa: F401
    AuthenticationError,
    DeviceBaseError,
    ValidationError,
)
from devicebase.http_client import DeviceBaseHttpClient
from devicebase.models import (
    AppInfo,
    Bounds,
    Device,
    DeviceInfo,
    HierarchyInfo,
    OperationResult,
    Point,
)
from devicebase.transport import DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from devicebase.websocket_client import MinicapClient, MinitouchClient


class DeviceBaseClient:
    """A serialno-bound view of the API for one device.

    Configuration can come from constructor arguments or the environment:

    * ``DEVICEBASE_BASE_URL`` — API base URL (default ``https://api.devicebase.cn``)
    * ``DEVICEBASE_API_KEY`` — Bearer token

    Example:
        ```python
        from devicebase import DeviceBaseClient, Point

        with DeviceBaseClient(serialno="db-mttul4i41di8") as client:
            client.tap(100, 200)
            client.swipe(0, 500, 500, 500)
            client.launch_app("com.example.app")
            open("screen.jpg", "wb").write(client.get_screenshot())
        ```

    Args:
        serialno: The device serialno from
            :meth:`~devicebase.api.device.DeviceApi.list_devices`. Optional so
            that discovery works before any device is known; the mobile actions
            raise :class:`~devicebase.errors.DeviceBaseError` until one is bound.
        base_url: API base URL. Falls back to ``DEVICEBASE_BASE_URL``.
        api_key: Bearer token. Falls back to ``DEVICEBASE_API_KEY``.
        timeout: Default deadline for a request, in seconds.
        serial: Deprecated alias for ``serialno``; passing both raises.

    Raises:
        AuthenticationError: If no API key is available.
        ValidationError: If both ``serialno`` and ``serial`` are passed.
    """

    #: Kept as a class attribute because this class has always exposed it there.
    DEFAULT_BASE_URL = DEFAULT_BASE_URL

    def __init__(
        self,
        serialno: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        *,
        serial: str | None = None,
    ) -> None:
        if serial is not None:
            if serialno is not None:
                raise ValidationError("Pass either serialno= or the deprecated serial=, not both.")
            warnings.warn(
                "DeviceBaseClient(serial=…) is deprecated; use serialno=.",
                DeprecationWarning,
                stacklevel=2,
            )
            serialno = serial
        self._serialno = serialno
        self._base_url = (
            base_url or os.environ.get("DEVICEBASE_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self._api_key = api_key or os.environ.get("DEVICEBASE_API_KEY")
        self._http = DeviceBaseHttpClient(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=timeout,
        )

    @property
    def serialno(self) -> str | None:
        """The serialno this client is bound to, or ``None``."""
        return self._serialno

    @property
    def serial(self) -> str | None:
        """Deprecated alias for :attr:`serialno`."""
        warnings.warn(
            "DeviceBaseClient.serial is deprecated; use .serialno.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._serialno

    @property
    def http(self) -> DeviceBaseHttpClient:
        """The full client, for the browser, computer and listing calls."""
        return self._http

    def close(self) -> None:
        """Close the client and release its connection pool."""
        self._http.close()

    def __enter__(self) -> DeviceBaseClient:
        """Context manager entry."""
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.close()

    # Discovery

    def list_devices(
        self,
        keyword: str | None = None,
        state: str | None = None,
        device_type: str | None = None,
        limit: int | None = None,
    ) -> list[Device]:
        """List the devices accessible to the current API key.

        Needs no serial, so it is usable on a client constructed for discovery
        alone. See :meth:`DeviceBaseHttpClient.list_devices` for the filters.
        """
        return self._http.list_devices(
            keyword=keyword,
            state=state,
            device_type=device_type,
            limit=limit,
        )

    # Device info

    def get_device_info(self) -> DeviceInfo:
        """Get detailed information about the device."""
        return self._http.get_device_info(self._require_serialno())

    # Touch

    def tap(self, x: int, y: int) -> OperationResult:
        """Tap once at the given coordinates."""
        return self._http.tap(self._require_serialno(), Point(x=x, y=y))

    def double_tap(self, x: int, y: int) -> OperationResult:
        """Tap twice at the given coordinates."""
        return self._http.double_tap(self._require_serialno(), Point(x=x, y=y))

    def long_press(self, x: int, y: int) -> OperationResult:
        """Press and hold at the given coordinates."""
        return self._http.long_press(self._require_serialno(), Point(x=x, y=y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int) -> OperationResult:
        """Swipe from ``(x1, y1)`` to ``(x2, y2)``."""
        return self._http.swipe(
            self._require_serialno(),
            Bounds(x1=x1, y1=y1, x2=x2, y2=y2),
        )

    # Navigation

    def back(self) -> OperationResult:
        """Press the device back button."""
        return self._http.back(self._require_serialno())

    def home(self) -> OperationResult:
        """Press the device home button."""
        return self._http.home(self._require_serialno())

    # Apps

    def launch_app(self, app_name: str) -> OperationResult:
        """Launch an application on the device."""
        return self._http.launch_app(self._require_serialno(), app_name)

    def stop_app(self, app_name: str) -> OperationResult:
        """Stop an application on the device."""
        return self._http.stop_app(self._require_serialno(), app_name)

    def stop_current_app(self) -> OperationResult:
        """Stop the app currently in the foreground."""
        return self._http.stop_current_app(self._require_serialno())

    def get_current_app(self) -> AppInfo:
        """Get information about the current foreground app."""
        return self._http.get_current_app(self._require_serialno())

    # Text

    def input_text(self, text: str) -> OperationResult:
        """Insert text into the focused field."""
        return self._http.input_text(self._require_serialno(), text)

    def clear_text(self) -> OperationResult:
        """Clear the focused text field."""
        return self._http.clear_text(self._require_serialno())

    # Shell

    def bash(self, command: str) -> OperationResult:
        """Run a shell command on the device (adb/hdc platforms only).

        The command's own exit status comes back as ``data["exitCode"]``; a
        non-zero value does not raise.
        """
        return self._http.bash(self._require_serialno(), command)

    # UI hierarchy

    def dump_hierarchy(self) -> HierarchyInfo:
        """Get the current UI hierarchy tree."""
        return self._http.dump_hierarchy(self._require_serialno())

    # Install

    def install_app(self, app_path: str) -> OperationResult:
        """Start installing a package, from a path on the agent host."""
        return self._http.install_app(self._require_serialno(), app_path)

    def install_status(self, install_id: str) -> OperationResult:
        """Query the background install task started by :meth:`install_app`."""
        return self._http.install_status(self._require_serialno(), install_id)

    # Screenshots

    def get_screenshot(self) -> bytes:
        """Capture the device screen as raw image bytes (JPEG).

        The route dispatches by device type, so a client bound to a browser or
        computer serial captures that platform's screen instead.
        """
        return self._http.get_screenshot(self._require_serialno())

    def download_screenshot(self) -> bytes:
        """Fetch the device's screenshot as a file attachment."""
        return self._http.download_screenshot(self._require_serialno())

    # WebSocket clients

    def minicap_client(self) -> MinicapClient:
        """Create a minicap client for screen streaming.

        Example:
            ```python
            async for frame in client.minicap_client().stream_frames():
                ...  # frame is JPEG bytes
            ```
        """
        return MinicapClient(
            base_url=self._base_url,
            serialno=self._require_serialno(),
            api_key=self._api_key,
        )

    def minitouch_client(self) -> MinitouchClient:
        """Create a minitouch client for low-level touch control.

        Example:
            ```python
            async with client.minitouch_client() as minitouch:
                await minitouch.tap(100, 200)
            ```
        """
        return MinitouchClient(
            base_url=self._base_url,
            serialno=self._require_serialno(),
            api_key=self._api_key,
        )

    def stream_minicap(self) -> AsyncIterator[bytes]:
        """Stream JPEG frames from the device screen.

        A convenience wrapper over :meth:`minicap_client`.
        """
        return self.minicap_client().stream_frames()

    # Internals

    def _require_serialno(self) -> str:
        """Return the bound serialno, or explain how to bind one."""
        if not self._serialno:
            raise DeviceBaseError(
                "No device serialno is bound. Pass serialno=… to DeviceBaseClient, "
                "or use client.http.<action>(serialno, …) and pass one per call. "
                "DeviceBaseClient.list_devices() finds the serialnos available to "
                "the current API key."
            )
        return self._serialno


def list_devices(
    keyword: str | None = None,
    state: str | None = None,
    device_type: str | None = None,
    limit: int | None = None,
    **client_options: Any,
) -> list[Device]:
    """List devices without constructing a client first.

    A module-level convenience over
    :meth:`DeviceBaseClient.list_devices`, for a script whose only jobs are
    discovery and nothing else::

        from devicebase import list_devices

        for device in list_devices(device_type="browser"):
            print(device.serial, device.display_name)

    Args:
        keyword: Free-text match against the device name and serial.
        state: Connection state — ``"busy"``, ``"free"`` or ``"offline"``.
        device_type: A category (``mobile`` / ``browser`` / ``computer``) or a
            system type such as ``android`` or ``chrome``.
        limit: Cap on the number of rows.
        **client_options: Passed to :class:`DeviceBaseClient` — ``base_url``,
            ``api_key``, ``timeout``.
    """
    with DeviceBaseClient(**client_options) as client:
        return client.list_devices(
            keyword=keyword,
            state=state,
            device_type=device_type,
            limit=limit,
        )
