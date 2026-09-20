"""Browser platform API (Chrome / Chromium / Edge over CDP).

Path family: ``POST/GET /api/browser/{serial}/{action...}``.

``serial`` is the platform serial of a registered browser device — the
``serial`` field from :meth:`~devicebase.api.device.DeviceApi.list_devices`
with ``type="browser"``. Selectors are CSS selectors.

The read-only actions (``state``, ``tabs``, ``text``, ``attribute``,
``exists``) carry no body; their arguments travel as query parameters.
"""

from __future__ import annotations

from devicebase.models import InputTextRequest, OperationResult
from devicebase.transport import HttpTransport, escape_path_segment


def browser_path(action: str, serial: str) -> str:
    """Build ``/api/browser/{serial}/{action}``."""
    return f"/api/browser/{escape_path_segment(serial)}/{action}"


class BrowserApi(HttpTransport):
    """Browser actions, each taking the device serial explicitly."""

    # --- Navigation -------------------------------------------------------

    def browser_navigate(self, serial: str, url: str) -> OperationResult:
        """Navigate the current tab to a URL."""
        return self._operation("POST", browser_path("navigate", serial), body={"url": url})

    def browser_refresh(self, serial: str) -> OperationResult:
        """Reload the current page."""
        return self._operation("POST", browser_path("refresh", serial))

    def browser_go_back(self, serial: str) -> OperationResult:
        """Go back in the browser history."""
        return self._operation("POST", browser_path("go_back", serial))

    def browser_go_forward(self, serial: str) -> OperationResult:
        """Go forward in the browser history."""
        return self._operation("POST", browser_path("go_forward", serial))

    # --- Text -------------------------------------------------------------

    def browser_input(self, serial: str, text: str) -> OperationResult:
        """Insert text into the page's focused element.

        Uses CDP ``Input.insertText``, which is reliable for CJK unlike
        synthesised key events.
        """
        return self._operation(
            "POST", browser_path("input", serial), body=InputTextRequest(text=text).to_dict()
        )

    # --- DOM --------------------------------------------------------------

    def browser_click(self, serial: str, selector: str) -> OperationResult:
        """Click the element matching a CSS selector."""
        return self._operation("POST", browser_path("click", serial), body={"selector": selector})

    def browser_fill(self, serial: str, selector: str, value: str) -> OperationResult:
        """Clear an input and type a value into it."""
        return self._operation(
            "POST", browser_path("fill", serial), body={"selector": selector, "value": value}
        )

    def browser_select(self, serial: str, selector: str, value: str) -> OperationResult:
        """Pick an option in a dropdown."""
        return self._operation(
            "POST", browser_path("select", serial), body={"selector": selector, "value": value}
        )

    def browser_text(self, serial: str, selector: str) -> OperationResult:
        """Get an element's text content."""
        return self._operation("GET", browser_path("text", serial), params={"selector": selector})

    def browser_attribute(self, serial: str, selector: str, attribute: str) -> OperationResult:
        """Get one attribute of an element."""
        return self._operation(
            "GET",
            browser_path("attribute", serial),
            params={"selector": selector, "attribute": attribute},
        )

    def browser_exists(self, serial: str, selector: str) -> OperationResult:
        """Report whether an element is present."""
        return self._operation("GET", browser_path("exists", serial), params={"selector": selector})

    def browser_execute(self, serial: str, script: str) -> OperationResult:
        """Evaluate JavaScript in the page.

        Danger tier: the script runs with the page's own privileges, which is the
        same reach as shell access to the browser profile.
        """
        return self._operation("POST", browser_path("execute", serial), body={"script": script})

    def browser_hotkey(self, serial: str, keys: list[str]) -> OperationResult:
        """Press the given keys together, e.g. ``["Meta", "a"]``.

        Editing shortcuts act on the page. Browser-chrome shortcuts such as
        ``Control+t`` are not reachable, because CDP drives the page rather than
        the browser UI.
        """
        return self._operation("POST", browser_path("hotkey", serial), body={"keys": keys})

    # --- State ------------------------------------------------------------

    def browser_state(self, serial: str) -> OperationResult:
        """Get the current URL, title, viewport size and tab count."""
        return self._operation("GET", browser_path("state", serial))

    def browser_tabs(self, serial: str) -> OperationResult:
        """List the open tabs."""
        return self._operation("GET", browser_path("tabs", serial))

    # --- Tabs -------------------------------------------------------------

    def browser_tab_open(self, serial: str, url: str) -> OperationResult:
        """Open a new tab at a URL."""
        return self._operation("POST", browser_path("tab/open", serial), body={"url": url})

    def browser_tab_close(self, serial: str, tab_id: str) -> OperationResult:
        """Close one tab."""
        return self._operation("POST", browser_path("tab/close", serial), body={"tab_id": tab_id})

    def browser_tab_close_all(self, serial: str) -> OperationResult:
        """Close every tab."""
        return self._operation("POST", browser_path("tab/close_all", serial))

    def browser_tab_switch(self, serial: str, tab_id: str) -> OperationResult:
        """Focus one tab."""
        return self._operation("POST", browser_path("tab/switch", serial), body={"tab_id": tab_id})

    # --- Lifecycle --------------------------------------------------------

    def browser_launch(self, serial: str) -> OperationResult:
        """Start the browser / CDP endpoint.

        Returns a connectable CDP URL for the session.
        """
        return self._operation("POST", browser_path("launch", serial))

    def browser_close(self, serial: str) -> OperationResult:
        """Stop the browser / CDP endpoint."""
        return self._operation("POST", browser_path("close", serial))
