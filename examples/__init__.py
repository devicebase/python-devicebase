"""Usage examples for the DeviceBase Python SDK.

Every example discovers its device rather than hard-coding a serial, so they run
against any account that has one:

    python examples/discovery.py             # finding a serial (start here)
    python examples/device_control.py        # mobile: touch, apps, text, shell
    python examples/browser_automation.py    # browser over CDP
    python examples/computer_control.py      # desktop: mouse, keyboard, host shell
    python examples/screenshot_hierarchy.py  # cross-family screenshots + UI tree
    python examples/error_handling.py        # both failure layers
    python examples/context_manager.py       # lifecycle, and multi-device use
    python examples/async_stream.py          # async frame streaming
    python examples/websocket_minicap.py     # real-time screen streaming
    python examples/websocket_minitouch.py   # low-level touch control

They read ``DEVICEBASE_API_KEY`` from the environment, and optionally
``DEVICEBASE_BASE_URL``. Run one as a module so imports resolve:

    DEVICEBASE_API_KEY=… python -m examples.discovery
"""

__all__: list[str] = []
