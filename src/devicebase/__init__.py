"""DeviceBase Python SDK for device automation.

Three device platforms are covered:

* **mobile** — Android / HarmonyOS / iOS, driven through the ``/v1/*`` actions
* **browser** — Chrome / Chromium / Edge over CDP, on ``/api/browser/*``
* **computer** — macOS / Windows / Linux desktops, on ``/api/computer/*``

Two clients are available. :class:`DeviceBaseClient` binds one serial and fills
it into every mobile call. :class:`DeviceBaseHttpClient` takes the serial per
call, and is where the browser and computer action families live.

Example:
    ```python
    from devicebase import DeviceBaseClient

    with DeviceBaseClient(serial="EDGER9DE2GFD03XH-001") as client:
        client.tap(100, 200)
        client.get_screenshot()
    ```
"""

from devicebase.client import DeviceBaseClient, list_devices
from devicebase.errors import (
    AuthenticationError,
    BusinessError,
    DeviceBaseError,
    DeviceNotFoundError,
    ValidationError,
)
from devicebase.http_client import DeviceBaseHttpClient
from devicebase.models import (
    MOUSE_BUTTONS,
    SCROLL_DIRECTIONS,
    AppInfo,
    Bounds,
    Device,
    DeviceInfo,
    HierarchyInfo,
    InputTextRequest,
    LaunchAppRequest,
    MouseButton,
    OperationResult,
    Point,
    ScrollDirection,
)
from devicebase.websocket_client import MinicapClient, MinitouchClient

__version__ = "2026.4.21"

__all__ = [
    # Clients
    "DeviceBaseClient",
    "DeviceBaseHttpClient",
    "list_devices",
    # Errors
    "AuthenticationError",
    "BusinessError",
    "DeviceBaseError",
    "DeviceNotFoundError",
    "ValidationError",
    # Models
    "MOUSE_BUTTONS",
    "SCROLL_DIRECTIONS",
    "AppInfo",
    "Bounds",
    "Device",
    "DeviceInfo",
    "HierarchyInfo",
    "InputTextRequest",
    "LaunchAppRequest",
    "MouseButton",
    "OperationResult",
    "Point",
    "ScrollDirection",
    # WebSocket clients
    "MinicapClient",
    "MinitouchClient",
]
