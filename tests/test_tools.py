"""Unit tests for appointment booking tools"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import date, time
from livekit import rtc
from livekit.agents import RunContext

# Import tools
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tools.identify_user import identify_user
from tools.fetch_slots import fetch_slots
from tools.book_appointment import book_appointment
from tools.retrieve_appointments import retrieve_appointments
from tools.cancel_appointment import cancel_appointment
from tools.modify_appointment import modify_appointment
from tools.end_conversation import end_conversation


@pytest.fixture
def mock_context():
    """Create a mock RunContext"""
    context = Mock(spec=RunContext)
    context.room = Mock(spec=rtc.Room)
    context.room.local_participant = Mock()
    context.room.local_participant.publish_data = AsyncMock()
    context.room.name = "test-room"
    context.store = {}
    return context


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client"""
    with patch("tools.identify_user.SupabaseClient.get_client") as mock:
        client = Mock()
        mock.return_value = client
        yield client


class TestIdentifyUser:
    """Tests for identify_user tool"""

    @pytest.mark.asyncio
    async def test_identify_existing_user(self, mock_context, mock_supabase_client):
        """Test identifying an existing user"""
        # Mock database response
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[{"contact_number": "5551234", "name": None}]
        )

        result = await identify_user(mock_context, "555-1234")

        assert "found" in result.lower()
        assert mock_context.store["contact_number"] == "5551234"

    @pytest.mark.asyncio
    async def test_identify_new_user(self, mock_context, mock_supabase_client):
        """Test creating a new user"""
        # Mock database responses
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[]
        )
        mock_supabase_client.table.return_value.insert.return_value.execute.return_value = Mock(
            data=[{"contact_number": "5551234"}]
        )

        result = await identify_user(mock_context, "555-1234")

        assert "created" in result.lower() or "welcome" in result.lower()
        assert mock_context.store["contact_number"] == "5551234"


class TestFetchSlots:
    """Tests for fetch_slots tool"""

    @pytest.mark.asyncio
    async def test_fetch_slots_weekday(self, mock_context, mock_supabase_client):
        """Test fetching slots for a weekday"""
        # Mock database response (no booked slots)
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.neq.return_value.execute.return_value = Mock(
            data=[]
        )

        result = await fetch_slots(mock_context, "2026-01-27")  # Monday

        assert "available" in result.lower()
        assert "AM" in result or "PM" in result

    @pytest.mark.asyncio
    async def test_fetch_slots_weekend(self, mock_context, mock_supabase_client):
        """Test fetching slots for a weekend"""
        result = await fetch_slots(mock_context, "2026-01-25")  # Saturday

        assert "weekend" in result.lower()

    @pytest.mark.asyncio
    async def test_fetch_slots_past_date(self, mock_context, mock_supabase_client):
        """Test fetching slots for a past date"""
        result = await fetch_slots(mock_context, "2020-01-01")

        assert "past" in result.lower()


class TestBookAppointment:
    """Tests for book_appointment tool"""

    @pytest.mark.asyncio
    async def test_book_appointment_success(self, mock_context, mock_supabase_client):
        """Test successfully booking an appointment"""
        mock_context.store["contact_number"] = "5551234"

        # Mock no existing appointment
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.neq.return_value.execute.return_value = Mock(
            data=[]
        )

        # Mock successful insert
        mock_supabase_client.table.return_value.insert.return_value.execute.return_value = Mock(
            data=[{
                "id": "test-id",
                "contact_number": "5551234",
                "appointment_date": "2026-01-27",
                "appointment_time": "09:00"
            }]
        )

        result = await book_appointment(mock_context, "2026-01-27", "09:00", "")

        assert "booked" in result.lower()

    @pytest.mark.asyncio
    async def test_book_appointment_no_user(self, mock_context):
        """Test booking without user identification"""
        result = await book_appointment(mock_context, "2026-01-27", "09:00", "")

        assert "identify" in result.lower() or "phone" in result.lower()


class TestRetrieveAppointments:
    """Tests for retrieve_appointments tool"""

    @pytest.mark.asyncio
    async def test_retrieve_appointments_success(self, mock_context, mock_supabase_client):
        """Test retrieving appointments"""
        mock_context.store["contact_number"] = "5551234"

        # Mock appointments
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value = Mock(
            data=[
                {
                    "id": "apt1",
                    "appointment_date": "2026-01-27",
                    "appointment_time": "09:00",
                    "status": "scheduled"
                }
            ]
        )

        result = await retrieve_appointments(mock_context)

        assert "appointment" in result.lower()

    @pytest.mark.asyncio
    async def test_retrieve_appointments_none(self, mock_context, mock_supabase_client):
        """Test retrieving when no appointments exist"""
        mock_context.store["contact_number"] = "5551234"

        mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value = Mock(
            data=[]
        )

        result = await retrieve_appointments(mock_context)

        assert "don't have" in result.lower() or "no" in result.lower()


class TestCancelAppointment:
    """Tests for cancel_appointment tool"""

    @pytest.mark.asyncio
    async def test_cancel_appointment_success(self, mock_context, mock_supabase_client):
        """Test cancelling an appointment"""
        mock_context.store["contact_number"] = "5551234"

        # Mock appointment exists
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[{
                "id": "apt1",
                "contact_number": "5551234",
                "appointment_date": "2026-01-27",
                "appointment_time": "09:00"
            }]
        )

        # Mock successful update
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value = Mock(
            data=[{"status": "cancelled"}]
        )

        result = await cancel_appointment(mock_context, "apt1")

        assert "cancelled" in result.lower()


class TestModifyAppointment:
    """Tests for modify_appointment tool"""

    @pytest.mark.asyncio
    async def test_modify_appointment_success(self, mock_context, mock_supabase_client):
        """Test modifying an appointment"""
        mock_context.store["contact_number"] = "5551234"

        # Mock appointment exists
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[{
                "id": "apt1",
                "contact_number": "5551234",
                "appointment_date": "2026-01-27",
                "appointment_time": "09:00"
            }]
        )

        # Mock new slot is available
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.neq.return_value.neq.return_value.execute.return_value = Mock(
            data=[]
        )

        # Mock successful update
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value = Mock(
            data=[{"appointment_date": "2026-01-28", "appointment_time": "10:00"}]
        )

        result = await modify_appointment(mock_context, "apt1", "2026-01-28", "10:00")

        assert "moved" in result.lower() or "modified" in result.lower()


class TestEndConversation:
    """Tests for end_conversation tool"""

    @pytest.mark.asyncio
    async def test_end_conversation_success(self, mock_context, mock_supabase_client):
        """Test ending conversation"""
        mock_context.store["contact_number"] = "5551234"

        # Mock appointments
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = Mock(
            data=[]
        )

        # Mock successful log insert
        mock_supabase_client.table.return_value.insert.return_value.execute.return_value = Mock(
            data=[{"id": "log1"}]
        )

        result = await end_conversation(mock_context)

        assert "thank" in result.lower() or "goodbye" in result.lower()
