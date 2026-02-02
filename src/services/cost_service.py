"""Service for calculating API usage costs from LiveKit metrics."""

import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class CostService:
    """
    Calculate accurate costs from LiveKit UsageSummary.

    Methods:
    - calculate_from_usage_summary(): Apply pricing to actual usage metrics

    Pricing (January 2026):
    - Deepgram: $0.0043/min | Azure OpenAI: $0.0015/$0.002 per 1K tokens
    - Cartesia: $0.00001/char | Avatar: $0.006/min
    """

    # Pricing rates (January 2026 - update as providers change rates)
    DEEPGRAM_PER_MINUTE = 0.0043  # Per minute of audio transcribed
    AZURE_OPENAI_INPUT_PER_1K = 0.0015  # Per 1K input tokens
    AZURE_OPENAI_OUTPUT_PER_1K = 0.002  # Per 1K output tokens
    CARTESIA_PER_CHARACTER = 0.00001  # Per character synthesized
    AVATAR_PER_MINUTE = 0.006  # Per minute of session (avatar runs entire call)

    @staticmethod
    def calculate_from_usage_summary(
        usage_summary: Any, session_duration: int
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate costs from LiveKit UsageSummary.

        Args:
            usage_summary: LiveKit UsageSummary with actual usage metrics
            session_duration: Total call duration in seconds

        Returns:
            Dict with usage_summary (raw metrics) and cost breakdown by service
        """
        try:
            # Extract metrics from UsageSummary object
            stt_seconds = getattr(usage_summary, "stt_audio_duration", 0.0)
            llm_prompt_tokens = getattr(usage_summary, "llm_prompt_tokens", 0)
            llm_completion_tokens = getattr(usage_summary, "llm_completion_tokens", 0)
            tts_characters = getattr(usage_summary, "tts_characters_count", 0)

            # Calculate costs
            stt_cost = (stt_seconds / 60) * CostService.DEEPGRAM_PER_MINUTE
            llm_input_cost = (
                llm_prompt_tokens / 1000
            ) * CostService.AZURE_OPENAI_INPUT_PER_1K
            llm_output_cost = (
                llm_completion_tokens / 1000
            ) * CostService.AZURE_OPENAI_OUTPUT_PER_1K
            tts_cost = tts_characters * CostService.CARTESIA_PER_CHARACTER

            # Avatar cost (if avatar was used)
            avatar_cost = 0.0
            if session_duration > 0:
                avatar_minutes = session_duration / 60
                avatar_cost = avatar_minutes * CostService.AVATAR_PER_MINUTE

            total_cost = (
                stt_cost + llm_input_cost + llm_output_cost + tts_cost + avatar_cost
            )

            return {
                "usage_summary": {
                    "stt_seconds": round(stt_seconds, 2),
                    "llm_prompt_tokens": llm_prompt_tokens,
                    "llm_completion_tokens": llm_completion_tokens,
                    "tts_characters": tts_characters,
                    "session_duration": session_duration,
                },
                "total": round(total_cost, 4),
                "speech_recognition": round(stt_cost, 4),
                "ai_processing_input": round(llm_input_cost, 4),
                "ai_processing_output": round(llm_output_cost, 4),
                "voice_synthesis": round(tts_cost, 4),
                "avatar": round(avatar_cost, 4),
            }

        except Exception as e:
            logger.error(f"Error calculating costs: {e}")
            return {
                "usage_summary": usage_summary,
                "total": 0.0,
                "speech_recognition": 0.0,
                "ai_processing_input": 0.0,
                "ai_processing_output": 0.0,
                "voice_synthesis": 0.0,
                "avatar": 0.0,
            }
