"""Client lifecycle, and driving two platforms from one process.

Both clients are context managers, so the connection pool is closed for you.
DeviceBaseClient is a bound view of one serialno; DeviceBaseHttpClient holds the
full surface and takes a serialno per call, which is what a multi-device script
wants.

Run with:

    DEVICEBASE_API_KEY=… python examples/context_manager.py
"""

from devicebase import DeviceBaseClient, DeviceBaseHttpClient, list_devices


def basic_context_manager() -> None:
    devices = list_devices(device_type="mobile", limit=1)
    if not devices:
        print("No mobile device available.")
        return

    with DeviceBaseClient(serialno=devices[0].serialno) as client:
        info = client.get_device_info()
        print(f"Device: {info.serialno}")
        client.tap(x=540, y=960)
        print(f"Screenshot: {len(client.get_screenshot())} bytes")
    # The connection pool is closed here.


def discovery_then_control() -> None:
    """Look the serialno up first; it is not something to hard-code."""
    with DeviceBaseHttpClient() as client:
        for device in client.list_devices(limit=5):
            print(f"  {device.serialno:32} {device.type:10} {device.state}")


def two_platforms_one_process() -> None:
    """Screenshots are the one action every platform shares."""
    with DeviceBaseHttpClient() as client:
        for device in client.list_devices(limit=3):
            try:
                image = client.get_screenshot(device.serialno)
            except Exception as exc:  # noqa: BLE001 - an example, kept short
                print(f"  {device.serialno}: {type(exc).__name__}")
            else:
                print(f"  {device.serialno}: {len(image)} bytes")


def automation_workflow() -> None:
    devices = list_devices(device_type="mobile", limit=1)
    if not devices:
        print("No mobile device available.")
        return

    with DeviceBaseClient(serialno=devices[0].serialno) as client:
        client.launch_app("com.example.testapp")
        client.tap(x=540, y=960)
        client.input_text("test input")
        client.tap(x=540, y=1800)  # submit

        with open("result.jpg", "wb") as handle:
            handle.write(client.get_screenshot())
        print("Result screenshot written to result.jpg")

        client.home()


if __name__ == "__main__":
    print("=== Bound client ===")
    basic_context_manager()

    print("\n=== Discovery ===")
    discovery_then_control()

    print("\n=== One client, several devices ===")
    two_platforms_one_process()

    print("\n=== Workflow ===")
    automation_workflow()
