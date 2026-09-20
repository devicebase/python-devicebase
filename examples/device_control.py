"""Mobile control (Android / HarmonyOS / iOS): touch, navigation, text, shell.

Run with:

    DEVICEBASE_API_KEY=… python examples/device_control.py
"""

from devicebase import DeviceBaseClient, list_devices


def main() -> None:
    mobiles = list_devices(device_type="mobile", limit=1)
    if not mobiles:
        print("No mobile device available on this account.")
        return
    serial = mobiles[0].serial

    # The serial is bound once here; every mobile call below fills it in.
    with DeviceBaseClient(serial=serial) as client:
        # --- Device info ---
        info = client.get_device_info()
        print(f"Device: {info.data.get('data')}")

        # --- Touch ---
        client.tap(x=540, y=960)  # single tap, centre of the screen
        client.double_tap(x=540, y=960)
        client.long_press(x=540, y=960)  # opens a context menu
        client.swipe(x1=540, y1=1600, x2=540, y2=400)  # swipe up

        # --- Navigation ---
        client.back()
        client.home()

        # --- Apps ---
        client.launch_app("华为商城")
        current = client.get_current_app()
        print(f"Foreground app: {current.data.get('data')}")
        client.stop_app("华为商城")
        client.stop_current_app()

        # --- Text ---
        client.input_text("Hello World")
        client.clear_text()

        # --- UI hierarchy ---
        hierarchy = client.dump_hierarchy()
        print(f"Hierarchy payload: {len(str(hierarchy.data))} chars")

        # --- Shell (adb/hdc platforms only) ---
        result = client.bash("getprop ro.product.model")
        # A command's own exit status is a result, not an error: it says the
        # command failed, not that the API call did.
        print(f"exitCode={result.payload.get('exitCode')} out={result.payload.get('stdout')}")

        # --- Install ---
        # app_path is a path on the *agent host*, not a local file.
        # install = client.install_app("/data/local/tmp/app.apk")
        # status = client.install_status(install.payload["install_id"])


if __name__ == "__main__":
    main()
