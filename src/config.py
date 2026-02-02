import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv(".env.local")


@dataclass
class Config:
    """Configuration class for the voice agent backend"""

    # LiveKit
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str

    # AI Services
    deepgram_api_key: str
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment: str
    azure_openai_api_version: str
    cartesia_api_key: str

    # Avatar
    avatar_provider: str  # "beyond_presence" or "tavus"
    avatar_api_key: str
    avatar_id: str

    # Database
    supabase_url: str
    supabase_key: str

    # Business Logic
    working_hours_start: int = 9
    working_hours_end: int = 17
    appointment_duration: int = 30
    available_times: List[str] = field(
        default_factory=lambda: ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]
    )

    @classmethod
    def from_env(cls):
        """Create configuration from environment variables"""
        return cls(
            livekit_url=os.getenv("LIVEKIT_URL", ""),
            livekit_api_key=os.getenv("LIVEKIT_API_KEY", ""),
            livekit_api_secret=os.getenv("LIVEKIT_API_SECRET", ""),
            deepgram_api_key=os.getenv("DEEPGRAM_API_KEY", ""),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", ""),
            azure_openai_api_version=os.getenv(
                "AZURE_OPENAI_API_VERSION", "2024-10-01-preview"
            ),
            cartesia_api_key=os.getenv("CARTESIA_API_KEY", ""),
            avatar_provider=os.getenv("AVATAR_PROVIDER", "beyond_presence"),
            avatar_api_key=os.getenv("BEYOND_PRESENCE_API_KEY"),
            avatar_id=os.getenv("AVATAR_ID", ""),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_key=os.getenv("SUPABASE_KEY", ""),
        )


# Global config instance
config = Config.from_env()
