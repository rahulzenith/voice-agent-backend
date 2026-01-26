"""Date and time utility functions"""
from datetime import datetime, date, time
import pytz

# IST timezone
IST = pytz.timezone('Asia/Kolkata')


def format_time_for_display(time_str: str) -> str:
    """Convert 24-hour time to 12-hour display format"""
    try:
        if isinstance(time_str, str):
            time_obj = datetime.strptime(time_str, "%H:%M:%S").time()
        else:
            time_obj = time_str
        
        hour = time_obj.hour
        minute = time_obj.minute
        
        if hour == 0:
            return f"12:{minute:02d} AM" if minute else "12 AM"
        elif hour < 12:
            return f"{hour}:{minute:02d} AM" if minute else f"{hour} AM"
        elif hour == 12:
            return f"12:{minute:02d} PM" if minute else "12 PM"
        else:
            return f"{hour-12}:{minute:02d} PM" if minute else f"{hour-12} PM"
    except:
        return str(time_str)


def get_ist_now() -> datetime:
    """Get current datetime in IST timezone"""
    return datetime.now(IST)


def get_ist_date() -> date:
    """Get current date in IST timezone"""
    return get_ist_now().date()


def get_time_of_day(hour: int) -> str:
    """Categorize time into morning, afternoon, or evening"""
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    else:
        return "evening"


def get_date_label(slot_date: date, today: date, tomorrow: date) -> str:
    """Get human-readable date label with today/tomorrow"""
    if slot_date == today:
        return f"today ({slot_date.strftime('%A, %B %d')})"
    elif slot_date == tomorrow:
        return f"tomorrow ({slot_date.strftime('%A, %B %d')})"
    else:
        # Format as "Monday, January 27"
        dt = datetime.combine(slot_date, datetime.min.time())
        return dt.strftime("%A, %B %d")
