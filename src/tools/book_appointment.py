"""Tool for booking appointments"""

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
async def book_appointment(
    context: RunContext, appointment_date: str, appointment_time: str, notes: str = ""
) -> str:
    """
    Books an appointment for the identified user.

    This tool creates a new appointment in the database after verifying the user
    is identified and the requested slot is still available.

    IMPORTANT: The user must be identified first using identify_user tool.

    RACE CONDITION PREVENTION:
    This tool uses a database-first approach to prevent race conditions when multiple
    users try to book the same slot simultaneously:

    1. **Database UNIQUE Constraint**: The `appointments` table has `UNIQUE(slot_id)`
       constraint that prevents double-booking at the database level. This is atomic
       and reliable.

    2. **No Pre-Checking**: We intentionally skip checking if the slot is booked by
       another user before inserting. This eliminates the race condition window
       between check and insert operations.

    3. **Direct Insert**: We attempt to insert the appointment directly. The database
       will reject the insert if the slot is already booked, ensuring atomicity.

    4. **Error Handling**: If a unique constraint violation occurs, we:
       - Check if it's the same user (duplicate tool call) → Return friendly message
       - Check if same date/time is booked → Return appropriate error
       - Otherwise → Treat as race condition (another user booked it)

    5. **Why This Works**: Database constraints are enforced atomically at the database
       level, making them immune to race conditions. Even if two users try to book
       the same slot simultaneously, only one will succeed, and the other will get
       a clear error message.

    This approach is more reliable than application-level locking or pre-checking,
    as it relies on the database's ACID properties to ensure data integrity.

    Args:
        appointment_date: The appointment date in YYYY-MM-DD format (e.g., "2026-01-27")
        appointment_time: The appointment time in HH:MM 24-hour format (e.g., "10:00" for 10 AM, "14:00" for 2 PM)
        notes: Optional notes or reason for the appointment

    Returns:
        Confirmation message with appointment details, or error message if:
        - User is not identified
        - Slot is already booked
        - Database operation fails

    Example: "Perfect! I've booked your appointment for 2026-01-27 at 2 PM. The appointment will last 30 minutes."
    """
    logger.info(
        f"🔧 TOOL CALLED: book_appointment with date={appointment_date}, time={appointment_time}"
    )

    # Disable interruptions during tool execution
    # Reference: https://docs.livekit.io/agents/logic/tools/#interruptions
    context.disallow_interruptions()

    # Get shared state
    shared_state = SharedState.get_instance()
    room = shared_state.get_room()
    contact_number = shared_state.get_contact_number()

    await EventService.emit_tool_call(
        room,
        "book_appointment",
        "started",
        {"date": appointment_date, "time": appointment_time},
    )

    try:
        if not contact_number:
            if room:
                await EventService.emit_tool_call(
                    room, "book_appointment", "error", {"error": "User not identified"}
                )
            return "I need to identify you first. Could you please provide your phone number?"

        # Get Supabase client
        client = SupabaseClient.get_client(config.supabase_url, config.supabase_key)

        # Find the slot in the slots table
        slot_query = (
            client.table("slots")
            .select("*")
            .eq("slot_date", appointment_date)
            .eq("slot_time", appointment_time)
            .execute()
        )

        if not slot_query.data:
            if room:
                await EventService.emit_tool_call(
                    room, "book_appointment", "error", {"error": "Slot not found"}
                )
            return f"I'm sorry, that time slot doesn't exist. Let me check what's available for you."

        slot = slot_query.data[0]
        slot_id = slot["id"]

        # Check if slot is still available
        if not slot.get("is_available", True):
            if room:
                await EventService.emit_tool_call(
                    room, "book_appointment", "error", {"error": "Slot not available"}
                )
            return f"I'm sorry, that slot at {format_time_for_display(appointment_time)} on {appointment_date} is no longer available. Let me check other available times for you."

        # Check if this user already has an appointment for this slot
        # This check is safe because it's user-specific and helps provide better UX
        user_existing = (
            client.table("appointments")
            .select("*")
            .eq("slot_id", slot_id)
            .eq("contact_number", contact_number)
            .execute()
        )

        if user_existing.data:
            if room:
                await EventService.emit_tool_call(
                    room,
                    "book_appointment",
                    "error",
                    {"error": "User already has this appointment"},
                )
            return f"You already have an appointment booked for {format_time_for_display(appointment_time)} on {appointment_date}. Would you like to modify or cancel it instead?"

        # RACE CONDITION PREVENTION STRATEGY:
        # 1. We rely on database UNIQUE(slot_id) constraint to prevent double-booking
        # 2. We skip pre-checking if slot is booked (removes race condition window)
        # 3. We try to insert directly - database will reject if slot is taken
        # 4. We handle unique constraint violations in the exception handler
        # This is the most reliable approach - let the database enforce atomicity

        appointment_data = {
            "contact_number": contact_number,
            "slot_id": slot_id,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "duration_minutes": config.appointment_duration,
            "status": "scheduled",
            "notes": notes if notes else None,
        }

        try:
            # Attempt to insert - database UNIQUE constraint will prevent double-booking
            result = client.table("appointments").insert(appointment_data).execute()

            if result.data:
                appointment = result.data[0]

                # Mark the slot as unavailable (best effort - if this fails, slot might still show as available)
                # This is acceptable because we check appointment existence, not slot availability
                try:
                    client.table("slots").update({"is_available": False}).eq(
                        "id", slot_id
                    ).execute()
                    logger.info(f"✅ Slot {slot_id} marked as unavailable")
                except Exception as update_error:
                    # Slot update failed, but appointment is booked - log and continue
                    logger.warning(
                        f"Failed to update slot availability: {update_error}"
                    )

                # Track tool call in shared state
                shared_state.tool_calls.append(
                    {
                        "tool": "book_appointment",
                        "timestamp": datetime.utcnow().isoformat(),
                        "params": {"date": appointment_date, "time": appointment_time},
                        "result": "success",
                    }
                )

                # Update user preferences based on booked appointment
                shared_state.user_preferences = PreferenceTracker.update_preferences(
                    shared_state.user_preferences, appointment_date, appointment_time
                )
                logger.info(
                    f"📊 Updated user preferences: {shared_state.user_preferences}"
                )

                # LLM costs are automatically tracked via metrics_collected event

                if room:
                    await EventService.emit_tool_call(
                        room,
                        "book_appointment",
                        "success",
                        {"appointment": appointment},
                    )

                # Format time for natural speech
                display_time = format_time_for_display(appointment_time)

                return f"Perfect! I've booked your appointment for {appointment_date} at {display_time}. The appointment will last {config.appointment_duration} minutes. See you then!"

        except Exception as insert_error:
            # Check if this is a unique constraint violation (race condition)
            # Supabase/PostgREST returns errors in various formats
            error_str = str(insert_error).lower()
            error_code = getattr(insert_error, "code", None)
            error_message = getattr(insert_error, "message", "")

            # Check for PostgreSQL unique constraint violation (error code 23505)
            # Also check common error message patterns
            is_unique_violation = (
                error_code == "23505"  # PostgreSQL unique violation code
                or "23505" in error_str  # Sometimes code is in string
                or "unique constraint" in error_str
                or "duplicate key" in error_str
                or "duplicate key value" in error_str
                or (
                    "unique" in error_str
                    and (
                        "slot_id" in error_str
                        or "appointment_date" in error_str
                        or "appointment_time" in error_str
                    )
                )
                or "already exists" in error_str
            )

            if is_unique_violation:
                # Unique constraint violation occurred - check who has the appointment
                # This could be:
                # 1. Same user (duplicate tool call)
                # 2. Different user (race condition)
                # 3. Same date/time (different slot_id but same date/time)

                # Check if this user already has this appointment
                user_existing = (
                    client.table("appointments")
                    .select("*")
                    .eq("slot_id", slot_id)
                    .eq("contact_number", contact_number)
                    .execute()
                )

                if user_existing.data:
                    # User already has this appointment (duplicate tool call from LLM)
                    appointment = user_existing.data[0]
                    display_time = format_time_for_display(appointment_time)
                    if room:
                        await EventService.emit_tool_call(
                            room,
                            "book_appointment",
                            "error",
                            {"error": "User already has this appointment"},
                        )
                    return f"You already have an appointment booked for {appointment_date} at {display_time}. Is there anything else I can help you with?"

                # Check if same date/time is booked (different constraint)
                date_time_existing = (
                    client.table("appointments")
                    .select("*")
                    .eq("appointment_date", appointment_date)
                    .eq("appointment_time", appointment_time)
                    .execute()
                )

                if date_time_existing.data:
                    # Same date/time booked (UNIQUE(appointment_date, appointment_time) constraint)
                    display_time = format_time_for_display(appointment_time)
                    if room:
                        await EventService.emit_tool_call(
                            room,
                            "book_appointment",
                            "error",
                            {"error": "Time slot already booked"},
                        )
                    return f"I'm sorry, that time slot at {display_time} on {appointment_date} is already booked. Let me check other available times for you."

                # Race condition: another user booked this exact slot_id
                logger.warning(
                    f"Race condition detected: Slot {slot_id} was booked by another user"
                )
                if room:
                    await EventService.emit_tool_call(
                        room,
                        "book_appointment",
                        "error",
                        {"error": "Slot booked by another user (race condition)"},
                    )
                return f"I'm sorry, that slot at {format_time_for_display(appointment_time)} on {appointment_date} was just booked by another user. Let me check other available times for you."
            else:
                # Some other database error - re-raise to be handled by outer exception handler
                logger.error(
                    f"Error inserting appointment: {insert_error}", exc_info=True
                )
                raise

        if room:
            await EventService.emit_tool_call(
                room,
                "book_appointment",
                "error",
                {"error": "Failed to create appointment"},
            )
        return "I'm sorry, I had trouble booking the appointment. Could you try again?"

    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        if room:
            await EventService.emit_tool_call(
                room, "book_appointment", "error", {"error": str(e)}
            )
        return "I'm sorry, I had trouble booking the appointment. Could you try again?"
