"""Errors raised by the DeviceBase SDK.

The API reports failures through two layers, and both are surfaced here:

* **Transport** — the HTTP status is non-2xx. :attr:`DeviceBaseError.status_code`
  carries it and the server's own body is kept in the message, so a specific
  complaint like ``设备不存在`` survives instead of being replaced by a label.
* **Business** — HTTP 200 with a non-2xx ``code`` inside the response envelope.
  :class:`BusinessError` carries that code. The control API answers action
  failures this way (a browser selector that matches nothing returns
  ``{"code":502,...}``), so guarding on the status line alone reports failure as
  success.

Example:
    ```python
    from devicebase import BusinessError, DeviceBaseClient, DeviceNotFoundError

    try:
        client.browser_click(serialno, "#submit")
    except DeviceNotFoundError:
        ...  # the serialno is wrong, or the device is offline
    except BusinessError as exc:
        print(exc.code, exc.body)  # the action itself failed
    ```
"""

from __future__ import annotations

#: Cap on the body text kept in an error message. A failed action's envelope is
#: small; this only guards against a misrouted binary response being pasted into
#: a log.
MAX_ERROR_BODY_CHARS = 4096


def truncate(body: str) -> str:
    """Bound a response body so it cannot flood a log or a stack trace."""
    if len(body) <= MAX_ERROR_BODY_CHARS:
        return body
    return body[:MAX_ERROR_BODY_CHARS] + "… (truncated)"


class DeviceBaseError(Exception):
    """Base error for every DeviceBase SDK failure.

    Attributes:
        message: The formatted error text, also available as ``str(exc)``.
        status_code: The HTTP status the failure came from, when there was one.
            ``None`` for an error raised from the response envelope, since the
            transport itself succeeded.
        code: The envelope's ``code`` for a :class:`BusinessError`, else ``None``.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class DeviceNotFoundError(DeviceBaseError):
    """The device is not found or not connected (HTTP 404)."""


class ValidationError(DeviceBaseError):
    """The server rejected the request parameters (HTTP 400 or 422)."""


class AuthenticationError(DeviceBaseError):
    """The API key is missing, or the server rejected it (HTTP 401)."""


class BusinessError(DeviceBaseError):
    """The API answered with a success status but failed inside the envelope.

    The control API returns HTTP 200 with a non-2xx ``code`` for action
    failures — a browser selector that matches nothing, a computer command the
    host refused to run. Guarding on the HTTP status alone would report those as
    success.

    Attributes:
        code: The envelope's ``code``, e.g. ``502``.
        body: The raw response body, which carries the server's own message.
    """

    def __init__(self, code: int, body: str) -> None:
        super().__init__(f"API error (code {code}): {truncate(body)}", None, code)
        self.body = body
