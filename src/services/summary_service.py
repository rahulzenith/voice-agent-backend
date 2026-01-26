"""Service for generating rule-based conversation summaries."""
import logging

logger = logging.getLogger(__name__)


class SummaryService:
    """
    Generate professional summaries from conversation transcripts.
    
    Methods:
    - generate_from_transcript(): Parse transcript and create summary
    
    Summary includes: user info, actions taken, appointments, user requests
    """
    
    @staticmethod
    def generate_from_transcript(transcript: str, contact_number: str, appointments: list) -> str:
        """
        Generate professional summary from transcript.
        
        Args:
            transcript: Full conversation transcript
            contact_number: User's phone number
            appointments: List of scheduled appointment dicts
            
        Returns:
            Multi-sentence summary of the call
        """
        try:
            actions_taken = []
            user_requests = []
            
            # Parse transcript for actions
            if "book_appointment" in transcript.lower():
                actions_taken.append("booked an appointment")
            if "cancel_appointment" in transcript.lower():
                actions_taken.append("cancelled an appointment")
            if "modify_appointment" in transcript.lower():
                actions_taken.append("modified an appointment")
            if "identify_user" in transcript.lower():
                user_requests.append("user identification")
            if "fetch_slots" in transcript.lower():
                user_requests.append("checked available time slots")
            
            # Build summary
            summary_parts = []
            
            if contact_number:
                summary_parts.append(f"User (phone: {contact_number}) contacted the appointment booking service.")
            else:
                summary_parts.append("User contacted the appointment booking service.")
            
            if user_requests:
                summary_parts.append(f"The conversation included {', '.join(user_requests)}.")
            
            if actions_taken:
                summary_parts.append(f"Actions completed: {', '.join(actions_taken)}.")
            else:
                summary_parts.append("The user inquired about appointment services.")
            
            if appointments:
                scheduled = [apt for apt in appointments if apt.get("status") == "scheduled"]
                if scheduled:
                    apt_details = []
                    for apt in scheduled[:2]:
                        date = apt.get("appointment_date", "")
                        time = apt.get("appointment_time", "")
                        apt_details.append(f"{date} at {time}")
                    
                    if apt_details:
                        summary_parts.append(f"Scheduled appointments: {', '.join(apt_details)}.")
            
            summary_parts.append("The call concluded successfully.")
            
            return " ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Call with user {contact_number}. {len(appointments)} appointments discussed."
