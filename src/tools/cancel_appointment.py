"""Tool for cancelling appointments"""

import logging
from datetime import datetime
from livekit.agents import function_tool, RunContext
from database.client import SupabaseClient
from services.event_service import EventService
from utils.shared_state import SharedState
from config import config
from utils.date_time_utils import format_time_for_display

logger = logging.getLogger(__name__)


@function_tool
async def cancel_appointment(context: RunContext, appointment_id: str) -> str:
    """
    Cancels an existing appointment by deleting it from the database.

    This tool deletes the appointment row and marks the slot as available again.

    CRITICAL WORKFLOW:
    1. ALWAYS call retrieve_appointments FIRST to get the list of appointments
    2. Find the appointment the user wants to cancel
    3. Extract the "id" field (UUID) from that appointment
    4. Pass that UUID as the appointment_id parameter

    IMPORTANT: The user must be identified first, and the appointment must belong to them.

    Args:
        appointment_id: The UUID of the appointment (e.g., "550e8400-e29b-41d4-a716-446655440000")
                       MUST be from retrieve_appointments response "id" field
                       NEVER use date/time strings like "2026-01-27 at 7 PM"

    Returns:
        Confirmation message with the cancelled appointment details, or error message if:
        - User is not identified
        - Appointment ID is not found or invalid UUID format
        - Appointment belongs to a different user
        - Database operation fails

    Example Response: "Your appointment for 2026-01-27 at 10 AM has been cancelled."
    """
    logger.info(
        f"🔧 TOOL CALLED: cancel_appointment with appointment_id={appointment_id}"
    )

    # Disable interruptions during tool execution
    # Reference: https://docs.livekit.io/agents/logic/tools/#interruptions
    context.disallow_interruptions()

    # Get shared state
    shared_state = SharedState.get_instance()
    room = shared_state.get_room()
    contact_number = shared_state.get_contact_number()

    await EventService.emit_tool_call(
        room, "cancel_appointment", "started", {"appointment_id": appointment_id}
    )

    try:
        if not contact_number:
            await EventService.emit_tool_call(
                room, "cancel_appointment", "error", {"error": "User not identified"}
            )
            return "I need to identify you first. Could you please provide your phone number?"

        # Get Supabase client
        client = SupabaseClient.get_client(config.supabase_url, config.supabase_key)

        # Verify appointment belongs to user
        appointment = (
            client.table("appointments").select("*").eq("id", appointment_id).execute()
        )

        if not appointment.data:
            await EventService.emit_tool_call(
                room, "cancel_appointment", "error", {"error": "Appointment not found"}
            )
            return "I couldn't find that appointment. Could you tell me the date and time of the appointment you'd like to cancel?"

        apt = appointment.data[0]
        if apt["contact_number"] != contact_number:
            await EventService.emit_tool_call(
                room,
                "cancel_appointment",
                "error",
                {"error": "Appointment belongs to different user"},
            )
            return "I'm sorry, that appointment doesn't belong to your account."

        # Store appointment details before deletion
        apt_date = apt["appointment_date"]
        time_str = apt["appointment_time"]
        display_time = format_time_for_display(time_str)
        slot_id = apt.get("slot_id")

        # Delete the appointment
        result = (
            client.table("appointments").delete().eq("id", appointment_id).execute()
        )

        if result.data:
            # Mark the slot as available again
            if slot_id:
                client.table("slots").update({"is_available": True}).eq(
                    "id", slot_id
                ).execute()
                logger.info(f"✅ Slot {slot_id} marked as available again")

            # Track tool call in shared state
            shared_state.tool_calls.append(
                {
                    "tool": "cancel_appointment",
                    "timestamp": datetime.utcnow().isoformat(),
                    "params": {"appointment_id": appointment_id},
                    "result": "success",
                }
            )

            # LLM costs are automatically tracked via metrics_collected event

            await EventService.emit_tool_call(
                room,
                "cancel_appointment",
                "success",
                {"appointment_id": appointment_id, "date": apt_date, "time": time_str},
            )

            return f"Your appointment for {apt_date} at {display_time} has been cancelled. Is there anything else I can help you with?"

        await EventService.emit_tool_call(
            room,
            "cancel_appointment",
            "error",
            {"error": "Failed to cancel appointment"},
        )
        return (
            "I'm sorry, I had trouble cancelling the appointment. Could you try again?"
        )

    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}")
        await EventService.emit_tool_call(
            room, "cancel_appointment", "error", {"error": str(e)}
        )
        return (
            "I'm sorry, I had trouble cancelling the appointment. Could you try again?"
        )
