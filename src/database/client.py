"""Supabase client setup and helper functions"""

import logging
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Singleton Supabase client"""

    _instance: Optional[Client] = None

    @classmethod
    def get_client(
        cls, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None
    ) -> Client:
        """
        Get or create Supabase client instance

        Args:
            supabase_url: Supabase project URL (required for first initialization)
            supabase_key: Supabase API key (required for first initialization)

        Returns:
            Client: Supabase client instance
        """
        if cls._instance is None:
            if not supabase_url or not supabase_key:
                raise ValueError(
                    "supabase_url and supabase_key are required for first initialization"
                )

            cls._instance = create_client(supabase_url, supabase_key)
            logger.info("Supabase client initialized")

        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the client instance (useful for testing)"""
        cls._instance = None
