"""Tool for identifying users by phone number"""
import logging
from datetime import datetime
from livekit.agents import function_tool, RunContext
from database.client import SupabaseClient
from services.event_service import EventService
from utils.shared_state import SharedState
from config import config

logger = logging.getLogger(__name__)


@function_tool
async def identify_user(
    context: RunContext,
    contact_number: str
) -> str:
    """
    Identifies or creates a user by their phone number.
    
    IMPORTANT: This MUST be called FIRST before any other operations.
    Always ask for the phone number at the start of the conversation.
    
    Args:
        contact_number: User's phone number in any format (e.g., "555-1234", "+1-555-1234", "5551234")
    
    Returns:
        Success message if user is found or created, error message otherwise.
    """
    logger.info(f"🔧 TOOL CALLED: identify_user with contact_number={contact_number}")
    
    # Disable interruptions during tool execution
    # Reference: https://docs.livekit.io/agents/logic/tools/#interruptions
    context.disallow_interruptions()
    
    # Get shared state
    shared_state = SharedState.get_instance()
    room = shared_state.get_room()
    
    await EventService.emit_tool_call(
        room,
        "identify_user",
        "started",
        {"contact_number": contact_number}
    )

    try:
        # Clean phone number (remove spaces, dashes, etc.)
        clean_number = contact_number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

        # Get Supabase client
        client = SupabaseClient.get_client(config.supabase_url, config.supabase_key)

        # Check if user exists
        result = client.table("users").select("*").eq("contact_number", clean_number).execute()

        if result.data:
            # User exists
            user = result.data[0]
            # Store contact number in shared state
            shared_state.set_contact_number(clean_number)
            logger.info(f"✅ Contact number stored in shared state: {clean_number}")
            
            # Track tool call
            shared_state.tool_calls.append({
                "tool": "identify_user",
                "timestamp": datetime.utcnow().isoformat(),
                "params": {"contact_number": clean_number},
                "result": "found"
            })
            
            # Track estimated LLM cost for this tool call
            # LLM costs are automatically tracked via metrics_collected event

            await EventService.emit_tool_call(
                room,
                "identify_user",
                "success",
                {"user": user, "action": "found"}
            )
            return f"User account found for {clean_number}. Welcome back!"
        else:
            # Create new user
            new_user = client.table("users").insert({
                "contact_number": clean_number
            }).execute()

            # Store contact number in shared state
            shared_state.set_contact_number(clean_number)
            logger.info(f"✅ Contact number stored in shared state: {clean_number}")
            
            # Track tool call
            shared_state.tool_calls.append({
                "tool": "identify_user",
                "timestamp": datetime.utcnow().isoformat(),
                "params": {"contact_number": clean_number},
                "result": "created"
            })
            
            # LLM costs are automatically tracked via metrics_collected event

            await EventService.emit_tool_call(
                room,
                "identify_user",
                "success",
                {"user": new_user.data[0] if new_user.data else {}, "action": "created"}
            )
            return f"New account created for {clean_number}. Welcome!"

    except Exception as e:
        logger.error(f"Error identifying user: {e}")
        await EventService.emit_tool_call(
            room,
            "identify_user",
            "error",
            {"error": str(e)}
        )
        return "I'm sorry, I had trouble looking up that phone number. Could you please repeat it?"
