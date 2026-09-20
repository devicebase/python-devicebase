"""Browser automation (Chrome / Chromium / Edge over CDP).

Browser actions live on :class:`DeviceBaseHttpClient`, not on the serial-bound
:class:`DeviceBaseClient`, because every one of them takes the serial per call
— one client drives many browsers.

Run with:

    DEVICEBASE_API_KEY=… python examples/browser_automation.py
"""

from devicebase import BusinessError, DeviceBaseHttpClient, list_devices


def main() -> None:
    browsers = list_devices(device_type="browser", limit=1)
    if not browsers:
        print("No browser device available on this account.")
        return
    serial = browsers[0].serial
    print(f"Driving browser {serial}")

    with DeviceBaseHttpClient() as client:
        # --- Lifecycle ---
        # browser_launch starts the CDP endpoint and returns a connectable URL.
        print(client.browser_launch(serial).payload)

        # --- Navigation ---
        client.browser_navigate(serial, "https://example.com")
        client.browser_refresh(serial)
        client.browser_go_back(serial)
        client.browser_go_forward(serial)

        # --- State ---
        state = client.browser_state(serial)
        print(f"URL: {state.payload.get('url')} title: {state.payload.get('title')}")

        for tab in client.browser_tabs(serial).payload.get("tabs", []):
            print(f"  tab {tab.get('id')}: {tab.get('url')}")

        # --- DOM ---
        # Selectors are CSS selectors.
        if client.browser_exists(serial, "h1").payload.get("exists"):
            print(f"h1 text: {client.browser_text(serial, 'h1').payload}")

        print(f"href: {client.browser_attribute(serial, 'a', 'href').payload}")

        client.browser_click(serial, "a")
        client.browser_fill(serial, "#search", "devicebase")
        client.browser_select(serial, "select#country", "CN")

        # Free-form input goes through CDP Input.insertText, which is reliable
        # for CJK unlike synthesised key events.
        client.browser_input(serial, "你好")

        # --- Keyboard ---
        # Editing shortcuts act on the page. Browser-chrome shortcuts such as
        # Control+t are not reachable — CDP drives the page, not the browser UI.
        client.browser_hotkey(serial, ["Meta", "a"])

        # --- JavaScript ---
        # Danger tier: the script runs with the page's own privileges, which is
        # the same reach as shell access to the browser profile.
        print(client.browser_execute(serial, "document.title").payload)

        # --- Tabs ---
        client.browser_tab_open(serial, "https://example.org")
        client.browser_tab_switch(serial, "1")
        client.browser_tab_close(serial, "1")
        client.browser_tab_close_all(serial)

        # A selector that matches nothing is reported inside a successful HTTP
        # response, so it raises BusinessError rather than being returned.
        try:
            client.browser_click(serial, "#does-not-exist")
        except BusinessError as exc:
            print(f"click failed as expected: code={exc.code} {exc.message[:80]}")

        client.browser_close(serial)


if __name__ == "__main__":
    main()
