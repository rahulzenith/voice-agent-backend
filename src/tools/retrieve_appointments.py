"""Tool for retrieving user appointments"""
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
async def retrieve_appointments(context: RunContext) -> str:
    """
    Retrieves all scheduled appointments for the current identified user.
    
    This tool fetches all scheduled appointments associated with the user's phone number from the database.
    Cancelled appointments are excluded.
    
    IMPORTANT: 
    - The user must be identified first using identify_user tool
    - The response includes appointment IDs which are REQUIRED for cancel_appointment and modify_appointment
    
    Returns:
        A natural language list of all appointments with IDs, dates, times, and status,
        or a message if no appointments exist.
    
    Example Response: 
        "You have 2 appointments: 
        ID: 550e8400-e29b-41d4-a716-446655440000, Date: 2026-01-27 at 10 AM, 
        and ID: 660e8400-e29b-41d4-a716-446655440001, Date: 2026-01-30 at 2 PM."
    
    CRITICAL: When user wants to cancel or modify, extract the ID from this response and use it.
    """
    logger.info(f"🔧 TOOL CALLED: retrieve_appointments")
    
    # Disable interruptions during tool execution
    # Reference: https://docs.livekit.io/agents/logic/tools/#interruptions
    context.disallow_interruptions()
    
    # Get shared state
    shared_state = SharedState.get_instance()
    room = shared_state.get_room()
    contact_number = shared_state.get_contact_number()
    
    await EventService.emit_tool_call(
        room,
        "retrieve_appointments",
        "started",
        {}
    )

    try:
        if not contact_number:
            await EventService.emit_tool_call(
                room,
                "retrieve_appointments",
                "error",
                {"error": "User not identified"}
            )
            return "I need to identify you first. Could you please provide your phone number?"

        # Get Supabase client
        client = SupabaseClient.get_client(config.supabase_url, config.supabase_key)

        # Retrieve all appointments for this user
        result = client.table("appointments").select("*").eq(
            "contact_number", contact_number
        ).order("appointment_date", desc=False).order("appointment_time", desc=False).execute()

        if not result.data:
            await EventService.emit_tool_call(
                room,
                "retrieve_appointments",
                "success",
                {"appointments": []}
            )
            return "You don't have any appointments scheduled yet. Would you like to book one?"

        # Format appointments for speech WITH IDs
        appointments = result.data
        appointment_list = []

        for apt in appointments:
            # Format date
            apt_date = apt["appointment_date"]
            # Format time
            time_str = apt["appointment_time"]
            display_time = format_time_for_display(time_str)

            status = apt["status"]
            status_text = f"({status})" if status != "scheduled" else ""
            
            # CRITICAL: Include the appointment ID so LLM can use it for cancel/modify
            apt_id = apt["id"]

            appointment_list.append(
                f"ID: {apt_id}, Date: {apt_date} at {display_time} {status_text}".strip()
            )

        # Track tool call
        shared_state.tool_calls.append({
            "tool": "retrieve_appointments",
            "timestamp": datetime.utcnow().isoformat(),
            "params": {},
            "result": f"{len(appointment_list)} appointments found"
        })
        
        # LLM costs are automatically tracked via metrics_collected event
        
        await EventService.emit_tool_call(
            room,
            "retrieve_appointments",
            "success",
            {"appointments": appointments}
        )

        if len(appointment_list) == 1:
            return f"You have 1 appointment: {appointment_list[0]}."
        else:
            appointments_text = ", ".join(appointment_list[:-1]) + f", and {appointment_list[-1]}"
            return f"You have {len(appointment_list)} appointments: {appointments_text}."

    except Exception as e:
        logger.error(f"Error retrieving appointments: {e}")
        await EventService.emit_tool_call(
            room,
            "retrieve_appointments",
            "error",
            {"error": str(e)}
        )
        return "I'm sorry, I had trouble retrieving your appointments. Could you try again?"
