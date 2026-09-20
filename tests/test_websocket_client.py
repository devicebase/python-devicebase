"""Tests for the WebSocket clients.

The connection is faked rather than opened: these tests are about the protocol
handling the clients do — banner parsing, frame reassembly, touch command
framing and handshake-error mapping.

One consequence of faking is worth stating up front. ``stream_frames`` ends by
raising: when the peer closes, ``websockets`` raises ``ConnectionClosed`` and the
client converts it into a ``DeviceBaseError``. There is no clean end-of-stream,
so :func:`collect_frames` stops after the frames it wants and swallows that
error, which is exactly what a caller looping over live frames would do.
"""

from __future__ import annotations

import os
import struct
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import pytest
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.http11 import Response

from devicebase.errors import AuthenticationError, DeviceBaseError, DeviceNotFoundError
from devicebase.websocket_client import MinicapClient, MinitouchClient

SERIAL = "device123"


def invalid_status(code: int) -> InvalidStatus:
    """Build the handshake rejection websockets raises for a non-101 answer."""
    return InvalidStatus(Response(code, "rejected", Headers(), b""))


class FakeConnection:
    """A stand-in for a websockets client connection."""

    def __init__(self, incoming: list[bytes] | None = None) -> None:
        self._incoming = list(incoming or [])
        self.sent: list[str] = []
        self.closed = False

    async def recv(self) -> bytes:
        if self._incoming:
            return self._incoming.pop(0)
        raise ConnectionClosed(None, None)

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        self.closed = True

    async def __aenter__(self) -> FakeConnection:
        return self

    async def __aexit__(self, *args: object) -> None:
        self.closed = True


class FakeConnect:
    """Stands in for websockets.connect, which is both awaitable and a context manager."""

    def __init__(self, connection: FakeConnection | Exception) -> None:
        self.connection = connection
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, url: str, **kwargs: Any) -> FakeConnect:
        self.calls.append((url, kwargs))
        return self

    def __await__(self) -> Any:
        async def resolve() -> FakeConnection:
            if isinstance(self.connection, Exception):
                raise self.connection
            return self.connection

        return resolve().__await__()

    async def __aenter__(self) -> FakeConnection:
        if isinstance(self.connection, Exception):
            raise self.connection
        return self.connection

    async def __aexit__(self, *args: object) -> None:
        return None


def patch_connect(target: FakeConnect) -> Any:
    """Replace websockets.connect inside the client module."""
    return patch("devicebase.websocket_client.websockets.connect", target)


def banner() -> bytes:
    """A 24-byte minicap banner."""
    return struct.pack(">BBIIIIIBB", 1, 24, 1234, 1080, 1920, 1080, 1920, 0, 0)


def framed(payload: bytes) -> list[bytes]:
    """A frame as the protocol sends it: a big-endian size, then the data."""
    return [struct.pack(">I", len(payload)), payload]


async def collect_frames(client: MinicapClient, limit: int) -> list[bytes]:
    """Collect up to ``limit`` frames, then stop.

    The stream ends by raising once the fake connection is drained; that, and
    a plain end of iteration, both count as "no more frames" here.
    """
    frames: list[bytes] = []
    stream = client.stream_frames().__aiter__()
    try:
        while len(frames) < limit:
            frames.append(await stream.__anext__())
    except (StopAsyncIteration, DeviceBaseError):
        pass
    return frames


async def drain(client: MinicapClient) -> list[bytes]:
    """Iterate the stream to its end, letting any error propagate.

    Contrast with :func:`collect_frames`: these are the tests where the error
    *is* the subject, so it must not be swallowed.
    """
    return [frame async for frame in client.stream_frames()]


class TestInit:
    """Client construction."""

    def test_minicap_explicit_params(self) -> None:
        client = MinicapClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
        assert client._serial == SERIAL
        assert client._api_key == "k"
        assert client._url == f"ws://test.com/v1/minicap/{SERIAL}"

    def test_minicap_converts_http_to_ws(self) -> None:
        client = MinicapClient(base_url="http://test.com", serial=SERIAL, api_key="k")
        assert client._url == f"ws://test.com/v1/minicap/{SERIAL}"

    def test_minitouch_converts_https_to_wss(self) -> None:
        client = MinitouchClient(base_url="https://test.com", serial=SERIAL, api_key="k")
        assert client._url == f"wss://test.com/v1/minitouch/{SERIAL}"

    def test_minicap_env_var(self) -> None:
        with patch.dict(os.environ, {"DEVICEBASE_API_KEY": "env-key"}):
            client = MinicapClient(base_url="ws://test.com", serial=SERIAL)
            assert client._api_key == "env-key"

    @pytest.mark.parametrize("client_class", [MinicapClient, MinitouchClient])
    def test_missing_api_key_raises(self, client_class: type[Any]) -> None:
        with patch.dict(os.environ, {}, clear=True), pytest.raises(AuthenticationError):
            client_class(base_url="ws://test.com", serial=SERIAL)


class TestMinicapStream:
    """Minicap banner parsing and frame reassembly."""

    async def test_streams_reassembled_frames(self) -> None:
        first, second = b"\xff\xd8first", b"\xff\xd8second"
        connection = FakeConnection([banner(), *framed(first), *framed(second)])
        with patch_connect(FakeConnect(connection)):
            client = MinicapClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
            frames = await collect_frames(client, 2)

        assert frames == [first, second]

    async def test_splits_a_frame_across_messages(self) -> None:
        payload = b"\xff\xd8abcdefgh"
        half = len(payload) // 2
        connection = FakeConnection(
            [banner(), struct.pack(">I", len(payload)), payload[:half], payload[half:]]
        )
        with patch_connect(FakeConnect(connection)):
            client = MinicapClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
            frames = await collect_frames(client, 1)

        assert frames == [payload]

    async def test_skips_a_stub_frame_header(self) -> None:
        # A message shorter than the 4-byte header is skipped, not treated as a
        # zero-length frame.
        payload = b"\xff\xd8real"
        connection = FakeConnection([banner(), b"\x00", *framed(payload)])
        with patch_connect(FakeConnect(connection)):
            client = MinicapClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
            frames = await collect_frames(client, 1)

        assert frames == [payload]

    async def test_sends_the_bearer_token(self) -> None:
        connect = FakeConnect(FakeConnection([banner()]))
        with patch_connect(connect):
            client = MinicapClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
            # Asking for one frame is what makes the generator start and
            # connect; the banner arrives, then the fake stream runs dry.
            assert await collect_frames(client, 1) == []

        url, kwargs = connect.calls[0]
        assert url == f"ws://test.com/v1/minicap/{SERIAL}"
        assert kwargs["additional_headers"] == {"Authorization": "Bearer k"}

    async def test_short_banner_is_rejected(self) -> None:
        connection = FakeConnection([b"short"])
        with patch_connect(FakeConnect(connection)):
            client = MinicapClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
            with pytest.raises(DeviceBaseError, match="Invalid minicap banner"):
                await drain(client)

    async def test_capture_frame_returns_the_first(self) -> None:
        payload = b"\xff\xd8only"
        connection = FakeConnection([banner(), *framed(payload)])
        with patch_connect(FakeConnect(connection)):
            client = MinicapClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
            assert await client.capture_frame() == payload

    async def test_capture_frame_reports_a_stream_with_no_frames(self) -> None:
        with patch_connect(FakeConnect(FakeConnection([banner()]))):
            client = MinicapClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
            with pytest.raises(DeviceBaseError):
                await client.capture_frame()


class TestHandshakeErrors:
    """A rejected handshake is mapped onto the error it actually means."""

    async def test_408_is_a_missing_device(self) -> None:
        with patch_connect(FakeConnect(invalid_status(408))):
            client = MinicapClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
            with pytest.raises(DeviceNotFoundError) as exc_info:
                await drain(client)
        assert SERIAL in str(exc_info.value)

    async def test_other_statuses_are_generic_failures(self) -> None:
        with patch_connect(FakeConnect(invalid_status(401))):
            client = MinicapClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
            with pytest.raises(DeviceBaseError) as exc_info:
                await drain(client)
        assert not isinstance(exc_info.value, DeviceNotFoundError)
        assert "WebSocket connection failed" in str(exc_info.value)

    async def test_minitouch_maps_408_too(self) -> None:
        with patch_connect(FakeConnect(invalid_status(408))):
            client = MinitouchClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
            with pytest.raises(DeviceNotFoundError):
                await client.connect()

    async def test_a_closed_stream_is_reported(self) -> None:
        with patch_connect(FakeConnect(FakeConnection([banner()]))):
            client = MinicapClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
            with pytest.raises(DeviceBaseError, match="closed"):
                _ = [frame async for frame in client.stream_frames()]


@pytest.fixture
async def minitouch() -> AsyncIterator[tuple[MinitouchClient, FakeConnection]]:
    """A connected minitouch client over a fake connection."""
    connection = FakeConnection([b"OK\n"] * 32)
    with patch_connect(FakeConnect(connection)):
        client = MinitouchClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
        await client.connect()
        yield client, connection
        await client.close()


class TestMinitouchCommands:
    """Minitouch sends newline-terminated protocol lines."""

    async def test_ensure_connected_before_connect_raises(self) -> None:
        client = MinitouchClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
        with pytest.raises(DeviceBaseError, match="WebSocket not connected"):
            client._ensure_connected()

    async def test_touch_down_framing(
        self, minitouch: tuple[MinitouchClient, FakeConnection]
    ) -> None:
        client, connection = minitouch
        assert await client.touch_down(0, 100, 200, pressure=50) == "OK\n"
        assert connection.sent[-1] == "d 0 100 200 50 0 0\n"

    async def test_touch_move_and_up_framing(
        self, minitouch: tuple[MinitouchClient, FakeConnection]
    ) -> None:
        client, connection = minitouch
        await client.touch_move(1, 10, 20)
        assert connection.sent[-1] == "m 1 10 20 50 0 0\n"
        await client.touch_up(1, 10, 20)
        assert connection.sent[-1] == "u 1 10 20 0 0 0\n"

    async def test_commit_framing(self, minitouch: tuple[MinitouchClient, FakeConnection]) -> None:
        client, connection = minitouch
        assert await client.commit() == "OK\n"
        assert connection.sent[-1] == "c\n"

    async def test_connect_is_idempotent(
        self, minitouch: tuple[MinitouchClient, FakeConnection]
    ) -> None:
        client, _ = minitouch
        existing = client._websocket
        await client.connect()
        assert client._websocket is existing

    async def test_close_releases_the_connection(self) -> None:
        connection = FakeConnection([b"OK\n"])
        with patch_connect(FakeConnect(connection)):
            client = MinitouchClient(base_url="ws://test.com", serial=SERIAL, api_key="k")
            await client.connect()
            await client.close()
        assert connection.closed is True
        assert client._websocket is None

    async def test_context_manager_connects_and_closes(self) -> None:
        connection = FakeConnection([b"OK\n"])
        with patch_connect(FakeConnect(connection)):
            async with MinitouchClient(
                base_url="ws://test.com", serial=SERIAL, api_key="k"
            ) as client:
                assert client._websocket is not None
        assert connection.closed is True

    async def test_tap_sends_down_and_up(
        self, minitouch: tuple[MinitouchClient, FakeConnection]
    ) -> None:
        client, connection = minitouch
        await client.tap(100, 200, duration_ms=0)
        assert connection.sent == [
            "d 0 100 200 50 0 0\n",
            "c\n",
            "u 0 100 200 0 0 0\n",
            "c\n",
        ]

    async def test_swipe_interpolates_between_the_endpoints(
        self, minitouch: tuple[MinitouchClient, FakeConnection]
    ) -> None:
        client, connection = minitouch
        await client.swipe(0, 0, 100, 0, duration_ms=0, steps=2)
        moves = [line for line in connection.sent if line.startswith("m ")]
        assert moves == ["m 0 50 0 50 0 0\n", "m 0 100 0 50 0 0\n"]
        assert connection.sent[0] == "d 0 0 0 50 0 0\n"
        # Lifting the finger is followed by a commit, as every other gesture is.
        assert connection.sent[-2] == "u 0 100 0 0 0 0\n"
        assert connection.sent[-1] == "c\n"
