"""The HTTP client, covering all three device platforms.

Three device platforms are served, each with its own path family:

==============  ============================================  ==========================
Platform        Devices                                       Path family
==============  ============================================  ==========================
mobile          Android / HarmonyOS / iOS                     ``/v1/{action}/{serialno}``
browser         Chrome / Chromium / Edge over CDP              ``/api/browser/{serialno}/{action...}``
computer        macOS / Windows / Linux desktops               ``/api/computer/{serialno}/{action}``
==============  ============================================  ==========================

Every method takes the device serialno as its first argument, because a serialno is
only meaningful within one platform family. Use
:meth:`~devicebase.api.device.DeviceApi.list_devices` to discover them, then:

    ```python
    from devicebase import DeviceBaseHttpClient

    with DeviceBaseHttpClient() as client:
        browser = client.list_devices(device_type="browser")[0]
        client.browser_navigate(browser.serialno, "https://example.com")
        client.browser_click(browser.serialno, "#submit")
    ```

For a mobile device driven repeatedly, :class:`~devicebase.client.DeviceBaseClient`
binds the serialno once so it never has to be repeated.
"""

from __future__ import annotations

from devicebase.api import BrowserApi, ComputerApi, DeviceApi, MobileApi
from devicebase.errors import (
    AuthenticationError,
    BusinessError,
    DeviceBaseError,
    DeviceNotFoundError,
    ValidationError,
)

__all__ = [
    "AuthenticationError",
    "BrowserApi",
    "BusinessError",
    "ComputerApi",
    "DeviceApi",
    "DeviceBaseError",
    "DeviceBaseHttpClient",
    "DeviceNotFoundError",
    "MobileApi",
    "ValidationError",
]


class DeviceBaseHttpClient(BrowserApi, ComputerApi, DeviceApi, MobileApi):
    """HTTP client exposing the whole API surface.

    It is safe to reuse across devices: every method takes the serialno
    explicitly, so one client with one connection pool can drive many devices.

    Args:
        base_url: API base URL. Falls back to ``DEVICEBASE_BASE_URL``, then
            ``https://api.devicebase.cn``.
        api_key: Bearer token. Falls back to ``DEVICEBASE_API_KEY``.
        timeout: Default deadline for a request, in seconds. Blocking actions
            (``computer_wait``, ``computer_bash``) widen it per call.

    Raises:
        AuthenticationError: If no API key is available.

    Example:
        ```python
        client = DeviceBaseHttpClient(base_url="http://localhost:3410", api_key="…")
        info = client.get_device_info("EDGER9DE2GFD03XH-001")
        client.close()
        ```
    """
