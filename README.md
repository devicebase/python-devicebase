# Devicebase Python SDK

Python SDK for the [Devicebase](https://devicebase.cn) device automation API, covering three device platforms:

| Platform | Devices | Client | Actions |
|----------|---------|--------|---------|
| **mobile** | Android, HarmonyOS, iOS | `DeviceBaseClient` (serialno-bound) or `DeviceBaseHttpClient` | 17 |
| **browser** | Chrome / Chromium / Edge over CDP | `DeviceBaseHttpClient` | 21 |
| **computer** | macOS / Windows / Linux desktops | `DeviceBaseHttpClient` | 15 |

Plus device discovery (`list_devices`) and two screenshot routes shared by all three platforms.

## Installation

```bash
pip install devicebase
```

Requires Python 3.10+.

## Quick start

```python
from devicebase import DeviceBaseClient, list_devices

# 1. Find a device. The serialno is discovered, never guessed.
serialno = list_devices(device_type="mobile", limit=1)[0].serialno

# 2. Bind it once and drive it.
with DeviceBaseClient(serialno=serialno) as client:
    client.tap(540, 960)
    client.swipe(540, 1600, 540, 400)
    client.launch_app("com.example.app")

    with open("screen.jpg", "wb") as f:
        f.write(client.get_screenshot())
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `DEVICEBASE_API_KEY` | yes | API key from https://www.devicebase.cn/ |
| `DEVICEBASE_BASE_URL` | no | API base URL (default `https://api.devicebase.cn`) |

Both can be passed to the constructor instead (`api_key=`, `base_url=`, `timeout=`).

## Two clients

**`DeviceBaseClient(serialno=…)`** is a serialno-bound view of one device. Every mobile action fills in the serialno, so a script never repeats it. `serialno` is optional — leave it off and the client can still call `list_devices`, which is how discovery works before a serialno is known.

**`DeviceBaseHttpClient()`** takes the serialno per call, and is where the browser and computer families live. One client with one connection pool drives as many devices as you like; reach it from a bound client with `client.http`.

Both are context managers and close their connection pool on exit.

## Discovery

```python
from devicebase import list_devices

list_devices()  # everything the key can see
list_devices(device_type="browser")  # a category
list_devices(device_type="chrome", limit=5)  # a system type
list_devices(state="free")  # busy / free / offline
list_devices(keyword="pixel")
```

A `Device` carries `serialno` (the identifier every call takes), `state`, `type`, `os_type`, `os_version`, `name`, `alias_name`, `model`, `brand`, `location`, `updated_at` and more.

`device_type` accepts a **category** (`mobile` / `browser` / `computer`) or a **system type** (`android` / `harmonyos` / `ios` / `macos` / `windows` / `linux` / `chrome` / `chromium` / `edge` / `other`). Both are forwarded verbatim as the `type` query parameter and resolved server-side.

> [!NOTE]
> On the deployment this SDK was verified against, `GET /v1/devices` applied `state` and `limit` but returned every device regardless of `keyword` or `type`. The SDK forwards the filters as documented and does not filter client-side, so check what comes back rather than assuming `type` narrowed the result.

## Mobile (Android / HarmonyOS / iOS)

Path family `/v1/{action}/{serialno}`. Available on both clients; the bound form drops the serialno argument.

| Area | Methods |
|------|---------|
| Info | `get_device_info` |
| Touch | `tap`, `double_tap`, `long_press`, `swipe` |
| Navigation | `back`, `home` |
| Apps | `launch_app`, `stop_app`, `stop_current_app`, `get_current_app` |
| Text | `input_text`, `clear_text` |
| Shell | `bash` (adb/hdc only) |
| State | `dump_hierarchy` |
| Install | `install_app`, `install_status` |

```python
with DeviceBaseClient(serialno=serialno) as client:
    client.bash("getprop ro.product.model")
    install = client.install_app("/data/local/tmp/app.apk")
    client.install_status(install.payload["install_id"])
```

`install_app` takes a path on the **agent host**, not a local file — the SDK does not upload the package.

## Browser (Chrome / Chromium / Edge over CDP)

Path family `/api/browser/{serialno}/{action}`. Selectors are CSS selectors. The read-only actions (`state`, `tabs`, `text`, `attribute`, `exists`) carry no body; their arguments travel as query parameters.

| Area | Methods |
|------|---------|
| Navigation | `browser_navigate`, `browser_refresh`, `browser_go_back`, `browser_go_forward` |
| DOM | `browser_click`, `browser_fill`, `browser_select`, `browser_text`, `browser_attribute`, `browser_exists`, `browser_execute` |
| Text | `browser_input` (CDP `Input.insertText`, reliable for CJK) |
| Keyboard | `browser_hotkey` |
| State | `browser_state`, `browser_tabs` |
| Tabs | `browser_tab_open`, `browser_tab_close`, `browser_tab_close_all`, `browser_tab_switch` |
| Lifecycle | `browser_launch`, `browser_close` |

```python
from devicebase import DeviceBaseHttpClient

with DeviceBaseHttpClient() as client:
    serialno = client.list_devices(device_type="browser")[0].serialno
    client.browser_navigate(serialno, "https://example.com")
    client.browser_click(serialno, "#submit")
    print(client.browser_state(serialno).payload)
```

> [!WARNING]
> `browser_execute` is **danger tier** — the script runs with the page's own privileges, the same reach as shell access to the browser profile.

Editing shortcuts (`Meta a`, `Control c`) act on the page. Browser-chrome shortcuts such as `Control t` are not reachable, because CDP drives the page rather than the browser UI.

## Computer (macOS / Windows / Linux)

Path family `/api/computer/{serialno}/{action}`. Coordinates are absolute screen pixels. `position`, `screen_size` and `permissions` are read-only.

| Area | Methods |
|------|---------|
| Mouse | `computer_click`, `computer_double_click`, `computer_long_click`, `computer_move`, `computer_drag`, `computer_scroll` |
| Keyboard | `computer_type_text`, `computer_press`, `computer_hotkey` |
| System | `computer_position`, `computer_screen_size`, `computer_permissions`, `computer_launch_app` |
| Blocking | `computer_wait` (milliseconds), `computer_bash` (timeout in seconds) |

```python
with DeviceBaseHttpClient() as client:
    serialno = client.list_devices(device_type="computer")[0].serialno
    size = client.computer_screen_size(serialno).payload
    client.computer_click(serialno, size["width"] // 2, size["height"] // 2)
    client.computer_click(serialno, 100, 100, button="right")
    client.computer_scroll(serialno, "down", amount=3)
```

> [!WARNING]
> `computer_bash` runs on the host machine as the desktop user, unsandboxed, under the platform default shell — treat it as shell access.

`computer_wait` and `computer_bash` widen the transport deadline past the 30s default, because the default would otherwise abort work the server is still doing and report a transport error for a call that would have succeeded.

`button` and `direction` are validated locally against `MOUSE_BUTTONS` and `SCROLL_DIRECTIONS` before anything is sent.

## Screenshots

```python
with DeviceBaseClient(serialno=serialno) as client:
    jpeg = client.get_screenshot()  # POST /v1/screen/{serialno}
    jpeg = client.download_screenshot()  # GET /v1/screenshot/{serialno}
```

`get_screenshot` is **cross-family**: the server dispatches `/v1/screen` by device type (computer → full-desktop capture, browser → CDP, otherwise the device's image queue), so one call serves all three platforms. The server chooses the format — JPEG today.

## Errors

The API reports failures in two places, and only one of them is the HTTP status line.

| Layer | Condition | Raised as |
|-------|-----------|-----------|
| Local | the SDK rejects an argument before sending | `ValidationError` (`status_code=None`) |
| Transport | the request never completed — timeout, refused, TLS | `DeviceBaseError` |
| Transport | HTTP 401 | `AuthenticationError` (`status_code=401`) |
| Transport | HTTP 404 | `DeviceNotFoundError` (`status_code=404`) |
| Transport | HTTP 400 / 422 | `ValidationError` |
| Transport | any other non-2xx, including an unfollowed redirect | `DeviceBaseError` |
| **Business** | **HTTP 200 with a non-2xx `code` in the envelope** | **`BusinessError` (`code`, `body`)** |

Every one of these is a `DeviceBaseError`, so a single handler covers all of them. `button=` and `direction=` are checked against `MOUSE_BUTTONS` and `SCROLL_DIRECTIONS` locally; a rejected argument carries no status code because nothing was sent.

A response that is not 2xx is never treated as the action's result. The client follows redirects (as the Go and Node clients do) and `_send` asserts the final status, so a redirect that was not followed raises rather than having its body decoded as a success.

The second layer is the one that is easy to miss. The control API answers action failures with a **success status** — a browser selector that matches nothing returns `{"code": 502, "message": "-32602: …"}` — so a client that only checks the status line reports failure as success. This SDK inspects the envelope on every response, including binary ones, so a failed action never comes back as image data.

```python
from devicebase import BusinessError, DeviceNotFoundError

try:
    client.browser_click(serialno, "#maybe-missing")
except DeviceNotFoundError:
    ...  # the serialno is wrong, or the device is offline
except BusinessError as exc:
    print(exc.code, exc.body)  # the action itself failed; status_code is None
```

Every error keeps the server's own message, so a specific complaint like `设备不存在: dev-1` survives instead of being replaced by a label. Bodies are truncated at 4096 characters.

### Return values

A successful call returns an `OperationResult` even when the *action* reports a non-zero status. A shell command exiting 1 arrives as:

```python
result = client.computer_bash(serialno, "exit 1")
result.success  # True — the API call succeeded
result.payload["exitCode"]  # 1 — the command's own status
result.data  # the whole envelope, code and message included
```

Use `.payload` for the action's result object; `.data` is the envelope around it.

## Migrating from 2026.4.21

This release adds the browser and computer platforms and changes a few things a 2026.4.21 caller would notice.

| Removed | Replacement |
|---------|-------------|
| `get_screenshot_post()` | `get_screenshot()` — it now POSTs to `/v1/screen/{serialno}`, like every other SDK |
| `get_mjpeg_stream()` | `minicap_client()` / `stream_minicap()`. `GET /v1/mjpeg/{serialno}` is not a route — it answers 404 |

### `serial` is renamed `serialno`

The device identifier is now spelled `serialno` everywhere, matching the field
name in the API contract and the other SDKs. The old spelling still works and
warns, so nothing breaks on upgrade:

| Was | Now | Old form |
|-----|-----|----------|
| `DeviceBaseClient(serial=…)` | `DeviceBaseClient(serialno=…)` | accepted, `DeprecationWarning` |
| `client.serial` | `client.serialno` | accepted, `DeprecationWarning` |
| `Device.serial` | `Device.serialno` | accepted, `DeprecationWarning` |
| `DeviceInfo.serial` | `DeviceInfo.serialno` | accepted, `DeprecationWarning` |
| every method's first argument | unchanged positionally | the parameter is now named `serialno` |

Passing both `serialno=` and `serial=` raises `ValidationError` rather than
silently picking one. The deprecated forms are removed in the next major
release.

`Device` also now reads the identifier from the `serialno` key **first**, with
`serial` as the fallback — the previous order depended on the fallback against
a server that sends only `serialno`.

`DEFAULT_BASE_URL` is still a class attribute on both clients, and `AuthenticationError` is still importable from `devicebase.client` as well as `devicebase.errors`.

Changed:

- `DeviceBaseClient(serialno=…)` — `serialno` is now optional, so `list_devices` works before a serialno is known. Positional and keyword use are unchanged.
- `list_devices(limit=0)` now raises `ValidationError`. Go omits a non-positive limit and Node sends it.
- `state="online"` was never a valid filter value; the API defines `busy`, `free` and `offline`.

Everything else — `get_device_info`, `tap`, `double_tap`, `long_press`, `swipe`, `back`, `home`, `launch_app`, `input_text`, `clear_text`, `get_current_app`, `dump_hierarchy`, `get_screenshot`, `download_screenshot`, and the `MinicapClient` / `MinitouchClient` classes — keeps its signature.

## WebSocket streaming

Real-time screen frames and low-level touch control:

```python
import asyncio


async def stream():
    with DeviceBaseClient(serialno=serialno) as client:
        async for frame in client.stream_minicap():
            with open("frame.jpg", "wb") as f:
                f.write(frame)


asyncio.run(stream())
```

```python
async with client.minitouch_client() as minitouch:
    await minitouch.tap(100, 200)
    await minitouch.swipe(0, 500, 500, 500, duration_ms=300)
```

A handshake rejected with `408` means the device is registered but not connected, and raises `DeviceNotFoundError`.

## Examples

Runnable scripts in [examples/](examples/) — each discovers its own device:

- [discovery.py](examples/discovery.py) — finding a serialno
- [device_control.py](examples/device_control.py) — mobile: touch, apps, text, shell
- [browser_automation.py](examples/browser_automation.py) — browser over CDP
- [computer_control.py](examples/computer_control.py) — desktop: mouse, keyboard, host shell
- [screenshot_hierarchy.py](examples/screenshot_hierarchy.py) — cross-family screenshots and the UI tree
- [error_handling.py](examples/error_handling.py) — both failure layers, and retry
- [context_manager.py](examples/context_manager.py) — lifecycle and multi-device use
- [websocket_minicap.py](examples/websocket_minicap.py), [websocket_minitouch.py](examples/websocket_minitouch.py), [async_stream.py](examples/async_stream.py)

## Development

```bash
uv venv && uv pip install -e '.[dev]'

pytest  # offline, hermetic
pytest --cov=devicebase
mypy src tests  # strict
ruff check . && ruff format --check .
```

Live tests are skipped by default and assert the SDK's behaviour against the real API:

```bash
DEVICEBASE_LIVE_TEST=1 DEVICEBASE_API_KEY=… pytest tests/test_live.py -v
```

### Troubleshooting

**Device calls fail with `HTTP 503: 请求失败: fetch failed` while `list_devices` works.**

If the machine has a system-wide HTTP proxy configured, `httpx` picks it up automatically (its `trust_env` default) and routes through it — including for `127.0.0.1`. Some proxies cause `httpx` to emit a duplicated `Connection` header, which the gateway rejects with a 503 that masks the real cause. Bypass the proxy for the Devicebase host:

```bash
export NO_PROXY=127.0.0.1,localhost,api.devicebase.cn
```

This is a client/proxy interaction rather than a Devicebase fault: `curl` and the Go client do not read the macOS system proxy settings, so they are unaffected on the same machine.

## License

MIT
