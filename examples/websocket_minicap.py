"""Real-time screen streaming via WebSocket (minicap)."""

import asyncio

from devicebase import DeviceBaseClient


async def stream_screen():
    """Stream and display device screen frames."""
    client = DeviceBaseClient(serialno="device123")

    # Use the high-level stream method
    frame_count = 0
    async for frame in client.stream_minicap():
        # Save frame to file
        with open(f"frame_{frame_count:04d}.jpg", "wb") as f:
            f.write(frame)

        frame_count += 1
        if frame_count >= 10:  # Capture 10 frames
            break

        print(f"Frame {frame_count}: {len(frame)} bytes")

    print(f"Captured {frame_count} frames")
    client.close()


async def capture_single():
    """Capture a single frame from the stream."""
    client = DeviceBaseClient(serialno="device123")

    # Using minicap_client for more control
    minicap = client.minicap_client()

    frame = await minicap.capture_frame()
    with open("capture.jpg", "wb") as f:
        f.write(frame)

    print(f"Captured: {len(frame)} bytes")
    client.close()


if __name__ == "__main__":
    asyncio.run(stream_screen())
