"""Error handling: the two failure layers, and recovering from them.

The API reports failures in two places, and only one of them is the HTTP status
line. An action that fails — a selector matching nothing, a device that went
offline — still answers HTTP 200 and carries the failure in the envelope:

    {"code": 502, "message": "-32602: Invalid parameters"}

Both layers raise here, so a caller that catches ``DeviceBaseError`` cannot
mistake a failed action for a successful one.

Run with:

    DEVICEBASE_API_KEY=… python examples/error_handling.py
"""

import time

from devicebase import (
    AuthenticationError,
    BusinessError,
    DeviceBaseClient,
    DeviceBaseError,
    DeviceNotFoundError,
    ValidationError,
    list_devices,
)

MISSING_SERIAL = "definitely-not-a-device"


def bad_api_key() -> None:
    """A rejected key is an HTTP 401, carrying the server's own message."""
    with DeviceBaseClient(serialno="x", api_key="invalid-key") as client:
        try:
            client.get_device_info()
        except AuthenticationError as exc:
            print(f"auth      HTTP {exc.status_code}: {exc.message[:70]}")


def wrong_serial() -> None:
    try:
        with DeviceBaseClient(serialno=MISSING_SERIAL, timeout=60.0) as client:
            client.get_device_info()
    except DeviceNotFoundError as exc:
        print(f"not found HTTP {exc.status_code}: {exc.message[:70]}")


def failed_action() -> None:
    """A failure inside a successful HTTP response."""
    devices = list_devices(limit=1)
    if not devices:
        print("no devices available")
        return

    with DeviceBaseClient(serialno=devices[0].serialno) as client:
        try:
            client.tap(1, 1)
        except BusinessError as exc:
            # status_code is None here: the transport succeeded, the action did
            # not. exc.code carries the envelope's code.
            print(f"business  code {exc.code} (HTTP {exc.status_code}): {exc.message[:60]}")
            print(f"          body: {exc.body[:80]}")
        except DeviceNotFoundError as exc:
            print(f"not found HTTP {exc.status_code}: {exc.message[:70]}")


def one_handler_for_everything() -> None:
    """Every error here is a DeviceBaseError, so the specific ones go first.

    ValidationError and DeviceNotFoundError are siblings, and both are caught
    by DeviceBaseError — catching the base class first would swallow them.
    """
    try:
        with DeviceBaseClient(serialno=MISSING_SERIAL, timeout=60.0) as client:
            client.get_device_info()
    except ValidationError as exc:
        print(f"validation: {exc.message[:70]}")
    except DeviceNotFoundError as exc:
        print(f"not found: {exc.message[:70]}")  # this one fires
    except DeviceBaseError as exc:
        print(f"other: {exc.message[:70]}")


def rejected_argument() -> None:
    """A bad argument is rejected locally, before anything is sent.

    It raises the SDK's own ValidationError rather than a bare ValueError, so
    the same ``except DeviceBaseError`` above covers it. ``status_code`` is None
    — no request was made.
    """
    with DeviceBaseClient(base_url="https://api.devicebase.cn", api_key="unused") as client:
        try:
            client.http.computer_scroll("pc-1", "diagonal")  # type: ignore[arg-type]
        except ValidationError as exc:
            # status_code is None: rejected locally, so no request was made.
            where = f"HTTP {exc.status_code}" if exc.status_code else "local"
            print(f"rejected  {where}: {exc.message[:70]}")


def retry_with_backoff(max_attempts: int = 3, delay: float = 1.0) -> None:
    """Retry a call that fails because the device is not ready.

    Only transient failures are worth retrying. A ``ValidationError`` means the
    request itself is malformed and will fail identically every time.
    """
    devices = list_devices(limit=1)
    if not devices:
        print("no devices available")
        return

    with DeviceBaseClient(serialno=devices[0].serialno) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                client.get_device_info()
            except DeviceBaseError as exc:
                print(f"attempt {attempt}/{max_attempts}: {type(exc).__name__}")
                if attempt == max_attempts:
                    print("giving up")
                    return
                time.sleep(delay * 2 ** (attempt - 1))  # exponential backoff
            else:
                print(f"attempt {attempt}: ok")
                return


if __name__ == "__main__":
    print("=== Rejected API key ===")
    bad_api_key()

    print("\n=== Unknown serialno ===")
    wrong_serial()

    print("\n=== Action failure inside HTTP 200 ===")
    failed_action()

    print("\n=== Rejected argument ===")
    rejected_argument()

    print("\n=== Catch order ===")
    one_handler_for_everything()

    print("\n=== Retry ===")
    retry_with_backoff()
