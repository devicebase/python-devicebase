"""Mobile platform API (Android / HarmonyOS / iOS).

Path family: ``POST/GET /v1/{action}/{serialno}``. The control server registers
these paths and redirects them to its ``/api/*`` handlers, so the method and the
body survive the hop.

A ``serialno`` identifies a registered mobile device: it is the ``serialno``
field from :meth:`~devicebase.api.device.DeviceApi.list_devices` with
``type="mobile"``. The device's ``device_sn`` UUID resolves too.

One action is cross-family: :meth:`MobileApi.get_screenshot` reaches
``/v1/screen/{serialno}``, which the server dispatches by device type, so a
browser or computer serialno works there as well.
"""

from __future__ import annotations

from devicebase.models import (
    AppInfo,
    Bounds,
    DeviceInfo,
    HierarchyInfo,
    InputTextRequest,
    LaunchAppRequest,
    OperationResult,
    Point,
)
from devicebase.transport import HttpTransport, escape_path_segment


def mobile_path(action: str, serialno: str) -> str:
    """Build ``/v1/{action}/{serialno}`` — the mobile route family."""
    return f"/v1/{action}/{escape_path_segment(serialno)}"


class MobileApi(HttpTransport):
    """Mobile actions, each taking the target device's serialno explicitly."""

    # --- Device info ------------------------------------------------------

    def get_device_info(self, serialno: str) -> DeviceInfo:
        """Get detailed information about a device.

        Returns:
            DeviceInfo with the raw payload in ``.data``.

        Raises:
            DeviceNotFoundError: If the device is not found or not connected.
        """
        data = self.request_json("POST", mobile_path("deviceinfo", serialno))
        return DeviceInfo.from_dict(serialno, data)

    # --- Touch ------------------------------------------------------------

    def tap(self, serialno: str, point: Point) -> OperationResult:
        """Tap once at the given coordinates."""
        return self._operation("POST", mobile_path("tap", serialno), body=point.to_dict())

    def double_tap(self, serialno: str, point: Point) -> OperationResult:
        """Tap twice at the given coordinates."""
        return self._operation("POST", mobile_path("double_tap", serialno), body=point.to_dict())

    def long_press(self, serialno: str, point: Point) -> OperationResult:
        """Press and hold at the given coordinates."""
        return self._operation("POST", mobile_path("long_press", serialno), body=point.to_dict())

    def swipe(self, serialno: str, bounds: Bounds) -> OperationResult:
        """Swipe from ``(x1, y1)`` to ``(x2, y2)``."""
        return self._operation("POST", mobile_path("swipe", serialno), body=bounds.to_dict())

    # --- Navigation -------------------------------------------------------

    def back(self, serialno: str) -> OperationResult:
        """Press the device back button."""
        return self._operation("POST", mobile_path("back", serialno))

    def home(self, serialno: str) -> OperationResult:
        """Press the device home button."""
        return self._operation("POST", mobile_path("home", serialno))

    # --- Apps -------------------------------------------------------------

    def launch_app(self, serialno: str, app_name: str) -> OperationResult:
        """Launch an application."""
        return self._app_action("launch_app", serialno, app_name)

    def stop_app(self, serialno: str, app_name: str) -> OperationResult:
        """Stop an application."""
        return self._app_action("stop_app", serialno, app_name)

    def stop_current_app(self, serialno: str) -> OperationResult:
        """Stop the app currently in the foreground."""
        return self._operation("POST", mobile_path("stop_current_app", serialno))

    def get_current_app(self, serialno: str) -> AppInfo:
        """Get information about the current foreground app."""
        data = self.request_json("POST", mobile_path("current_app", serialno))
        return AppInfo.from_dict(data)

    # --- Text -------------------------------------------------------------

    def input_text(self, serialno: str, text: str) -> OperationResult:
        """Insert text into the focused field."""
        return self._operation(
            "POST",
            mobile_path("input", serialno),
            body=InputTextRequest(text=text).to_dict(),
        )

    def clear_text(self, serialno: str) -> OperationResult:
        """Clear the focused text field."""
        return self._operation("POST", mobile_path("clear_text", serialno))

    # --- Shell ------------------------------------------------------------

    def bash(self, serialno: str, command: str) -> OperationResult:
        """Run a shell command on the device (adb/hdc platforms only).

        The command's own exit status comes back as ``payload["exitCode"]``. A
        non-zero value is not an API error, so it does not raise.
        """
        return self._operation("POST", mobile_path("bash", serialno), body={"command": command})

    # --- State ------------------------------------------------------------

    def dump_hierarchy(self, serialno: str) -> HierarchyInfo:
        """Get the current UI hierarchy tree."""
        data = self.request_json("POST", mobile_path("dump_hierarchy", serialno))
        return HierarchyInfo.from_dict(data)

    # --- Install ----------------------------------------------------------

    def install_app(self, serialno: str, app_path: str) -> OperationResult:
        """Start installing a package, in the background.

        Args:
            serialno: The device serialno.
            app_path: Path to the package on the **agent host**, not a local
                file — the SDK does not upload the package.

        Returns:
            OperationResult carrying the install id to poll with
            :meth:`install_status`.
        """
        return self._operation(
            "POST", mobile_path("install_app", serialno), body={"app_path": app_path}
        )

    def install_status(self, serialno: str, install_id: str) -> OperationResult:
        """Query the background install task started by :meth:`install_app`.

        Args:
            serialno: The device serialno.
            install_id: The id returned by :meth:`install_app`.
        """
        return self._operation(
            "GET",
            mobile_path("install_status", serialno),
            params={"install_id": install_id},
        )

    # --- Screenshot -------------------------------------------------------

    def get_screenshot(self, serialno: str) -> bytes:
        """Capture the screen and return the raw image bytes.

        The server decides the format — JPEG today. This route is cross-family:
        it dispatches by device type, so a browser or computer serialno captures
        that platform's screen instead (computer → full desktop, browser → CDP).

        Args:
            serialno: The device serialno, on any of the three platforms.

        Returns:
            Raw image bytes.
        """
        return self.request_bytes("POST", mobile_path("screen", serialno))

    def download_screenshot(self, serialno: str) -> bytes:
        """Fetch the device's screenshot as a file attachment.

        A second, SDK-only route with no CLI equivalent: ``GET
        /v1/screenshot/{serialno}`` rather than the cross-family ``/v1/screen``
        used by :meth:`get_screenshot`.
        """
        return self.request_bytes("GET", f"/v1/screenshot/{escape_path_segment(serialno)}")

    # --- Internals --------------------------------------------------------

    def _app_action(self, action: str, serialno: str, app_name: str) -> OperationResult:
        """Shared body for the two actions that take an app name."""
        return self._operation(
            "POST",
            mobile_path(action, serialno),
            body=LaunchAppRequest(app_name=app_name).to_dict(),
        )
