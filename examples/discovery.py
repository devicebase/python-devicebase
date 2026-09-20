"""Finding a device: the call every other example starts with.

A serial is discovered, never guessed, and it is only meaningful within one
platform family — a mobile serial cannot drive a browser endpoint.

Run with:

    DEVICEBASE_API_KEY=… python examples/discovery.py
"""

from devicebase import list_devices


def main() -> None:
    print("All devices:")
    for device in list_devices(limit=20):
        print(
            f"  {device.serial:32} {device.type:10} {device.os_type:12} "
            f"{device.state:8} {device.display_name}"
        )

    # The `type` filter takes either a category bucket or a system type. A
    # category covers every system in it: mobile = Android + HarmonyOS + iOS.
    print("\nMobiles only:")
    for device in list_devices(device_type="mobile", limit=5):
        print(f"  {device.serial} ({device.os_type} {device.os_version})")

    # A system type is narrower — these resolve against the device's os_type,
    # because a row only carries the coarse type.
    print("\nChrome browsers only:")
    for device in list_devices(device_type="chrome", limit=5):
        print(f"  {device.serial} ({device.os_type})")

    # state is one of busy / free / offline.
    print("\nFree devices only:")
    for device in list_devices(state="free", limit=5):
        print(f"  {device.serial} ({device.type})")

    # Serial numbers are short-lived in the sense that a device can be
    # reassigned; look one up rather than hard-coding it.
    devices = list_devices(device_type="mobile", limit=1)
    if devices:
        print(f"\nFirst mobile: {devices[0].serial}")


if __name__ == "__main__":
    main()
