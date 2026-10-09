"""Per-platform API mixins.

Each module layers one platform's actions onto :class:`~devicebase.transport.HttpTransport`:

======================  ==============================================================
Platform                Path family
======================  ==============================================================
:mod:`~devicebase.api.mobile`    ``/v1/{action}/{serialno}``
:mod:`~devicebase.api.browser`   ``/api/browser/{serialno}/{action...}``
:mod:`~devicebase.api.computer`  ``/api/computer/{serialno}/{action}``
:mod:`~devicebase.api.device`    ``/v1/devices``
:mod:`~devicebase.api.cloud_browser`  ``/v1/browser/*``
======================  ==============================================================

:class:`~devicebase.http_client.DeviceBaseHttpClient` composes all five, so
their methods are reached as ``client.tap(...)``, ``client.browser_click(...)``
and so on.
"""

from devicebase.api.browser import BrowserApi, browser_path
from devicebase.api.cloud_browser import CloudBrowserApi, cloud_browser_path
from devicebase.api.computer import ComputerApi, bash_timeout, computer_path, wait_timeout
from devicebase.api.device import DeviceApi
from devicebase.api.mobile import MobileApi, mobile_path

__all__ = [
    "BrowserApi",
    "CloudBrowserApi",
    "ComputerApi",
    "DeviceApi",
    "MobileApi",
    "bash_timeout",
    "browser_path",
    "cloud_browser_path",
    "computer_path",
    "mobile_path",
    "wait_timeout",
]
