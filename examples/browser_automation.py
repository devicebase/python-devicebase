"""Browser automation (Chrome / Chromium / Edge over CDP).

Browser actions live on :class:`DeviceBaseHttpClient`, not on the serialno-bound
:class:`DeviceBaseClient`, because every one of them takes the serialno per call
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
    serialno = browsers[0].serialno
    print(f"Driving browser {serialno}")

    with DeviceBaseHttpClient() as client:
        # --- Lifecycle ---
        # browser_launch starts the CDP endpoint and returns a connectable URL.
        print(client.browser_launch(serialno).payload)

        # --- Navigation ---
        client.browser_navigate(serialno, "https://example.com")
        client.browser_refresh(serialno)
        client.browser_go_back(serialno)
        client.browser_go_forward(serialno)

        # --- State ---
        state = client.browser_state(serialno)
        print(f"URL: {state.payload.get('url')} title: {state.payload.get('title')}")

        for tab in client.browser_tabs(serialno).payload.get("tabs", []):
            print(f"  tab {tab.get('id')}: {tab.get('url')}")

        # --- DOM ---
        # Selectors are CSS selectors.
        if client.browser_exists(serialno, "h1").payload.get("exists"):
            print(f"h1 text: {client.browser_text(serialno, 'h1').payload}")

        print(f"href: {client.browser_attribute(serialno, 'a', 'href').payload}")

        client.browser_click(serialno, "a")
        client.browser_fill(serialno, "#search", "devicebase")
        client.browser_select(serialno, "select#country", "CN")

        # Free-form input goes through CDP Input.insertText, which is reliable
        # for CJK unlike synthesised key events.
        client.browser_input(serialno, "你好")

        # --- Keyboard ---
        # Editing shortcuts act on the page. Browser-chrome shortcuts such as
        # Control+t are not reachable — CDP drives the page, not the browser UI.
        client.browser_hotkey(serialno, ["Meta", "a"])

        # --- JavaScript ---
        # Danger tier: the script runs with the page's own privileges, which is
        # the same reach as shell access to the browser profile.
        print(client.browser_execute(serialno, "document.title").payload)

        # --- Tabs ---
        client.browser_tab_open(serialno, "https://example.org")
        client.browser_tab_switch(serialno, "1")
        client.browser_tab_close(serialno, "1")
        client.browser_tab_close_all(serialno)

        # A selector that matches nothing is reported inside a successful HTTP
        # response, so it raises BusinessError rather than being returned.
        try:
            client.browser_click(serialno, "#does-not-exist")
        except BusinessError as exc:
            print(f"click failed as expected: code={exc.code} {exc.message[:80]}")

        client.browser_close(serialno)


if __name__ == "__main__":
    main()
