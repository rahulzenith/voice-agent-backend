"""Service for emitting real-time events to frontend via LiveKit data messages."""
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from livekit import rtc

logger = logging.getLogger(__name__)


class EventService:
    """
    Emit real-time events to frontend via LiveKit data channel.
    
    Methods:
    - emit_tool_call(): Send tool execution status (started/success/error)
    - emit_summary(): Send final call summary with costs and appointments
    """

    @staticmethod
    async def emit_tool_call(
        room: Optional[rtc.Room],
        tool_name: str,
        status: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """
        Send tool execution event to frontend.
        
        Args:
            room: LiveKit room (if None, event skipped)
            tool_name: Tool name (e.g., "book_appointment")
            status: "started", "success", or "error"
            data: Event payload (results or error details)
        """
        if not room:
            return
            
        event = {
            "type": "tool_call",
            "tool": tool_name,
            "status": status,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            await room.local_participant.publish_data(
                json.dumps(event).encode("utf-8"),
                reliable=True
            )
        except Exception as e:
            logger.error(f"Failed to emit tool event: {e}")

    @staticmethod
    async def emit_summary(
        room: Optional[rtc.Room],
        summary: str,
        appointments: List[Dict[str, Any]],
        user_preferences: Dict[str, Any],
        cost_breakdown: Optional[Dict[str, float]] = None,
        duration_seconds: int = 0
    ):
        """
        Send final call summary to frontend.
        
        Args:
            room: LiveKit room (if None, event skipped)
            summary: Human-readable summary text
            appointments: List of scheduled appointments
            user_preferences: Learned preferences (time/day)
            cost_breakdown: Cost details by service
            duration_seconds: Total call duration
        """
        if not room:
            return
            
        event = {
            "type": "call_summary",
            "summary": summary,
            "appointments": appointments,
            "user_preferences": user_preferences,
            "cost_breakdown": cost_breakdown,
            "duration_seconds": duration_seconds,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            await room.local_participant.publish_data(
                json.dumps(event).encode("utf-8"),
                reliable=True
            )
        except Exception as e:
            logger.error(f"Failed to emit summary: {e}")
