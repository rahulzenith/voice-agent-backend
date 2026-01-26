"""Utility for tracking user preferences during conversation"""
from typing import Dict, Any
from datetime import datetime


class PreferenceTracker:
    """Track and extract user preferences from appointments and interactions"""
    
    @staticmethod
    def extract_time_preference(time_str: str) -> str:
        """
        Extract time of day preference from appointment time.
        
        Args:
            time_str: Time in HH:MM or HH:MM:SS format
            
        Returns:
            "morning", "afternoon", or "evening"
        """
        try:
            if ':' in time_str:
                hour = int(time_str.split(':')[0])
                
                if 6 <= hour < 12:
                    return "morning"
                elif 12 <= hour < 17:
                    return "afternoon"
                else:
                    return "evening"
        except:
            pass
        
        return "unknown"
    
    @staticmethod
    def extract_day_preference(date_str: str) -> str:
        """
        Extract day of week from appointment date.
        
        Args:
            date_str: Date in YYYY-MM-DD format
            
        Returns:
            Day name (e.g., "Monday")
        """
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            return date_obj.strftime("%A")  # Full day name
        except:
            return "unknown"
    
    @staticmethod
    def update_preferences(
        preferences: Dict[str, Any],
        appointment_date: str,
        appointment_time: str
    ) -> Dict[str, Any]:
        """
        Update preferences based on booked appointment.
        
        Args:
            preferences: Existing preferences dict
            appointment_date: Date in YYYY-MM-DD format
            appointment_time: Time in HH:MM format
            
        Returns:
            Updated preferences dict
        """
        time_of_day = PreferenceTracker.extract_time_preference(appointment_time)
        day_of_week = PreferenceTracker.extract_day_preference(appointment_date)
        
        # Update preferred time
        if time_of_day != "unknown":
            preferences["preferred_time"] = time_of_day
        
        # Update preferred days (track last 3)
        if day_of_week != "unknown":
            if "preferred_days" not in preferences:
                preferences["preferred_days"] = []
            
            if day_of_week not in preferences["preferred_days"]:
                preferences["preferred_days"].append(day_of_week)
                # Keep only last 3
                if len(preferences["preferred_days"]) > 3:
                    preferences["preferred_days"] = preferences["preferred_days"][-3:]
        
        # Track last appointment
        preferences["last_appointment_date"] = appointment_date
        preferences["last_appointment_time"] = appointment_time
        
        return preferences
