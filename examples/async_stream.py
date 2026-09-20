"""Async streaming with frame processing pipeline."""

import asyncio
import base64
import os
from datetime import datetime

from devicebase import DeviceBaseClient


async def process_frame(frame: bytes, index: int) -> dict:
    """Process a single frame (simulate analysis)."""
    return {
        "index": index,
        "size": len(frame),
        "timestamp": datetime.now().isoformat(),
    }


async def stream_with_save(output_dir: str = "frames"):
    """Stream frames and save to disk."""
    os.makedirs(output_dir, exist_ok=True)

    client = DeviceBaseClient(serialno="device123")
    frame_count = 0

    try:
        async for frame in client.stream_minicap():
            # Save frame
            filename = f"{output_dir}/frame_{frame_count:06d}.jpg"
            with open(filename, "wb") as f:
                f.write(frame)

            # Process frame
            info = await process_frame(frame, frame_count)
            print(f"[{info['timestamp']}] Frame {frame_count}: {info['size']} bytes")

            frame_count += 1

            # Stop after 100 frames
            if frame_count >= 100:
                break

    finally:
        client.close()

    print(f"Saved {frame_count} frames to {output_dir}/")


async def stream_with_interval(fps: float = 5.0):
    """Stream frames at a fixed interval (not full speed)."""
    client = DeviceBaseClient(serialno="device123")
    interval = 1.0 / fps
    frame_count = 0

    try:
        async for frame in client.stream_minicap():
            # Process frame
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp}] Frame {frame_count}: {len(frame)} bytes")

            frame_count += 1

            # Wait for next frame interval
            await asyncio.sleep(interval)

            if frame_count >= 20:  # Capture 20 frames at specified FPS
                break

    finally:
        client.close()

    print(f"Captured {frame_count} frames at {fps} FPS")


async def stream_encode_base64():
    """Stream frames encoded as base64 (for API transmission)."""
    client = DeviceBaseClient(serialno="device123")
    frame_count = 0

    async for frame in client.stream_minicap():
        # Encode as base64 for transmission
        encoded = base64.b64encode(frame).decode("utf-8")

        # Simulate sending to API
        print(f"Frame {frame_count}: {len(encoded)} base64 chars")

        frame_count += 1
        if frame_count >= 5:
            break

    client.close()


if __name__ == "__main__":
    print("=== Stream and Save ===")
    asyncio.run(stream_with_save())

    print("\n=== Stream at Interval ===")
    asyncio.run(stream_with_interval(fps=5.0))

    print("\n=== Base64 Encode ===")
    asyncio.run(stream_encode_base64())
