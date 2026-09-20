"""HTTP transport shared by every platform client.

This module knows about base URLs, Bearer auth, query escaping, deadlines and
the two failure layers — and deliberately nothing about devices. The platform
methods live in :mod:`devicebase.api`, each a subclass of :class:`HttpTransport`.

Two failure layers are mapped to errors:

* a non-2xx HTTP status, via :func:`error_for_status`;
* a business failure reported inside an otherwise successful response, via
  :func:`check_envelope`.

The same envelope inspection runs over binary responses (:meth:`request_bytes`),
so a screenshot that came back as a JSON error is not handed to the caller as
image data.
"""

from __future__ import annotations

import json
import os
from typing import Any, TypeVar
from urllib.parse import quote

import httpx

from devicebase.errors import (
    AuthenticationError,
    BusinessError,
    DeviceBaseError,
    DeviceNotFoundError,
    ValidationError,
    truncate,
)
from devicebase.models import OperationResult

#: Default API base URL, used when neither ``base_url`` nor
#: ``DEVICEBASE_BASE_URL`` is set.
DEFAULT_BASE_URL = "https://api.devicebase.cn"

#: The 2xx band. Anything outside it is a failure: a redirect the client did not
#: follow is not the action's result, and treating it as one would report an
#: action that never ran as a success.
_SUCCESS_STATUS = range(200, 300)

#: Deadline for an ordinary request, in seconds.
DEFAULT_TIMEOUT = 30.0

#: Headroom added on top of a blocking action's own budget, covering connect and
#: body-read overhead. ``computer_wait`` and ``computer_bash`` size their
#: deadline from it.
ACTION_TIMEOUT_MARGIN = 15.0

#: The server's own default for a ``computer_bash`` command, in seconds. Used
#: only to size the client deadline when the caller omits a timeout.
DEFAULT_BASH_TIMEOUT_SECONDS = 120

#: Bodies larger than this are never sniffed for an envelope. Screenshots run to
#: hundreds of kilobytes, so decoding one as JSON to look for an error would cost
#: more than it could save.
ENVELOPE_SNIFF_BYTES = 64 * 1024

#: Binds the context-manager methods to the class they were called on. Without
#: it `with DeviceBaseHttpClient() as client:` would be typed as HttpTransport,
#: and every platform method would vanish for a type checker.
_TransportT = TypeVar("_TransportT", bound="HttpTransport")


def escape_path_segment(value: str) -> str:
    """URL-quote a serialno so it cannot break out of a path segment."""
    return quote(str(value), safe="")


def error_for_status(status: int, detail: str) -> DeviceBaseError:
    """Map a non-2xx HTTP status onto the matching error class.

    ``detail`` is the already-truncated body of the response, or its reason
    phrase when the body was empty.
    """
    message = f"API error (HTTP {status}): {detail}"
    if status == 401:
        return AuthenticationError(message, status)
    if status == 404:
        return DeviceNotFoundError(message, status)
    if status in (400, 422):
        # The gateway reports validation failures as 400; 422 is kept for
        # compatibility with older deployments.
        return ValidationError(message, status)
    return DeviceBaseError(message, status)


def reject(message: str) -> ValidationError:
    """Build a ValidationError for an argument rejected before any request.

    It carries no HTTP status: nothing was sent, so there is no status to
    report. Raising the SDK's own error type rather than a bare ``ValueError``
    keeps ``except DeviceBaseError`` the single handler a caller needs.
    """
    return ValidationError(message)


def check_envelope(text: str) -> None:
    """Raise :class:`BusinessError` when the body carries a business failure.

    The control API answers HTTP 200 with a non-2xx ``code`` for action
    failures, e.g. ``{"code":502,"message":"-32602: …"}`` when a browser action
    fails in the driver. Trusting the status line alone reports those as success.

    Bodies that are not an envelope (arrays, empty, non-JSON) are left alone, as
    are codes inside the 2xx range.
    """
    stripped = text.lstrip()
    if not stripped.startswith("{"):
        return
    try:
        # A body starting with "{" can only decode to a mapping, so the shape
        # needs no second check once this succeeds.
        parsed = json.loads(stripped)
    except ValueError:
        return

    code = parsed.get("code")
    # bool is a subclass of int, and JSON `true` must not read as code 1.
    if isinstance(code, bool) or not isinstance(code, int):
        return
    if 200 <= code < 300:
        return
    raise BusinessError(code, text)


def sniff_json_prefix(data: bytes) -> str:
    """Return a binary body as text if it plausibly is a JSON envelope.

    Returns ``""`` for an empty, oversized or clearly-binary response, so the
    caller can skip envelope inspection without decoding a screenshot.
    """
    if not data or len(data) > ENVELOPE_SNIFF_BYTES:
        return ""
    if data.lstrip()[:1] != b"{":
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return ""


class HttpTransport:
    """Base URL, Bearer auth, query building, envelope inspection, error mapping.

    Platform methods are layered on top by the mixins in :mod:`devicebase.api`;
    :class:`~devicebase.http_client.DeviceBaseHttpClient` combines all of them.
    :meth:`request_json` and :meth:`request_bytes` are public so an endpoint
    without a typed method can still be reached.

    Args:
        base_url: API base URL. Falls back to ``DEVICEBASE_BASE_URL``, then
            :data:`DEFAULT_BASE_URL`.
        api_key: Bearer token. Falls back to ``DEVICEBASE_API_KEY``.
        timeout: Default deadline for a request, in seconds.

    Raises:
        AuthenticationError: If no API key is available.
    """

    #: Kept as a class attribute because the client classes that inherit this
    #: one have always exposed it there.
    DEFAULT_BASE_URL = DEFAULT_BASE_URL

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        # A trailing slash would turn every appended path into "//v1/…".
        resolved = base_url or os.environ.get("DEVICEBASE_BASE_URL") or DEFAULT_BASE_URL
        self._base_url = resolved.rstrip("/")
        self._api_key = api_key or os.environ.get("DEVICEBASE_API_KEY")

        if not self._api_key:
            raise AuthenticationError(
                "API key is required. Provide it via 'api_key' parameter "
                "or DEVICEBASE_API_KEY environment variable."
            )

        self._timeout = timeout
        # base_url is what makes the "/v1/…" paths below absolute; without it
        # httpx rejects them as URLs with no scheme.
        #
        # follow_redirects matches the Go and Node clients, which follow by
        # default. The mobile family is documented as redirecting /v1/{action}
        # onto the /api/* handlers; it answers directly today, so this is here
        # for the day that changes. _send still asserts the final status, so a
        # redirect that is not followed raises rather than passing a redirect
        # body off as the action's result.
        self._client = httpx.Client(
            base_url=self._base_url,
            headers=self._auth_headers(),
            timeout=timeout,
            follow_redirects=True,
        )

    def _auth_headers(self) -> dict[str, str]:
        """Build the default headers carrying the Bearer token."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _send(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Send a request and raise for anything but a 2xx status.

        ``timeout`` overrides the client-wide deadline for this call, which is
        how blocking actions get a deadline that covers however long the server
        is prepared to work.

        Raises:
            DeviceBaseError: If the request never completed — a timeout, a
                refused connection, a TLS failure. These are wrapped so the
                documented ``except DeviceBaseError`` handler, and the retry
                loops built on it, cover them too.
            DeviceBaseError: For any status outside 2xx, mapped by
                :func:`error_for_status`. That includes a redirect the client
                did not follow: its body is not the action's result, and
                returning it would report an action that never ran as a success.
        """
        request_kwargs: dict[str, Any] = {"params": _clean_params(params)}
        if body is not None:
            request_kwargs["json"] = body
        if timeout is not None:
            request_kwargs["timeout"] = timeout

        try:
            response = self._client.request(method, path, **request_kwargs)
        except httpx.HTTPError as exc:
            raise DeviceBaseError(f"Request failed: {exc}") from exc

        if response.status_code not in _SUCCESS_STATUS:
            detail = truncate(response.text) or response.reason_phrase
            raise error_for_status(response.status_code, detail)
        return response

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send a request and decode the JSON envelope it returns.

        Raises:
            DeviceBaseError: If the body is not valid JSON.
            BusinessError: If the envelope carries a non-2xx ``code``.
        """
        response = self._send(method, path, body=body, params=params, timeout=timeout)
        if not response.content:
            return {}
        try:
            decoded = response.json()
        except ValueError as exc:
            raise DeviceBaseError(
                f"Invalid JSON response: {truncate(response.text)}",
                response.status_code,
            ) from exc
        check_envelope(response.text)
        if not isinstance(decoded, dict):
            # An endpoint that answers with a bare list still decodes usefully.
            return {"data": decoded}
        return decoded

    def _operation(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> OperationResult:
        """Run a device action and wrap its payload as an OperationResult.

        Every action route answers with the same envelope shape, so the platform
        mixins share one wrapper rather than each defining their own — a private
        helper of the same name in two mixins would silently shadow itself
        through the MRO of :class:`~devicebase.http_client.DeviceBaseHttpClient`.
        """
        data = self.request_json(method, path, body=body, params=params, timeout=timeout)
        return OperationResult.from_dict(data)

    def request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> bytes:
        """Send a request and return the raw body, for endpoints answering bytes.

        The envelope is still inspected, so an action that failed inside an
        otherwise successful response is not handed back as image data.
        """
        response = self._send(method, path, params=params, timeout=timeout)
        content: bytes = response.content
        check_envelope(sniff_json_prefix(content))
        return content

    def close(self) -> None:
        """Close the HTTP client and release its connection pool."""
        self._client.close()

    def __enter__(self: _TransportT) -> _TransportT:
        """Context manager entry."""
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.close()


def _clean_params(params: dict[str, Any] | None) -> dict[str, str] | None:
    """Drop unset query values and stringify the rest.

    Selectors travel as query parameters on the browser read-only actions, and
    httpx escapes whatever it is handed, so an empty value only has to be left
    out rather than escaped.
    """
    if not params:
        return None
    cleaned = {
        key: str(value) for key, value in params.items() if value is not None and value != ""
    }
    return cleaned or None
