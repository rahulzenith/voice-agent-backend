"""Tool for ending conversation and generating summary"""

import logging
import asyncio
from datetime import datetime
from livekit.agents import function_tool, RunContext
from database.client import SupabaseClient
from utils.shared_state import SharedState
from services.event_service import EventService
from services.call_service import CallService
from services.transcript_service import TranscriptService
from services.summary_service import SummaryService
from services.cost_service import CostService
from config import config

logger = logging.getLogger(__name__)


@function_tool
async def end_conversation(context: RunContext) -> str:
    """
    Ends the conversation and generates a comprehensive summary.

    Returns:
        A farewell message. The summary is sent to the frontend via event emission.
    """
    # Disable interruptions during tool execution
    # Reference: https://docs.livekit.io/agents/logic/tools/#interruptions
    context.disallow_interruptions()

    shared_state = SharedState.get_instance()
    room = shared_state.get_room()
    contact_number = shared_state.get_contact_number()

    await EventService.emit_tool_call(room, "end_conversation", "started", {})

    try:
        client = SupabaseClient.get_client(config.supabase_url, config.supabase_key)

        # Retrieve user's appointments
        appointments = []
        if contact_number:
            result = (
                client.table("appointments")
                .select("*")
                .eq("contact_number", contact_number)
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
            appointments = result.data if result.data else []

        # Extract conversation from session chat context
        transcript_messages = []
        transcript_text = ""

        try:
            session = shared_state.get_session()
            if (
                session
                and hasattr(session, "_chat_ctx")
                and hasattr(session._chat_ctx, "items")
            ):
                chat_items = session._chat_ctx.items
                transcript_messages = TranscriptService.extract_from_chat_context(
                    chat_items
                )
                transcript_text = TranscriptService.format_for_display(
                    transcript_messages
                )
            else:
                # Fallback: Use shared state
                conversation_messages = getattr(
                    shared_state, "conversation_messages", []
                )
                tool_calls = shared_state.tool_calls

                transcript_messages.extend(conversation_messages)

                for tool_call in tool_calls:
                    transcript_messages.append(
                        {
                            "role": "function",
                            "name": tool_call["tool"],
                            "timestamp": tool_call["timestamp"],
                            "params": tool_call.get("params", {}),
                            "result": tool_call.get("result", ""),
                        }
                    )

                transcript_messages.sort(key=lambda x: x.get("timestamp", ""))
                transcript_text = TranscriptService.format_for_display(
                    transcript_messages
                )
        except Exception as e:
            logger.error(f"Error extracting transcript: {e}")

        # Generate summary using LLM
        summary_text = await SummaryService.generate_from_transcript(
            transcript_text, contact_number or "Unknown", appointments
        )

        # Only scheduled appointments for frontend (exclude cancelled)
        recent_appointments = []
        if appointments:
            scheduled_appointments = [
                apt for apt in appointments if apt.get("status") == "scheduled"
            ]
            recent_appointments = [
                {
                    "date": apt["appointment_date"],
                    "time": apt["appointment_time"],
                    "status": apt["status"],
                }
                for apt in scheduled_appointments
            ]

        # Get user preferences
        user_preferences = shared_state.user_preferences

        # Calculate session duration
        session_duration = 0
        if (
            hasattr(shared_state, "session_start_time")
            and shared_state.session_start_time
        ):
            duration_delta = datetime.utcnow() - shared_state.session_start_time
            session_duration = int(duration_delta.total_seconds())

        # Calculate costs from usage metrics
        cost_breakdown = None
        if hasattr(shared_state, "usage_collector") and shared_state.usage_collector:
            try:
                usage_summary = shared_state.usage_collector.get_summary()
                cost_breakdown = CostService.calculate_from_usage_summary(
                    usage_summary, session_duration
                )
            except Exception as e:
                logger.error(f"Error calculating costs: {e}")

        # Get tool calls from shared state
        tool_calls = shared_state.tool_calls

        # Count different message types
        user_messages = [m for m in transcript_messages if m.get("role") == "user"]
        assistant_messages = [
            m for m in transcript_messages if m.get("role") == "assistant"
        ]
        function_calls = [m for m in transcript_messages if m.get("role") == "function"]

        # Save conversation log to database
        if contact_number:
            conversation_data = {
                "session_id": room.name if room else "unknown",
                "contact_number": contact_number,
                "transcript": {
                    "messages": transcript_messages,
                    "tool_calls_count": len(tool_calls),
                    "full_transcript_text": transcript_text,
                },
                "summary": summary_text,
                "tool_calls": tool_calls,
                "duration_seconds": session_duration,
                "cost_breakdown": cost_breakdown,
                "user_preferences": user_preferences,
            }

            try:
                client.table("conversation_logs").insert(conversation_data).execute()
            except Exception as e:
                logger.error(f"Failed to save conversation log: {e}")

        # Emit summary to frontend
        await EventService.emit_summary(
            room,
            summary_text,
            recent_appointments,
            user_preferences,
            cost_breakdown,
            session_duration,
        )

        await EventService.emit_tool_call(
            room, "end_conversation", "success", {"summary": summary_text}
        )

        # Schedule disconnect
        if room:
            asyncio.create_task(CallService.schedule_disconnect(room, delay_seconds=8))

        return "Thank you for using our appointment booking service. Have a great day!"

    except Exception as e:
        logger.error(f"Error ending conversation: {e}")
        await EventService.emit_tool_call(
            room, "end_conversation", "error", {"error": str(e)}
        )
        return "Thank you for your time. Goodbye!"
