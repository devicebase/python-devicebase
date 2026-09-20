"""Screenshots and UI hierarchy inspection.

Screenshots are cross-family: one route serves all three platforms, and the
server dispatches it by device type (computer → full desktop, browser → CDP,
otherwise the device's image queue). So the same call captures a phone, a
browser tab or a whole desktop.

Run with:

    DEVICEBASE_API_KEY=… python examples/screenshot_hierarchy.py
"""

from devicebase import DeviceBaseHttpClient, list_devices


def main() -> None:
    devices = list_devices(limit=1)
    if not devices:
        print("No device available on this account.")
        return
    serial = devices[0].serial

    with DeviceBaseHttpClient() as client:
        # --- Screenshot as raw JPEG bytes ---
        screenshot = client.get_screenshot(serial)
        with open("screenshot.jpg", "wb") as handle:
            handle.write(screenshot)
        print(f"Screenshot: {len(screenshot)} bytes")

        # The server chooses the format, so do not decode these as PNG.
        assert screenshot[:2] == b"\xff\xd8", "expected JPEG"

        # --- A second route, returning the image as a file attachment ---
        # GET /v1/screenshot/{serial}; the cross-family /v1/screen above is the
        # one every platform shares.
        attachment = client.download_screenshot(serial)
        with open(f"{serial}_screenshot.jpg", "wb") as handle:
            handle.write(attachment)

        # --- Screenshot + hierarchy is the usual automation loop ---
        # Capture, find the element you want in the tree, then act on its
        # coordinates. The hierarchy carries pixel bounds for every node.
        hierarchy = client.dump_hierarchy(serial)
        print(f"Hierarchy payload: {len(str(hierarchy.data))} chars")

        # On a browser or computer serial, dump_hierarchy is not available —
        # use browser_state/browser_text or computer_screen_size instead.
        # Screenshots are the part that is genuinely shared.


if __name__ == "__main__":
    main()
