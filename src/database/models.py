"""Pydantic models for database entities"""

from datetime import date, time, datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class User(BaseModel):
    """User model"""

    contact_number: str
    name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Slot(BaseModel):
    """Available time slot model"""

    id: Optional[UUID] = None
    slot_date: date
    slot_time: time
    duration_minutes: int = 30
    is_available: bool = True
    created_at: Optional[datetime] = None


class Appointment(BaseModel):
    """Appointment model"""

    id: Optional[UUID] = None
    contact_number: str
    slot_id: Optional[UUID] = None
    appointment_date: date
    appointment_time: time
    duration_minutes: int = 30
    status: str = "scheduled"  # scheduled, cancelled, completed
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ConversationLog(BaseModel):
    """Conversation log model"""

    id: Optional[UUID] = None
    session_id: str
    contact_number: Optional[str] = None
    transcript: Dict[str, Any]
    summary: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    duration_seconds: Optional[int] = None
    cost_breakdown: Optional[Dict[str, float]] = None
    created_at: Optional[datetime] = None
