"""Tool for modifying appointments"""
import logging
from datetime import datetime
from livekit.agents import function_tool, RunContext
from database.client import SupabaseClient
from services.event_service import EventService
from utils.shared_state import SharedState
from utils.preference_tracker import PreferenceTracker
from config import config
from utils.date_time_utils import format_time_for_display

logger = logging.getLogger(__name__)


@function_tool
async def modify_appointment(
    context: RunContext,
    appointment_id: str,
    new_date: str,
    new_time: str
) -> str:
    """
    Modifies an existing appointment to a new date and/or time.
    
    This tool updates an appointment's date and time after verifying the new slot is available.
    
    CRITICAL WORKFLOW:
    1. ALWAYS call retrieve_appointments FIRST to get the list of appointments
    2. Find the appointment the user wants to modify
    3. Extract the "id" field (UUID) from that appointment
    4. Call fetch_slots to show available new time slots
    5. Pass the UUID as appointment_id, plus new_date and new_time
    
    IMPORTANT: The user must be identified first, and the appointment must belong to them.
    
    Args:
        appointment_id: The UUID of the appointment (e.g., "550e8400-e29b-41d4-a716-446655440000")
                       MUST be from retrieve_appointments response "id" field
                       NEVER use date/time strings like "2026-01-27 at 7 PM"
        new_date: The new appointment date in YYYY-MM-DD format (e.g., "2026-01-30")
        new_time: The new appointment time in HH:MM 24-hour format (e.g., "14:00" for 2 PM)
    
    Returns:
        Confirmation message showing old and new appointment details, or error message if:
        - User is not identified
        - Appointment ID is not found or invalid UUID format
        - Appointment belongs to a different user
        - New slot is already booked
        - Database operation fails
    
    Example Response: "Perfect! I've moved your appointment from 2026-01-27 at 10 AM to 2026-01-30 at 2 PM."
    """
    logger.info(f"🔧 TOOL CALLED: modify_appointment with appointment_id={appointment_id}, new_date={new_date}, new_time={new_time}")
    
    # Disable interruptions during tool execution
    # Reference: https://docs.livekit.io/agents/logic/tools/#interruptions
    context.disallow_interruptions()
    
    # Get shared state
    shared_state = SharedState.get_instance()
    room = shared_state.get_room()
    contact_number = shared_state.get_contact_number()
    
    await EventService.emit_tool_call(
        room,
        "modify_appointment",
        "started",
        {"appointment_id": appointment_id, "new_date": new_date, "new_time": new_time}
    )

    try:
        if not contact_number:
            await EventService.emit_tool_call(
                room,
                "modify_appointment",
                "error",
                {"error": "User not identified"}
            )
            return "I need to identify you first. Could you please provide your phone number?"

        # Get Supabase client
        client = SupabaseClient.get_client(config.supabase_url, config.supabase_key)

        # Verify appointment belongs to user
        appointment = client.table("appointments").select("*").eq("id", appointment_id).execute()

        if not appointment.data:
            await EventService.emit_tool_call(
                room,
                "modify_appointment",
                "error",
                {"error": "Appointment not found"}
            )
            return "I couldn't find that appointment. Could you tell me which appointment you'd like to modify?"

        apt = appointment.data[0]
        if apt["contact_number"] != contact_number:
            await EventService.emit_tool_call(
                room,
                "modify_appointment",
                "error",
                {"error": "Appointment belongs to different user"}
            )
            return "I'm sorry, that appointment doesn't belong to your account."

        # Find the new slot in the slots table
        new_slot_query = client.table("slots").select("*").eq(
            "slot_date", new_date
        ).eq("slot_time", new_time).execute()

        if not new_slot_query.data:
            await EventService.emit_tool_call(
                room,
                "modify_appointment",
                "error",
                {"error": "New slot not found"}
            )
            return f"I'm sorry, that time slot doesn't exist. Let me check what's available for you."

        new_slot = new_slot_query.data[0]
        new_slot_id = new_slot["id"]

        # Check if new slot is available (exclude current appointment)
        existing = client.table("appointments").select("*").eq(
            "slot_id", new_slot_id
        ).neq("id", appointment_id).execute()

        if existing.data:
            await EventService.emit_tool_call(
                room,
                "modify_appointment",
                "error",
                {"error": "New slot already booked"}
            )
            return f"I'm sorry, the slot at {new_time} on {new_date} is already booked. Would you like to try a different time?"

        # Get old appointment details for confirmation message
        old_date = apt["appointment_date"]
        old_time = apt["appointment_time"]
        old_slot_id = apt.get("slot_id")

        # Update the appointment with new slot
        result = client.table("appointments").update({
            "slot_id": new_slot_id,
            "appointment_date": new_date,
            "appointment_time": new_time
        }).eq("id", appointment_id).execute()

        if result.data:
            # Mark old slot as available again
            if old_slot_id:
                client.table("slots").update({"is_available": True}).eq("id", old_slot_id).execute()
                logger.info(f"✅ Old slot {old_slot_id} marked as available again")
            
            # Mark new slot as unavailable
            client.table("slots").update({"is_available": False}).eq("id", new_slot_id).execute()
            logger.info(f"✅ New slot {new_slot_id} marked as unavailable")
            
            # Track tool call in shared state
            shared_state.tool_calls.append({
                "tool": "modify_appointment",
                "timestamp": datetime.utcnow().isoformat(),
                "params": {"appointment_id": appointment_id, "new_date": new_date, "new_time": new_time},
                "result": "success"
            })
            
            # Update user preferences based on modified appointment
            shared_state.user_preferences = PreferenceTracker.update_preferences(
                shared_state.user_preferences,
                new_date,
                new_time
            )
            logger.info(f"📊 Updated user preferences: {shared_state.user_preferences}")
            
            # LLM costs are automatically tracked via metrics_collected event
            
            # Format times for natural speech
            new_display_time = format_time_for_display(new_time)
            old_display_time = format_time_for_display(old_time)

            await EventService.emit_tool_call(
                room,
                "modify_appointment",
                "success",
                {"appointment": result.data[0]}
            )

            return f"Perfect! I've moved your appointment from {old_date} at {old_display_time} to {new_date} at {new_display_time}."

        await EventService.emit_tool_call(
            room,
            "modify_appointment",
            "error",
            {"error": "Failed to modify appointment"}
        )
        return "I'm sorry, I had trouble modifying the appointment. Could you try again?"

    except Exception as e:
        logger.error(f"Error modifying appointment: {e}")
        await EventService.emit_tool_call(
            room,
            "modify_appointment",
            "error",
            {"error": str(e)}
        )
        return "I'm sorry, I had trouble modifying the appointment. Could you try again?"
