"""WebSocket clients for real-time device streams and control."""

from __future__ import annotations

import asyncio
import os
import struct
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatus

from devicebase.errors import AuthenticationError, DeviceBaseError, DeviceNotFoundError
from devicebase.transport import escape_path_segment

if TYPE_CHECKING:
    from websockets.asyncio.client import ClientConnection as WebSocketClientProtocol


def _handshake_status(exc: InvalidStatus) -> int | None:
    """Read the HTTP status from a rejected WebSocket handshake.

    ``websockets`` puts the response on ``exc.response``; there is no
    ``status_code`` attribute on the exception itself, so reading one directly
    would silently never match and every rejection would be reported as a
    generic connection failure.
    """
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return status_code if isinstance(status_code, int) else None


def _device_refused(exc: InvalidStatus, serial: str) -> DeviceBaseError | None:
    """Map a handshake rejection onto the error it actually means."""
    if _handshake_status(exc) == 408:
        # The server answers 408 when the device is registered but not
        # connected: the request timed out waiting for it.
        return DeviceNotFoundError(f"Device '{serial}' not found or not connected")
    return None


class MinicapClient:
    """WebSocket client for minicap protocol screen streaming.

    This client connects to the minicap WebSocket endpoint and receives
    real-time JPEG frames from the device screen.

    Protocol format: Banner(24 bytes) + FrameData(4 bytes size + JPEG data)

    Example:
        ```python
        client = MinicapClient("ws://localhost:3410", "device123", "api-key")

        async for frame in client.stream_frames():
            # frame is bytes containing JPEG image
            with open("screenshot.jpg", "wb") as f:
                f.write(frame)
        ```
    """

    BANNER_SIZE = 24
    FRAME_HEADER_SIZE = 4

    def __init__(
        self,
        base_url: str,
        serial: str,
        api_key: str | None = None,
    ) -> None:
        """Initialize the minicap client.

        Args:
            base_url: The WebSocket base URL (ws:// or wss://).
            serial: The device unique identifier.
            api_key: JWT API key. If not provided, reads from DEVICEBASE_API_KEY.

        Raises:
            AuthenticationError: If no API key is available.
        """
        self._serial = serial
        self._api_key = api_key or os.environ.get("DEVICEBASE_API_KEY")

        if not self._api_key:
            raise AuthenticationError(
                "API key is required. Provide it via 'api_key' parameter "
                "or DEVICEBASE_API_KEY environment variable."
            )

        # Convert http:// to ws:// if needed
        ws_base = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self._url = f"{ws_base}/v1/minicap/{escape_path_segment(serial)}"

    async def stream_frames(self) -> AsyncIterator[bytes]:
        """Stream JPEG frames from the device.

        Yields:
            JPEG image bytes for each frame.

        Raises:
            DeviceNotFoundError: If the device is not found or not connected.
            DeviceBaseError: For connection or protocol errors.
        """
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            async with websockets.connect(self._url, additional_headers=headers) as ws:
                # Read and parse banner (24 bytes)
                banner = await ws.recv()
                if isinstance(banner, str):
                    banner = banner.encode()

                if len(banner) < self.BANNER_SIZE:
                    raise DeviceBaseError("Invalid minicap banner received")

                # Banner format (simplified - just skip it)
                # Version(1) + HeaderSize(1) + PID(4) + RealWidth(4) + RealHeight(4)
                # + VirtualWidth(4) + VirtualHeight(4) + Orientation(1) + Quirk(1)

                # Now read frames continuously
                while True:
                    # Read frame header (4 bytes = frame size)
                    header_data = await ws.recv()
                    if isinstance(header_data, str):
                        header_data = header_data.encode()

                    if len(header_data) < self.FRAME_HEADER_SIZE:
                        continue

                    # Parse frame size (big-endian uint32)
                    frame_size = struct.unpack(">I", header_data[: self.FRAME_HEADER_SIZE])[0]

                    # Read frame data
                    frame_data = b""
                    while len(frame_data) < frame_size:
                        chunk = await ws.recv()
                        if isinstance(chunk, str):
                            chunk = chunk.encode()
                        frame_data += chunk

                    yield frame_data[:frame_size]

        except InvalidStatus as e:
            raise _device_refused(e, self._serial) or DeviceBaseError(
                f"WebSocket connection failed: {e}"
            ) from e
        except ConnectionClosed as e:
            raise DeviceBaseError(f"WebSocket connection closed: {e}") from e
        except Exception as e:
            raise DeviceBaseError(f"Minicap stream error: {e}") from e

    async def capture_frame(self) -> bytes:
        """Capture a single frame from the stream.

        Returns:
            JPEG image bytes.

        Raises:
            DeviceBaseError: If no frame is received from the stream.
        """
        frame: bytes | None = None
        async for f in self.stream_frames():
            frame = f
            break
        if frame is None:
            raise DeviceBaseError("No frame received from stream")
        return frame


class MinitouchClient:
    """WebSocket client for minitouch protocol touch control.

    This client connects to the minitouch WebSocket endpoint and sends
    touch event commands to control the device.

    Supported commands:
    - `d <id> <x> <y> <pressure> <width> <height>` - Touch down
    - `m <id> <x> <y> <pressure> <width> <height>` - Touch move
    - `u <id> <x> <y> <pressure> <width> <height>` - Touch up
    - `c` - Commit events

    Example:
        ```python
        client = MinitouchClient("ws://localhost:3410", "device123", "api-key")
        await client.connect()

        # Tap at coordinates (100, 200)
        await client.touch_down(0, 100, 200)
        await client.commit()
        await client.touch_up(0, 100, 200)
        await client.commit()

        await client.close()
        ```
    """

    def __init__(
        self,
        base_url: str,
        serial: str,
        api_key: str | None = None,
    ) -> None:
        """Initialize the minitouch client.

        Args:
            base_url: The WebSocket base URL (ws:// or wss://).
            serial: The device unique identifier.
            api_key: JWT API key. If not provided, reads from DEVICEBASE_API_KEY.

        Raises:
            AuthenticationError: If no API key is available.
        """
        self._serial = serial
        self._api_key = api_key or os.environ.get("DEVICEBASE_API_KEY")

        if not self._api_key:
            raise AuthenticationError(
                "API key is required. Provide it via 'api_key' parameter "
                "or DEVICEBASE_API_KEY environment variable."
            )

        # Convert http:// to ws:// if needed
        ws_base = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self._url = f"{ws_base}/v1/minitouch/{escape_path_segment(serial)}"
        self._websocket: WebSocketClientProtocol | None = None

    async def connect(self) -> None:
        """Establish the WebSocket connection.

        Raises:
            DeviceNotFoundError: If the device is not found.
            DeviceBaseError: If connection fails.
        """
        if self._websocket is not None:
            return

        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            self._websocket = await websockets.connect(self._url, additional_headers=headers)
        except InvalidStatus as e:
            raise _device_refused(e, self._serial) or DeviceBaseError(
                f"WebSocket connection failed: {e}"
            ) from e

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._websocket is not None:
            await self._websocket.close()
            self._websocket = None

    async def __aenter__(self) -> MinitouchClient:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

    def _ensure_connected(self) -> WebSocketClientProtocol:
        """Ensure the WebSocket is connected."""
        if self._websocket is None:
            raise DeviceBaseError("WebSocket not connected. Call connect() first.")
        return self._websocket

    async def _send_command(self, command: str) -> str:
        """Send a command and return the response.

        Returns:
            Response string ("OK\n" or "ERROR: <message>\n").
        """
        ws = self._ensure_connected()
        await ws.send(command)
        response = await ws.recv()
        return response if isinstance(response, str) else response.decode()

    async def touch_down(
        self,
        contact_id: int,
        x: int,
        y: int,
        pressure: int = 50,
        width: int = 0,
        height: int = 0,
    ) -> str:
        """Send a touch down event.

        Args:
            contact_id: Touch contact identifier (0-9).
            x: X coordinate.
            y: Y coordinate.
            pressure: Touch pressure (0-65535).
            width: Touch width.
            height: Touch height.

        Returns:
            Server response ("OK\n" on success).
        """
        command = f"d {contact_id} {x} {y} {pressure} {width} {height}\n"
        return await self._send_command(command)

    async def touch_move(
        self,
        contact_id: int,
        x: int,
        y: int,
        pressure: int = 50,
        width: int = 0,
        height: int = 0,
    ) -> str:
        """Send a touch move event.

        Args:
            contact_id: Touch contact identifier (0-9).
            x: X coordinate.
            y: Y coordinate.
            pressure: Touch pressure (0-65535).
            width: Touch width.
            height: Touch height.

        Returns:
            Server response ("OK\n" on success).
        """
        command = f"m {contact_id} {x} {y} {pressure} {width} {height}\n"
        return await self._send_command(command)

    async def touch_up(
        self,
        contact_id: int,
        x: int = 0,
        y: int = 0,
        pressure: int = 0,
        width: int = 0,
        height: int = 0,
    ) -> str:
        """Send a touch up event.

        Args:
            contact_id: Touch contact identifier (0-9).
            x: X coordinate (optional).
            y: Y coordinate (optional).
            pressure: Touch pressure.
            width: Touch width.
            height: Touch height.

        Returns:
            Server response ("OK\n" on success).
        """
        command = f"u {contact_id} {x} {y} {pressure} {width} {height}\n"
        return await self._send_command(command)

    async def commit(self) -> str:
        """Commit all pending touch events.

        This must be called after sending touch commands for them to take effect.

        Returns:
            Server response ("OK\n" on success).
        """
        return await self._send_command("c\n")

    async def tap(self, x: int, y: int, duration_ms: float = 50) -> None:
        """Perform a complete tap gesture.

        This is a convenience method that sends down, commit, wait, up, commit.

        Args:
            x: X coordinate.
            y: Y coordinate.
            duration_ms: How long to hold the tap (milliseconds).
        """
        await self.touch_down(0, x, y)
        await self.commit()
        await asyncio.sleep(duration_ms / 1000.0)
        await self.touch_up(0, x, y)
        await self.commit()

    async def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: float = 300,
        steps: int = 10,
    ) -> None:
        """Perform a swipe gesture.

        This is a convenience method that interpolates touch move events.

        Args:
            x1: Starting X coordinate.
            y1: Starting Y coordinate.
            x2: Ending X coordinate.
            y2: Ending Y coordinate.
            duration_ms: Total swipe duration (milliseconds).
            steps: Number of intermediate move steps.
        """
        # Touch down at start
        await self.touch_down(0, x1, y1)
        await self.commit()

        # Interpolate movement
        step_delay = duration_ms / 1000.0 / steps
        for i in range(1, steps + 1):
            progress = i / steps
            x = int(x1 + (x2 - x1) * progress)
            y = int(y1 + (y2 - y1) * progress)
            await self.touch_move(0, x, y)
            await self.commit()
            await asyncio.sleep(step_delay)

        # Touch up at end
        await self.touch_up(0, x2, y2)
        await self.commit()
