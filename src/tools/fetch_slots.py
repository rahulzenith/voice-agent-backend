"""Tool for fetching available appointment slots from Supabase with IST timezone support"""
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from livekit.agents import function_tool, RunContext
from database.client import SupabaseClient
from services.event_service import EventService
from utils.shared_state import SharedState
from utils.date_time_utils import (
    format_time_for_display,
    get_ist_now,
    get_ist_date,
    get_time_of_day,
    get_date_label
)
from config import config

logger = logging.getLogger(__name__)


@function_tool
async def fetch_slots(
    context: RunContext,
    specific_date: str = ""
) -> str:
    """
    Fetches available appointment slots.
    
    Behavior:
    - If specific_date is provided: Returns ALL available slots on that date (grouped by time of day)
      * Allows LLM to filter by morning/afternoon/evening when user specifies
      * If that date has no slots: Returns ALL slots FROM that date onwards (next 14 days)
    - If specific_date is empty: Returns only 3 nearest future slots for quick booking
    
    Args:
        specific_date: Optional date in YYYY-MM-DD format (e.g., "2026-01-27")
                      - Provide this when user mentions a specific date/day
                      - Leave empty for quick "I want to book" requests
    
    Returns:
        - With specific_date: ALL available slots on that date, grouped as:
          "FRIDAY SLOTS: Morning (9 AM, 10 AM, 11 AM), Afternoon (12 PM, 2 PM), Evening (5 PM)"
        - Without specific_date: "I have 3 nearest slots available at: [slot1], [slot2], [slot3]"
    
    Examples:
        User: "Book appointment" → fetch_slots() → 3 nearest slots
        User: "Slots on Friday?" → fetch_slots(specific_date="2026-01-31") → ALL Friday slots
        User: "Friday evening?" → fetch_slots(specific_date="2026-01-31") → ALL Friday slots (LLM filters evening)
    
    IMPORTANT: Call book_appointment with exact date (YYYY-MM-DD) and time (HH:MM 24-hour format)
    """
    # Disable interruptions during tool execution
    # Reference: https://docs.livekit.io/agents/logic/tools/#interruptions
    context.disallow_interruptions()
    
    shared_state = SharedState.get_instance()
    room = shared_state.get_room()
    
    await EventService.emit_tool_call(
        room,
        "fetch_slots",
        "started",
        {"specific_date": specific_date if specific_date else "nearest_3"}
    )

    try:
        client = SupabaseClient.get_client(config.supabase_url, config.supabase_key)
        
        # Get current date and time in IST
        now_ist = get_ist_now()
        today_ist = now_ist.date()
        current_time_ist = now_ist.time()
        tomorrow_ist = today_ist + timedelta(days=1)
        
        # Build query based on whether specific_date is provided
        if specific_date:
            # Query specific date only
            slots_query = client.table("slots").select("*").eq(
                "slot_date", specific_date
            ).eq("is_available", True).order("slot_time")
        else:
            # Query next 14 days to find 3 nearest slots (performance optimization)
            end_date = today_ist + timedelta(days=14)
            slots_query = client.table("slots").select("*").gte(
                "slot_date", today_ist.isoformat()
            ).lte(
                "slot_date", end_date.isoformat()
            ).eq("is_available", True).order("slot_date").order("slot_time")
        
        slots_result = slots_query.execute()
        
        if not slots_result.data:
            await EventService.emit_tool_call(
                room,
                "fetch_slots",
                "success",
                {"available_slots": []}
            )
            if specific_date:
                # Parse the date to show it in a user-friendly format
                try:
                    requested_date = datetime.strptime(specific_date, "%Y-%m-%d")
                    formatted_date = requested_date.strftime("%A, %B %d")
                    return f"I'm sorry, there are no available slots on {formatted_date}. Please try a different date."
                except:
                    return "I'm sorry, there are no available slots on that date. Please try a different date."
            else:
                return "I'm sorry, there are no available slots at the moment. Please try again later."
        
        # Filter out booked slots and past times (only for today)
        available_slots = []
        for slot in slots_result.data:
            slot_date = datetime.strptime(slot["slot_date"], "%Y-%m-%d").date()
            slot_time = datetime.strptime(slot["slot_time"], "%H:%M:%S").time()
            
            # Skip past times for today only (if querying from today)
            if not specific_date and slot_date == today_ist and slot_time <= current_time_ist:
                continue
            
            # Check if this slot is already booked
            booked = client.table("appointments").select("id").eq(
                "slot_id", slot["id"]
            ).execute()
            
            if not booked.data:
                available_slots.append(slot)
                
                # If no specific date: Stop after finding 3 slots (performance optimization)
                # If specific date: Get ALL slots on that date
                if not specific_date and len(available_slots) >= 3:
                    break
        
        if not available_slots:
            await EventService.emit_tool_call(
                room,
                "fetch_slots",
                "success",
                {"available_slots": []}
            )
            if specific_date:
                # Parse the date to show it in a user-friendly format
                try:
                    requested_date = datetime.strptime(specific_date, "%Y-%m-%d")
                    formatted_date = requested_date.strftime("%A, %B %d")
                    return f"I'm sorry, there are no available slots on {formatted_date}. Please try a different date."
                except:
                    return "I'm sorry, there are no available slots on that date. Please try a different date."
            else:
                return "I'm sorry, all available slots are currently booked. Please check back later for new availability."
        
        # Format response based on whether specific_date was provided
        all_slot_data = []
        
        if specific_date:
            # Return ALL slots on that date, grouped by time of day
            slots_by_time = {"morning": [], "afternoon": [], "evening": []}
            
            for slot in available_slots:
                slot_date = datetime.strptime(slot["slot_date"], "%Y-%m-%d").date()
                slot_time = datetime.strptime(slot["slot_time"], "%H:%M:%S").time()
                time_display = format_time_for_display(slot["slot_time"])
                date_label = get_date_label(slot_date, today_ist, tomorrow_ist)
                hour = slot_time.hour
                
                # Categorize by time of day
                if 6 <= hour < 12:
                    time_category = "morning"
                elif 12 <= hour < 17:
                    time_category = "afternoon"
                else:
                    time_category = "evening"
                
                slots_by_time[time_category].append(time_display)
                
                # Prepare data for frontend
                all_slot_data.append({
                    "date": slot["slot_date"],
                    "time": slot["slot_time"],
                    "time_display": time_display,
                    "date_label": date_label,
                    "time_of_day": time_category
                })
            
            # Build response with grouping
            slot_date_obj = datetime.strptime(specific_date, "%Y-%m-%d").date()
            date_label = get_date_label(slot_date_obj, today_ist, tomorrow_ist).upper()
            
            response_parts = [f"{date_label} SLOTS:"]
            
            if slots_by_time["morning"]:
                response_parts.append(f"Morning: {', '.join(slots_by_time['morning'])}")
            if slots_by_time["afternoon"]:
                response_parts.append(f"Afternoon: {', '.join(slots_by_time['afternoon'])}")
            if slots_by_time["evening"]:
                response_parts.append(f"Evening: {', '.join(slots_by_time['evening'])}")
            
            response = " | ".join(response_parts) + "."
            
        else:
            # Return only 3 nearest slots
            nearest_3_slots = available_slots[:3]
            slot_descriptions = []
            
            for slot in nearest_3_slots:
                slot_date = datetime.strptime(slot["slot_date"], "%Y-%m-%d").date()
                time_display = format_time_for_display(slot["slot_time"])
                date_label = get_date_label(slot_date, today_ist, tomorrow_ist)
                
                # Format: "today at 2 PM", "tomorrow at 10 AM"
                slot_descriptions.append(f"{date_label} at {time_display}")
                
                # Prepare data for frontend
                all_slot_data.append({
                    "date": slot["slot_date"],
                    "time": slot["slot_time"],
                    "time_display": time_display,
                    "date_label": date_label
                })
            
            # Build response: Always say "I have 3 nearest slots available at:"
            response = f"I have 3 nearest slots available at: {', '.join(slot_descriptions)}."
        
        # Track tool call
        shared_state.tool_calls.append({
            "tool": "fetch_slots",
            "timestamp": datetime.utcnow().isoformat(),
            "params": {"specific_date": specific_date if specific_date else "nearest_3"},
            "result": f"{len(all_slot_data)} slots fetched"
        })
        
        await EventService.emit_tool_call(
            room,
            "fetch_slots",
            "success",
            {"available_slots": all_slot_data, "count": len(all_slot_data)}
        )
        
        return response

    except Exception as e:
        logger.error(f"Error fetching slots: {e}")
        await EventService.emit_tool_call(
            room,
            "fetch_slots",
            "error",
            {"error": str(e)}
        )
        return "I'm sorry, I had trouble checking availability. Could you try again?"
