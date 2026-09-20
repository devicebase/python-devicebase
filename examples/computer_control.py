"""Desktop control (macOS / Windows / Linux): mouse, keyboard, host shell.

Coordinates are absolute screen pixels, so ask the device for its screen size
before computing a position rather than assuming a resolution.

Run with:

    DEVICEBASE_API_KEY=… python examples/computer_control.py
"""

from devicebase import DeviceBaseHttpClient, list_devices


def main() -> None:
    computers = list_devices(device_type="computer", limit=1)
    if not computers:
        print("No computer device available on this account.")
        return
    serialno = computers[0].serialno
    os_type = computers[0].os_type
    # macOS uses Meta for the shortcuts that Windows and Linux put on Control.
    modifier = "Meta" if os_type.lower() == "macos" else "Control"
    print(f"Driving desktop {serialno} ({os_type})")

    with DeviceBaseHttpClient() as client:
        # --- Permissions first ---
        # Screen recording and accessibility are granted per application on
        # macOS, and a missing one shows up here rather than as a click that
        # silently does nothing.
        print(f"permissions: {client.computer_permissions(serialno).payload}")

        size = client.computer_screen_size(serialno).payload
        print(f"screen: {size}")
        width = int(size.get("width", 1920))
        height = int(size.get("height", 1080))
        centre_x, centre_y = width // 2, height // 2

        # --- Mouse ---
        client.computer_move(serialno, centre_x, centre_y)
        client.computer_click(serialno, centre_x, centre_y)
        client.computer_click(serialno, centre_x, centre_y, button="right")
        client.computer_double_click(serialno, centre_x, centre_y)
        # duration is in seconds; omitted, the driver picks its own.
        client.computer_long_click(serialno, centre_x, centre_y, duration=2)
        client.computer_drag(serialno, 100, 100, centre_x, centre_y)
        client.computer_scroll(serialno, "down", amount=3)

        print(f"pointer now at {client.computer_position(serialno).payload}")

        # --- Keyboard ---
        client.computer_type_text(serialno, "你好, world")
        client.computer_press(serialno, "Enter")
        client.computer_hotkey(serialno, [modifier, "c"])

        # --- Apps ---
        client.computer_launch_app(serialno, "Safari")  # a macOS example; name the
        # equivalent application per platform in real use

        # --- Blocking actions ---
        # Both widen the transport deadline past the shared 30s default, so a
        # long wait is not aborted client-side while the server is still working.
        client.computer_wait(serialno, 2000)  # milliseconds

        # computer_bash runs on the host as the desktop user, unsandboxed —
        # treat it as shell access. timeout_seconds is the server-side budget.
        result = client.computer_bash(serialno, "uname -a", timeout_seconds=30)
        print(f"exitCode={result.payload.get('exitCode')} out={result.payload.get('stdout')}")


if __name__ == "__main__":
    main()
