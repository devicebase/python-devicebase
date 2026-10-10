"""Data models for the DeviceBase SDK.

The response containers here are deliberately tolerant: an unknown field is
ignored and a missing one takes a default, so a server-side addition never
breaks a caller. The one exception is :class:`Device`, whose fields are parsed
individually because it is the discovery result every other call depends on.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final, Literal

#: Mouse buttons accepted by :meth:`~devicebase.api.computer.ComputerApi.computer_click`.
#: An omitted button is left out of the body and the server defaults it to "left".
MouseButton = Literal["left", "right", "middle"]

#: Directions accepted by :meth:`~devicebase.api.computer.ComputerApi.computer_scroll`.
ScrollDirection = Literal["up", "down", "left", "right"]

MOUSE_BUTTONS: Final[tuple[str, ...]] = ("left", "right", "middle")
SCROLL_DIRECTIONS: Final[tuple[str, ...]] = ("up", "down", "left", "right")

#: Timestamp layouts accepted from the API, tried in order after
#: :meth:`datetime.datetime.fromisoformat`. The server is not consistent: a
#: device row carries a naive local time with no zone offset
#: (``"2026-09-20T15:11:31"``), while other fields are RFC 3339.
_TIMESTAMP_FORMATS: Final[tuple[str, ...]] = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def parse_timestamp(value: Any) -> datetime | None:
    """Parse an API timestamp, returning ``None`` when it is not recognizable.

    A display field must never fail the response that carries it, so an
    unparseable timestamp degrades to ``None`` rather than raising.

    The result is timezone-naive when the server sent no offset, which is the
    common case for device rows.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        # fromisoformat covers the RFC 3339 forms on 3.11+; the Z swap keeps it
        # working on 3.10, where fromisoformat rejects a trailing Z.
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _as_str(value: Any) -> str:
    """Coerce an API field to a string, treating ``None`` as empty."""
    return value if isinstance(value, str) else ""


def _as_int(value: Any) -> int:
    """Coerce an API field to an int, treating anything else as 0."""
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


# --- Geometry ---------------------------------------------------------------


@dataclass(frozen=True)
class Point:
    """A single screen coordinate.

    Used by the mobile tap / double-tap / long-press actions and by the computer
    click / double-click / move actions. On mobile the coordinates are in the
    screen's own pixel space; on computer they are absolute desktop pixels.

    Attributes:
        x: Horizontal coordinate (pixels from the left).
        y: Vertical coordinate (pixels from the top).
    """

    x: int = 0
    y: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert to a request body."""
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Point:
        """Create a Point from a response payload."""
        return cls(x=_as_int(data.get("x")), y=_as_int(data.get("y")))


@dataclass(frozen=True)
class Bounds:
    """A screen rectangle: a mobile swipe path or a computer drag path.

    Attributes:
        x1: Starting x-coordinate.
        y1: Starting y-coordinate.
        x2: Ending x-coordinate.
        y2: Ending y-coordinate.
    """

    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert to a request body."""
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Bounds:
        """Create Bounds from a response payload."""
        return cls(
            x1=_as_int(data.get("x1")),
            y1=_as_int(data.get("y1")),
            x2=_as_int(data.get("x2")),
            y2=_as_int(data.get("y2")),
        )


# --- Request payloads -------------------------------------------------------


@dataclass(frozen=True)
class LaunchAppRequest:
    """Body for the actions that take an app name.

    Used by mobile ``launch_app`` / ``stop_app`` and computer ``launch_app``.

    Attributes:
        app_name: Package name on mobile, application name on computer.
    """

    app_name: str = ""

    def to_dict(self) -> dict[str, str]:
        """Convert to a request body."""
        return {"app_name": self.app_name}


@dataclass(frozen=True)
class InputTextRequest:
    """Body for the actions that insert text.

    Used by mobile ``input``, browser ``input`` (CDP ``Input.insertText``) and
    computer ``type_text``.

    Attributes:
        text: The text to insert.
    """

    text: str = ""

    def to_dict(self) -> dict[str, str]:
        """Convert to a request body."""
        return {"text": self.text}


# --- Response payloads ------------------------------------------------------


@dataclass(frozen=True)
class DeviceInfo:
    """Device status, hardware info and connection state.

    The payload is kept as a mapping because its shape differs per platform.
    """

    serialno: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def serial(self) -> str:
        """Deprecated alias for :attr:`serialno`."""
        warnings.warn(
            "DeviceInfo.serial is deprecated; use DeviceInfo.serialno.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.serialno

    @classmethod
    def from_dict(cls, serialno: str, data: dict[str, Any]) -> DeviceInfo:
        """Create DeviceInfo from an API response."""
        return cls(serialno=serialno, data=data)


@dataclass(frozen=True)
class AppInfo:
    """Information about the currently running application."""

    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppInfo:
        """Create AppInfo from an API response."""
        return cls(data=data)


@dataclass(frozen=True)
class HierarchyInfo:
    """The current UI element tree."""

    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HierarchyInfo:
        """Create HierarchyInfo from an API response."""
        return cls(data=data)


@dataclass(frozen=True)
class OperationResult:
    """The result of a device control action.

    A successful call returns one of these even when the action itself reports a
    non-zero status — a shell command that exits 1 arrives with ``exitCode``
    set, not as an exception, because the API call succeeded. A failure that the
    API itself reports raises instead (see
    :class:`~devicebase.errors.BusinessError`).

    Attributes:
        success: The payload's ``success`` flag, defaulting to ``True`` when the
            endpoint does not send one.
        data: The whole response envelope, ``code`` and ``message`` included.
            Use :attr:`payload` for the action's own object.
    """

    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OperationResult:
        """Create OperationResult from an API response."""
        raw = data.get("success")
        return cls(success=raw if isinstance(raw, bool) else True, data=data)

    @property
    def payload(self) -> dict[str, Any]:
        """The response envelope's ``data`` object.

        The action's own result lives one level in — an action answers
        ``{"code":200,"data":{…}}`` — so ``result.payload["exitCode"]`` is the
        useful spelling, not ``result.data["data"]["exitCode"]``.

        Returns an empty mapping when the envelope carries no ``data`` object.
        """
        inner = self.data.get("data")
        return inner if isinstance(inner, dict) else {}


@dataclass(frozen=True)
class Device:
    """One row of the device list.

    ``serialno`` is the identifier every control method takes — it is what the
    ``/v1/devices`` route names ``serialno``, e.g. ``"db-mttul4i41di8"``.
    ``device_sn`` is the physical serial; the gateway resolves either, but
    ``serialno`` is the primary key and the one this SDK hands back.

    Attributes:
        id: Numeric device id.
        serialno: Platform identifier, used as the serialno in every call.
        device_sn: Physical serial, when the row carries one.
        state: Connection state — ``"busy"``, ``"free"`` or ``"offline"``.
        name: Registered device name.
        alias_name: User-set display name.
        udid: Platform UDID, when the platform exposes one.
        type: Coarse platform bucket — ``mobile``, ``browser`` or ``computer``.
        brand: Manufacturer.
        model: Hardware model.
        os_type: System type, e.g. ``Android``, ``Chrome``, ``macOS``. This is
            what the ``--type`` system values resolve against.
        os_version: System version.
        display: Screen specification.
        location: Physical location of the device.
        operator: Carrier, when applicable.
        network: Network type, when applicable.
        updated_at: Last state change. Timezone-naive when the server sent no
            offset; ``None`` when the field was absent or unparseable.
    """

    id: int = 0
    serialno: str = ""
    device_sn: str = ""
    state: str = ""
    name: str = ""
    alias_name: str = ""
    udid: str = ""
    type: str = ""
    brand: str = ""
    model: str = ""
    os_type: str = ""
    os_version: str = ""
    display: str = ""
    location: str = ""
    operator: str = ""
    network: str = ""
    updated_at: datetime | None = None

    @property
    def serial(self) -> str:
        """Deprecated alias for :attr:`serialno`."""
        warnings.warn(
            "Device.serial is deprecated; use Device.serialno.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.serialno

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Device:
        """Create a Device from one row of ``GET /v1/devices``.

        The identifier is read from ``serialno``. ``serial`` is accepted as a
        fallback because the older Python service names the same column that
        way; deployments of the two services disagree, so both are honoured.
        Either value is what a control call takes.
        """
        return cls(
            id=_as_int(data.get("id")),
            serialno=_as_str(data.get("serialno")) or _as_str(data.get("serial")),
            device_sn=_as_str(data.get("device_sn")),
            state=_as_str(data.get("state")),
            name=_as_str(data.get("name")),
            alias_name=_as_str(data.get("alias_name")),
            udid=_as_str(data.get("udid")),
            type=_as_str(data.get("type")),
            brand=_as_str(data.get("brand")),
            model=_as_str(data.get("model")),
            os_type=_as_str(data.get("os_type")),
            os_version=_as_str(data.get("os_version")),
            display=_as_str(data.get("display")),
            location=_as_str(data.get("location")),
            operator=_as_str(data.get("operator")),
            network=_as_str(data.get("network")),
            updated_at=parse_timestamp(data.get("updated_at")),
        )

    @property
    def display_name(self) -> str:
        """The friendliest available label, falling back to the serialno."""
        return self.alias_name or self.name or self.serialno


@dataclass(frozen=True)
class CloudBrowserCreateResult:
    """What a successful ``cloud_browser_create`` hands back.

    Creating is asynchronous — the browser has to start and register itself —
    so the call waits for that and reports both halves: ``serialno`` once the
    browser exists as a device, and ``device_sn`` either way.

    ``registered`` being ``False`` is **not** a failure: the browser is still
    starting. Ask again with
    :meth:`~devicebase.api.cloud_browser.CloudBrowserApi.cloud_browser_status`
    using ``device_sn``, or delete it with the same value.

    Attributes:
        serialno: The platform identifier every other browser call takes. Empty
            until the browser has registered.
        device_sn: The node-side identifier it registers under. Valid as a
            handle whether or not registration has happened yet.
        name: The platform's own identity name (`Browser-` plus the first eight
            characters of the serial). Not the name you asked for — that is
            ``alias_name``.
        alias_name: The name passed to ``cloud_browser_create``, verbatim, or
            empty when none was given. The platform pins it at creation and the
            node's later re-registrations cannot change it: a node calls its
            instance ``<requested>-<port>``, which is not what a caller should
            be shown.
        registered: Whether the device row exists yet.
    """

    serialno: str = ""
    device_sn: str = ""
    name: str = ""
    alias_name: str = ""
    registered: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CloudBrowserCreateResult:
        return cls(
            serialno=_as_str(data.get("serialno")),
            device_sn=_as_str(data.get("device_sn")),
            name=_as_str(data.get("name")),
            alias_name=_as_str(data.get("alias_name")),
            registered=bool(data.get("registered")),
        )


@dataclass(frozen=True)
class CloudBrowserQuota:
    """The account's cloud browser allowance.

    Counted from the same source as the check creation performs, so the two
    cannot disagree. Only cloud browsers count — ones you attached yourself are
    not part of it.

    Attributes:
        limit: How many cloud browsers the account may have.
        used: How many it has.
        remaining: How many may still be created; never negative.
    """

    limit: int = 0
    used: int = 0
    remaining: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CloudBrowserQuota:
        return cls(
            limit=_as_int(data.get("limit")),
            used=_as_int(data.get("used")),
            remaining=_as_int(data.get("remaining")),
        )


@dataclass(frozen=True)
class CloudBrowserStatus:
    """Whether a created cloud browser has registered itself yet.

    ``registered`` is ``False`` while the browser is still starting up, which
    is a normal answer rather than an error — polling for it is quiet. The
    remaining fields are only meaningful once it is ``True``.

    Attributes:
        registered: Whether the device row exists yet.
        device_id: Numeric device id, once registered.
        serialno: The platform identifier to drive it with, once registered.
        name: The platform's identity name for the browser.
        alias_name: The name the caller asked for, empty when none was given.
        state: Connection state — ``"busy"``, ``"free"`` or ``"offline"``.
        server_url: Relay host the platform reaches it through. Its presence is
            what "can I start using it" depends on.
        is_cloud: Whether the platform built this one (as opposed to a browser
            attached by hand). Always true for a browser this call created.
    """

    registered: bool = False
    device_id: int = 0
    serialno: str = ""
    name: str = ""
    alias_name: str = ""
    state: str = ""
    server_url: str = ""
    is_cloud: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CloudBrowserStatus:
        return cls(
            registered=bool(data.get("registered")),
            device_id=_as_int(data.get("device_id")),
            serialno=_as_str(data.get("serialno")),
            name=_as_str(data.get("name")),
            alias_name=_as_str(data.get("alias_name")),
            state=_as_str(data.get("state")),
            server_url=_as_str(data.get("server_url")),
            is_cloud=bool(data.get("is_cloud")),
        )


# --- Account ----------------------------------------------------------------


@dataclass(frozen=True)
class UserInfo:
    """The account behind the API key.

    Returned by :meth:`~devicebase.api.user.UserApi.user_info`: the name shown
    in the console, the phone number on the account, the points balance and
    when the account was created.

    Attributes:
        id: Account id.
        username: The name shown in the console.
        mobile: Phone number on the account.
        credits: Points balance (积分).
        registered_at: When the account was created, naive ISO format.
        can_checkin: Whether today's check-in reward is still unclaimed.
    """

    id: int = 0
    username: str = ""
    mobile: str = ""
    credits: int = 0
    registered_at: str = ""
    can_checkin: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserInfo:
        return cls(
            id=_as_int(data.get("id")),
            username=_as_str(data.get("username")),
            mobile=_as_str(data.get("mobile")),
            credits=_as_int(data.get("credits")),
            registered_at=_as_str(data.get("registered_at")),
            can_checkin=bool(data.get("can_checkin")),
        )


@dataclass(frozen=True)
class UserCheckin:
    """The result of claiming the daily points.

    ``already_checked`` is a normal outcome rather than an error: claiming
    twice in one day answers with it ``True``, ``credits_earned`` 0 and the
    platform's own ``message`` ("今日已签到"). That is what makes the daily
    check-in safe to run from a scheduled task.

    Attributes:
        success: Whether this call actually granted points.
        credits_earned: Points granted, 0 when the day was already claimed.
        consecutive_days: The streak this claim belongs to; the first day is 1.
        already_checked: Whether today had already been claimed.
        message: The platform's own wording, for display as-is.
        credits: Points balance after this call.
    """

    success: bool = False
    credits_earned: int = 0
    consecutive_days: int = 0
    already_checked: bool = False
    message: str = ""
    credits: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserCheckin:
        return cls(
            success=bool(data.get("success")),
            credits_earned=_as_int(data.get("credits_earned")),
            consecutive_days=_as_int(data.get("consecutive_days")),
            already_checked=bool(data.get("already_checked")),
            message=_as_str(data.get("message")),
            credits=_as_int(data.get("credits")),
        )
