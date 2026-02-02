"""Service for generating LLM-based conversation summaries."""

import logging
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from config import config

logger = logging.getLogger(__name__)


class SummaryService:
    """
    Generate professional summaries from conversation transcripts using LLM via LangChain.

    Methods:
    - generate_from_transcript(): Generate summary using LLM from transcript
    """

    @staticmethod
    async def generate_from_transcript(
        transcript: str, contact_number: str, appointments: list
    ) -> str:
        """
        Generate professional summary from transcript using LLM via LangChain.

        Args:
            transcript: Full conversation transcript
            contact_number: User's phone number
            appointments: List of scheduled appointment dicts (for context)

        Returns:
            Multi-sentence summary of the call
        """
        try:
            # Create Azure OpenAI client using LangChain
            llm_client = AzureChatOpenAI(
                azure_deployment=config.azure_openai_deployment,
                azure_endpoint=config.azure_openai_endpoint,
                api_key=config.azure_openai_api_key,
                api_version=config.azure_openai_api_version,
                temperature=0.7,  # Slightly creative for summaries
            )

            # Build context about user's appointments
            appointments_context = ""
            if appointments:
                scheduled = [
                    apt for apt in appointments if apt.get("status") == "scheduled"
                ]
                if scheduled:
                    apt_details = []
                    for apt in scheduled[:5]:  # Limit to 5 most recent
                        date = apt.get("appointment_date", "")
                        time = apt.get("appointment_time", "")
                        apt_details.append(f"{date} at {time}")
                    if apt_details:
                        appointments_context = f"\n\nUser's current scheduled appointments: {', '.join(apt_details)}."

            # Create prompt for summary generation
            summary_prompt = f"""You are a professional call summary generator. Analyze the following conversation transcript and create a concise, professional summary.

CONVERSATION TRANSCRIPT:
{transcript}
{appointments_context}

INSTRUCTIONS:
- Create a 2-4 sentence summary of the conversation
- Include: user identification, main actions taken (booking/modifying/cancelling appointments), key details
- Mention specific appointment dates and times if any were booked/modified/cancelled
- Use professional, clear language
- Focus on what happened in THIS conversation, not general user information
- If appointments were booked/modified/cancelled, include the specific dates and times

SUMMARY:"""

            # Generate summary using LangChain
            messages = [HumanMessage(content=summary_prompt)]
            response = await llm_client.ainvoke(messages)

            # Extract text from response
            summary = (
                response.content.strip()
                if hasattr(response, "content")
                else str(response).strip()
            )

            # Clean up response (remove any markdown formatting if present)
            if summary.startswith("**"):
                # Remove markdown bold if present
                summary = summary.replace("**", "")

            return (
                summary
                if summary
                else f"Call with user {contact_number}. Conversation completed successfully."
            )

        except Exception as e:
            logger.error(f"Error generating summary with LLM: {e}", exc_info=True)
            # Fallback to simple summary
            return (
                f"Call with user {contact_number}. Conversation completed successfully."
            )
