"""Low-level touch control via WebSocket (minitouch)."""

import asyncio

from devicebase import DeviceBaseClient


async def basic_touch():
    """Basic tap and swipe using MinitouchClient."""
    client = DeviceBaseClient(serialno="device123")
    minitouch = client.minitouch_client()

    async with minitouch:
        # Tap at coordinates
        await minitouch.tap(540, 960)

        # Swipe from bottom to top
        await minitouch.swipe(540, 1600, 540, 400, duration_ms=500)

        # Multi-point gestures
        # Two-finger zoom simulation
        await minitouch.touch_down(0, 300, 960)
        await minitouch.touch_down(1, 780, 960)
        await minitouch.commit()

        # Move fingers apart
        for i in range(10):
            await minitouch.touch_move(0, 300 - i * 20, 960)
            await minitouch.touch_move(1, 780 + i * 20, 960)
            await minitouch.commit()
            await asyncio.sleep(0.02)

        await minitouch.touch_up(0)
        await minitouch.touch_up(1)
        await minitouch.commit()

    print("Touch sequence completed")
    client.close()


async def drag_and_drop():
    """Drag and drop gesture simulation."""
    client = DeviceBaseClient(serialno="device123")
    minitouch = client.minitouch_client()

    start_x, start_y = 540, 1600
    end_x, end_y = 540, 400

    async with minitouch:
        # Touch down
        await minitouch.touch_down(0, start_x, start_y)
        await minitouch.commit()

        # Move in steps (simulate drag)
        steps = 20
        for i in range(1, steps + 1):
            progress = i / steps
            x = int(start_x + (end_x - start_x) * progress)
            y = int(start_y + (end_y - start_y) * progress)
            await minitouch.touch_move(0, x, y)
            await minitouch.commit()
            await asyncio.sleep(0.02)  # 20ms between steps

        # Touch up
        await minitouch.touch_up(0, end_x, end_y)
        await minitouch.commit()

    print("Drag completed")
    client.close()


if __name__ == "__main__":
    asyncio.run(basic_touch())
