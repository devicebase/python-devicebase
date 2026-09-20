"""Browser platform API (Chrome / Chromium / Edge over CDP).

Path family: ``POST/GET /api/browser/{serialno}/{action...}``.

``serialno`` is the platform serialno of a registered browser device — the
``serialno`` field from :meth:`~devicebase.api.device.DeviceApi.list_devices`
with ``type="browser"``. Selectors are CSS selectors.

The read-only actions (``state``, ``tabs``, ``text``, ``attribute``,
``exists``) carry no body; their arguments travel as query parameters.
"""

from __future__ import annotations

from devicebase.models import InputTextRequest, OperationResult
from devicebase.transport import HttpTransport, escape_path_segment


def browser_path(action: str, serialno: str) -> str:
    """Build ``/api/browser/{serialno}/{action}``."""
    return f"/api/browser/{escape_path_segment(serialno)}/{action}"


class BrowserApi(HttpTransport):
    """Browser actions, each taking the device serialno explicitly."""

    # --- Navigation -------------------------------------------------------

    def browser_navigate(self, serialno: str, url: str) -> OperationResult:
        """Navigate the current tab to a URL."""
        return self._operation("POST", browser_path("navigate", serialno), body={"url": url})

    def browser_refresh(self, serialno: str) -> OperationResult:
        """Reload the current page."""
        return self._operation("POST", browser_path("refresh", serialno))

    def browser_go_back(self, serialno: str) -> OperationResult:
        """Go back in the browser history."""
        return self._operation("POST", browser_path("go_back", serialno))

    def browser_go_forward(self, serialno: str) -> OperationResult:
        """Go forward in the browser history."""
        return self._operation("POST", browser_path("go_forward", serialno))

    # --- Text -------------------------------------------------------------

    def browser_input(self, serialno: str, text: str) -> OperationResult:
        """Insert text into the page's focused element.

        Uses CDP ``Input.insertText``, which is reliable for CJK unlike
        synthesised key events.
        """
        return self._operation(
            "POST", browser_path("input", serialno), body=InputTextRequest(text=text).to_dict()
        )

    # --- DOM --------------------------------------------------------------

    def browser_click(self, serialno: str, selector: str) -> OperationResult:
        """Click the element matching a CSS selector."""
        return self._operation("POST", browser_path("click", serialno), body={"selector": selector})

    def browser_fill(self, serialno: str, selector: str, value: str) -> OperationResult:
        """Clear an input and type a value into it."""
        return self._operation(
            "POST", browser_path("fill", serialno), body={"selector": selector, "value": value}
        )

    def browser_select(self, serialno: str, selector: str, value: str) -> OperationResult:
        """Pick an option in a dropdown."""
        return self._operation(
            "POST", browser_path("select", serialno), body={"selector": selector, "value": value}
        )

    def browser_text(self, serialno: str, selector: str) -> OperationResult:
        """Get an element's text content."""
        return self._operation("GET", browser_path("text", serialno), params={"selector": selector})

    def browser_attribute(self, serialno: str, selector: str, attribute: str) -> OperationResult:
        """Get one attribute of an element."""
        return self._operation(
            "GET",
            browser_path("attribute", serialno),
            params={"selector": selector, "attribute": attribute},
        )

    def browser_exists(self, serialno: str, selector: str) -> OperationResult:
        """Report whether an element is present."""
        return self._operation(
            "GET", browser_path("exists", serialno), params={"selector": selector}
        )

    def browser_execute(self, serialno: str, script: str) -> OperationResult:
        """Evaluate JavaScript in the page.

        Danger tier: the script runs with the page's own privileges, which is the
        same reach as shell access to the browser profile.
        """
        return self._operation("POST", browser_path("execute", serialno), body={"script": script})

    def browser_hotkey(self, serialno: str, keys: list[str]) -> OperationResult:
        """Press the given keys together, e.g. ``["Meta", "a"]``.

        Editing shortcuts act on the page. Browser-chrome shortcuts such as
        ``Control+t`` are not reachable, because CDP drives the page rather than
        the browser UI.
        """
        return self._operation("POST", browser_path("hotkey", serialno), body={"keys": keys})

    # --- State ------------------------------------------------------------

    def browser_state(self, serialno: str) -> OperationResult:
        """Get the current URL, title, viewport size and tab count."""
        return self._operation("GET", browser_path("state", serialno))

    def browser_tabs(self, serialno: str) -> OperationResult:
        """List the open tabs."""
        return self._operation("GET", browser_path("tabs", serialno))

    # --- Tabs -------------------------------------------------------------

    def browser_tab_open(self, serialno: str, url: str) -> OperationResult:
        """Open a new tab at a URL."""
        return self._operation("POST", browser_path("tab/open", serialno), body={"url": url})

    def browser_tab_close(self, serialno: str, tab_id: str) -> OperationResult:
        """Close one tab."""
        return self._operation("POST", browser_path("tab/close", serialno), body={"tab_id": tab_id})

    def browser_tab_close_all(self, serialno: str) -> OperationResult:
        """Close every tab."""
        return self._operation("POST", browser_path("tab/close_all", serialno))

    def browser_tab_switch(self, serialno: str, tab_id: str) -> OperationResult:
        """Focus one tab."""
        return self._operation(
            "POST", browser_path("tab/switch", serialno), body={"tab_id": tab_id}
        )

    # --- Lifecycle --------------------------------------------------------

    def browser_launch(self, serialno: str) -> OperationResult:
        """Start the browser / CDP endpoint.

        Returns a connectable CDP URL for the session.
        """
        return self._operation("POST", browser_path("launch", serialno))

    def browser_close(self, serialno: str) -> OperationResult:
        """Stop the browser / CDP endpoint."""
        return self._operation("POST", browser_path("close", serialno))
