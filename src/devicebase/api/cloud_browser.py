"""Cloud browser lifecycle — ``POST /v1/browser/create``,
``DELETE /v1/browser/{serialno}``, ``GET /v1/browser/{serialno}/status`` and
``GET /v1/browser/quota``.

Not to be confused with :class:`~devicebase.api.browser.BrowserApi`: those are
device actions against an already registered browser
(``/api/browser/{serialno}/{action}``), while these four are the account-level
resource lifecycle that creates and destroys one. A cloud browser is a browser
the platform runs for you on its own cluster; a Chrome you attached yourself is
not one of them — :attr:`~devicebase.models.Device.is_cloud` tells the two
apart.

The contract lives in ``devicebase-ts/openapi/src/api/routes/browser.ts``.

Status codes decide whether a retry is worth it. ``409`` means a conflict that
retrying will not fix (quota exhausted, or the identifier is not a cloud
browser), ``502`` a platform↔node problem somebody has to repair, ``503`` the
temporary kind (no capacity right now, or the node could not be reached). None
of the three has a dedicated exception class — they arrive as
:class:`~devicebase.errors.DeviceBaseError` carrying ``status_code``, which is
what a caller branches on.
"""

from __future__ import annotations

from typing import Any

from devicebase.models import CloudBrowserCreateResult, CloudBrowserQuota, CloudBrowserStatus
from devicebase.transport import HttpTransport, escape_path_segment, reject

# The server trims and bounds the name (``devices.name`` is VARCHAR(200) and the
# API takes half of it); rejecting it here saves a round trip that would
# otherwise run placement first.
NAME_MAX_LENGTH = 100

# Wait bounds — the server's own (it rejects anything outside them).
DEFAULT_WAIT_SECONDS = 15
MAX_WAIT_SECONDS = 60

# The platform's node-call budget is 20s, and the wait comes after it; the slack
# covers both so the client never gives up on a request still being answered.
CREATE_TIMEOUT_SLACK_SECONDS = 45.0


def cloud_browser_path(identifier: str) -> str:
    """Build ``/v1/browser/{identifier}``, escaping the path segment.

    The identifier is caller-supplied — a ``serialno``, or the ``serial``
    returned by creation — so unlike a device serialno it is not guaranteed to
    be URL-safe.
    """
    return f"/v1/browser/{escape_path_segment(identifier)}"


class CloudBrowserApi(HttpTransport):
    """Cloud browser lifecycle, none of it addressing an existing device."""

    # --- Creation ---------------------------------------------------------

    def cloud_browser_create(
        self,
        *,
        name: str | None = None,
        window_size: str | None = None,
        wait_seconds: int | None = None,
    ) -> CloudBrowserCreateResult:
        """Ask the platform for a new cloud browser.

        The platform picks the machine itself, so there is nothing here to
        choose a node with. Creation is asynchronous — the browser has to start
        and register itself — so the call waits for that (15 seconds by
        default) and hands back the ``serialno`` every other browser method
        takes. Nobody should have to write a poll loop to use what they just
        created.

        A cloud browser always runs headless: it lives on a machine nobody is
        looking at, and there is no argument for that.

        Args:
            name: Label shown in the device list, at most 100 characters. The
                server applies its own naming rule when omitted.
            window_size: ``"1366x768"`` shaped — the node parses width x height.
            wait_seconds: How long to wait for it to register before answering,
                0-60. ``0`` answers immediately, which suits creating a batch.
                Left as ``None`` the server waits its own default of 15.

        Returns:
            The creation result: ``serialno`` (the platform key, empty when it
            has not come up yet), ``device_sn``, ``name`` and ``registered``.
            A wait that runs out is not a failure — see
            :class:`~devicebase.models.CloudBrowserCreateResult`.

        Raises:
            ValidationError: If ``name``, ``window_size`` or ``wait_seconds``
                was rejected locally.
            DeviceBaseError: With ``status_code == 409`` when the account's
                browser quota is exhausted; ``503`` when no node had room or
                the chosen one could not be reached (retrying later is
                reasonable); ``502`` when the platform and the node failed to
                authenticate each other (retrying does not help).
        """
        if name is not None:
            trimmed = name.strip()
            if not trimmed:
                raise reject("name cannot be empty")
            if len(trimmed) > NAME_MAX_LENGTH:
                raise reject(f"name is longer than {NAME_MAX_LENGTH} characters")
            name = trimmed
        if window_size is not None:
            window_size = _validated_window_size(window_size)

        if wait_seconds is not None and not 0 <= wait_seconds <= MAX_WAIT_SECONDS:
            raise reject(
                f"wait_seconds must be between 0 and {MAX_WAIT_SECONDS}, got {wait_seconds}"
            )

        body: dict[str, Any] = {
            "name": name,
            "window_size": window_size,
            "wait_seconds": wait_seconds,
        }
        # The call blocks on the platform side for the dispatch (up to 20s) and
        # then the wait, so it raises its own deadline — the shared default would
        # abort a request the server is still working on.
        wait = wait_seconds if wait_seconds is not None else DEFAULT_WAIT_SECONDS
        data = self.request_json(
            "POST",
            "/v1/browser/create",
            body=_without_none(body),
            timeout=wait + CREATE_TIMEOUT_SLACK_SECONDS,
        )
        return CloudBrowserCreateResult.from_dict(_data_object(data))

    # --- Deletion ---------------------------------------------------------

    def cloud_browser_delete(self, identifier: str) -> None:
        """Destroy a cloud browser and its profile. Irreversible.

        Not the same as :meth:`~devicebase.api.browser.BrowserApi.browser_close`,
        which only stops the CDP engine of a browser you still have.

        The call does not wait for the machine: the platform queues the reap and
        the node collects it on its next heartbeat, so this succeeds even while
        the node is offline.

        Args:
            identifier: The platform ``serialno`` (``db-…``) or the ``serial``
                returned by :meth:`cloud_browser_create`.

        Raises:
            DeviceNotFoundError: If it does not exist, is not yours, or was
                already deleted — the server answers the same way for all three,
                so the endpoint cannot be used to probe for someone else's.
            DeviceBaseError: With ``status_code == 409`` when the device is
                not a cloud browser — one you attached yourself is not the
                platform's to remove.
        """
        if not identifier.strip():
            raise reject("identifier cannot be empty")
        self._send("DELETE", cloud_browser_path(identifier))

    # --- Inspection -------------------------------------------------------

    def cloud_browser_status(self, identifier: str) -> CloudBrowserStatus:
        """Report whether the browser has registered itself yet.

        The device row appears only when the node registers the browser, a
        moment after creation returns, so this is how the wait is spent.

        "Not up yet" is a normal answer — ``registered`` is ``False`` and
        nothing is raised — so polling this in a loop is quiet.

        Args:
            identifier: The ``serial`` from creation, or the ``serialno`` once
                it is up. Either resolves.
        """
        if not identifier.strip():
            raise reject("identifier cannot be empty")
        data = self.request_json("GET", f"{cloud_browser_path(identifier)}/status")
        return CloudBrowserStatus.from_dict(_data_object(data))

    def cloud_browser_quota(self) -> CloudBrowserQuota:
        """How many cloud browsers this account may still create.

        Counted from the same source as the check creation performs, so the two
        cannot disagree. Only cloud browsers count — ones you attached yourself
        are not part of the allowance.
        """
        data = self.request_json("GET", "/v1/browser/quota")
        return CloudBrowserQuota.from_dict(_data_object(data))


def _validated_window_size(window_size: str) -> str:
    """Reject anything the node would not parse, before the round trip."""
    size = window_size.strip()
    width, separator, height = size.partition("x")
    if (
        separator != "x"
        or not width.isdigit()
        or not height.isdigit()
        or not 1 <= len(width) <= 5
        or not 1 <= len(height) <= 5
    ):
        raise reject(f'window_size must look like 1366x768, got "{window_size}"')
    return size


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    """Drop unset fields: the server reads absence, not null."""
    return {key: value for key, value in values.items() if value is not None}


def _data_object(data: dict[str, Any]) -> dict[str, Any]:
    """The ``data`` object of an envelope, or an empty mapping."""
    inner = data.get("data")
    if not isinstance(inner, dict):
        return {}
    return inner
