"""Computer platform API (macOS / Windows / Linux desktops).

Path family: ``POST/GET /api/computer/{serial}/{action}``.

``serial`` is the platform serial of a registered computer device — the
``serial`` field from :meth:`~devicebase.api.device.DeviceApi.list_devices`
with ``type="computer"``. Coordinates are absolute screen pixels.

The read-only actions (``position``, ``screen_size``, ``permissions``) carry no
body. Coordinates arrive as plain numbers rather than the mobile family's
``Point``/``Bounds``, because every computer action also takes an optional
argument (a button, a duration) that a geometry object cannot carry.
"""

from __future__ import annotations

from typing import Any

from devicebase.models import (
    MOUSE_BUTTONS,
    SCROLL_DIRECTIONS,
    InputTextRequest,
    LaunchAppRequest,
    MouseButton,
    OperationResult,
    ScrollDirection,
)
from devicebase.transport import (
    ACTION_TIMEOUT_MARGIN,
    DEFAULT_BASH_TIMEOUT_SECONDS,
    HttpTransport,
    escape_path_segment,
    reject,
)


def computer_path(action: str, serial: str) -> str:
    """Build ``/api/computer/{serial}/{action}``."""
    return f"/api/computer/{escape_path_segment(serial)}/{action}"


def bash_timeout(timeout_seconds: int) -> float:
    """Bound the HTTP deadline for a bash call, in seconds.

    It has to exceed the requested command timeout, or the client would abort a
    command the server is still running and report a transport error for work
    that would have succeeded.
    """
    seconds = timeout_seconds if timeout_seconds > 0 else DEFAULT_BASH_TIMEOUT_SECONDS
    return seconds + ACTION_TIMEOUT_MARGIN


def wait_timeout(milliseconds: int) -> float:
    """The same idea for ``wait``, whose budget arrives as milliseconds.

    The shared 30s default would abort every wait past 30s.
    """
    return max(0, milliseconds) / 1000 + ACTION_TIMEOUT_MARGIN


def _check_choice(value: str, allowed: tuple[str, ...], argument: str) -> None:
    """Reject a value outside a fixed set before it reaches the network.

    Raises:
        ValidationError: So ``except DeviceBaseError`` covers a local rejection
            as well as a server-side one. Carries no status code — nothing was
            sent.
    """
    if value not in allowed:
        raise reject(f"{argument} must be one of {', '.join(allowed)}, got {value!r}")


class ComputerApi(HttpTransport):
    """Computer actions, each taking the device serial explicitly."""

    # --- Mouse ------------------------------------------------------------

    def computer_click(
        self,
        serial: str,
        x: int,
        y: int,
        button: MouseButton | None = None,
    ) -> OperationResult:
        """Click at absolute screen coordinates.

        Args:
            serial: The device serial.
            x: Horizontal screen pixel.
            y: Vertical screen pixel.
            button: ``"left"``, ``"right"`` or ``"middle"``. Omitted, the field
                is left out of the body and the server defaults it to left.

        Raises:
            ValidationError: If ``button`` is not one of the three accepted
                values. Raised locally, before any request.
        """
        body: dict[str, Any] = {"x": x, "y": y}
        if button is not None:
            _check_choice(button, MOUSE_BUTTONS, "button")
            body["button"] = button
        return self._operation("POST", computer_path("click", serial), body=body)

    def computer_double_click(self, serial: str, x: int, y: int) -> OperationResult:
        """Double click at absolute screen coordinates, with the left button."""
        return self._operation("POST", computer_path("double_click", serial), body={"x": x, "y": y})

    def computer_long_click(
        self,
        serial: str,
        x: int,
        y: int,
        duration: int = 0,
    ) -> OperationResult:
        """Press and hold the left button at the coordinates.

        Args:
            serial: The device serial.
            x: Horizontal screen pixel.
            y: Vertical screen pixel.
            duration: Hold time in seconds. Zero leaves the field out and the
                server applies the driver default.
        """
        body: dict[str, Any] = {"x": x, "y": y}
        if duration:
            body["duration"] = duration
        return self._operation("POST", computer_path("long_click", serial), body=body)

    def computer_move(self, serial: str, x: int, y: int) -> OperationResult:
        """Move the mouse to absolute screen coordinates, without clicking."""
        return self._operation("POST", computer_path("move", serial), body={"x": x, "y": y})

    def computer_drag(
        self,
        serial: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> OperationResult:
        """Press the left button at ``(x1, y1)``, move to ``(x2, y2)``, release."""
        body = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        return self._operation("POST", computer_path("drag", serial), body=body)

    def computer_scroll(
        self,
        serial: str,
        direction: ScrollDirection,
        amount: int = 0,
    ) -> OperationResult:
        """Scroll the mouse wheel.

        Args:
            serial: The device serial.
            direction: ``"up"``, ``"down"``, ``"left"`` or ``"right"``.
            amount: Scroll amount. Zero leaves the field out and the server
                applies its own default.

        Raises:
            ValidationError: If ``direction`` is not one of the four accepted
                values. Raised locally, before any request.
        """
        _check_choice(direction, SCROLL_DIRECTIONS, "direction")
        body: dict[str, Any] = {"direction": direction}
        if amount:
            body["amount"] = amount
        return self._operation("POST", computer_path("scroll", serial), body=body)

    # --- Keyboard ---------------------------------------------------------

    def computer_type_text(self, serial: str, text: str) -> OperationResult:
        """Type text at the current caret of the focused application."""
        return self._operation(
            "POST",
            computer_path("type_text", serial),
            body=InputTextRequest(text=text).to_dict(),
        )

    def computer_press(self, serial: str, key: str) -> OperationResult:
        """Press a single key, e.g. ``"Enter"`` or ``"F5"``."""
        return self._operation("POST", computer_path("press", serial), body={"key": key})

    def computer_hotkey(self, serial: str, keys: list[str]) -> OperationResult:
        """Press the given keys together, e.g. ``["Meta", "c"]``."""
        return self._operation("POST", computer_path("hotkey", serial), body={"keys": keys})

    # --- System -----------------------------------------------------------

    def computer_position(self, serial: str) -> OperationResult:
        """Get the current mouse position."""
        return self._operation("GET", computer_path("position", serial))

    def computer_screen_size(self, serial: str) -> OperationResult:
        """Get the primary screen size in pixels."""
        return self._operation("GET", computer_path("screen_size", serial))

    def computer_permissions(self, serial: str) -> OperationResult:
        """Get the desktop-control permission status.

        Screen recording and accessibility permissions are granted per
        application on macOS, so a missing one shows up here rather than as a
        mysteriously failed click.
        """
        return self._operation("GET", computer_path("permissions", serial))

    def computer_launch_app(self, serial: str, app_name: str) -> OperationResult:
        """Launch a desktop application."""
        return self._operation(
            "POST",
            computer_path("launch_app", serial),
            body=LaunchAppRequest(app_name=app_name).to_dict(),
        )

    # --- Blocking actions -------------------------------------------------

    def computer_wait(self, serial: str, milliseconds: int) -> OperationResult:
        """Block for the given duration, in milliseconds.

        The deadline is widened to cover the wait itself — the shared 30s
        default would abort any wait longer than that. A negative duration
        waits not at all rather than going backwards.
        """
        seconds = max(0, milliseconds) / 1000
        return self._operation(
            "POST",
            computer_path("wait", serial),
            body={"seconds": seconds},
            timeout=wait_timeout(milliseconds),
        )

    def computer_bash(
        self,
        serial: str,
        command: str,
        timeout_seconds: int = 0,
    ) -> OperationResult:
        """Run a shell command on the host machine that owns this device.

        The command runs as the desktop user under the platform default shell,
        unsandboxed — treat it as shell access. ``timeout_seconds`` is the
        server-side budget for the command; zero leaves the field out and the
        server applies its 120s default. The transport deadline is widened to
        cover it either way.

        The command's own exit status comes back as ``payload["exitCode"]``. A
        non-zero value is not an API error, so it does not raise — check it when
        the command's outcome matters.
        """
        body: dict[str, Any] = {"command": command}
        if timeout_seconds:
            body["timeout"] = timeout_seconds
        return self._operation(
            "POST",
            computer_path("bash", serial),
            body=body,
            timeout=bash_timeout(timeout_seconds),
        )
