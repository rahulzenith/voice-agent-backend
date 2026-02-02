"""Service for managing WebRTC call lifecycle and graceful termination."""

import logging
import asyncio
from livekit import rtc

logger = logging.getLogger(__name__)


class CallService:
    """
    Handle WebRTC call disconnection with delay for message delivery.

    Methods:
    - schedule_disconnect(): Wait specified seconds, then disconnect
    """

    @staticmethod
    async def schedule_disconnect(room: rtc.Room, delay_seconds: int = 8) -> None:
        """
        Disconnect from room after delay (ensures message delivery).

        Args:
            room: LiveKit room to disconnect from
            delay_seconds: Seconds to wait before disconnect (default: 8)
        """
        await asyncio.sleep(delay_seconds)

        try:
            await room.disconnect()
            logger.info("Room disconnected successfully")
        except Exception as e:
            logger.error(f"Error disconnecting from room: {e}")
