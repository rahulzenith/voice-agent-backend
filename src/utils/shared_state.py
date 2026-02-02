"""Shared state manager for agent session"""

from typing import Optional, Dict, Any
from livekit import rtc


class SharedState:
    """
    Singleton-like shared state for the agent session.
    Stores contact_number, room, and other session data that needs to persist across tool calls.
    """

    _instance: Optional["SharedState"] = None

    def __init__(self):
        self.contact_number: Optional[str] = None
        self.room: Optional[rtc.Room] = None
        self.participant: Optional[Any] = None  # Store the participant (for disconnect)
        self.session: Optional[Any] = (
            None  # Store the AgentSession (for chat context access)
        )
        self.usage_collector: Optional[Any] = (
            None  # LiveKit UsageCollector for metrics-based cost tracking
        )
        self.tool_calls: list = []
        self.conversation_messages: list = []  # Track full conversation (user + agent messages) - FALLBACK ONLY
        self.session_start_time: Optional[Any] = None
        self.user_preferences: Dict[
            str, Any
        ] = {}  # Track preferences mentioned during conversation
        self.data: Dict[str, Any] = {}

    @classmethod
    def get_instance(cls) -> "SharedState":
        """Get or create the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the shared state (for new sessions)"""
        cls._instance = None

    def set_contact_number(self, number: str):
        """Store the identified user's contact number"""
        self.contact_number = number

    def get_contact_number(self) -> Optional[str]:
        """Get the stored contact number"""
        return self.contact_number

    def set_room(self, room: rtc.Room):
        """Store the LiveKit room instance"""
        self.room = room

    def get_room(self) -> Optional[rtc.Room]:
        """Get the LiveKit room instance"""
        return self.room

    def set_participant(self, participant: Any):
        """Store the participant instance"""
        self.participant = participant

    def get_participant(self) -> Optional[Any]:
        """Get the participant instance"""
        return self.participant

    def set_session(self, session: Any):
        """Store the AgentSession instance"""
        self.session = session

    def get_session(self) -> Optional[Any]:
        """Get the AgentSession instance"""
        return self.session
