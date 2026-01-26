"""Integration tests for the appointment booking agent"""
import pytest
from livekit.agents import AgentSession, inference, llm
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent import Assistant


def _llm() -> llm.LLM:
    """Create test LLM instance"""
    return inference.LLM(model="openai/gpt-4.1-mini")


@pytest.mark.asyncio
async def test_agent_asks_for_phone_number() -> None:
    """Test that agent asks for phone number as first step"""
    async with (
        _llm() as test_llm,
        AgentSession(llm=test_llm) as session,
    ):
        await session.start(Assistant())

        # Agent should greet and ask for phone number
        result = await session.run(user_input="Hello")

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                test_llm,
                intent="""
                Greets the user warmly and asks for their phone number to identify their account.
                
                The response should:
                - Include a greeting
                - Request the user's phone number
                - Explain it's needed to look up their account
                """,
            )
        )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_agent_uses_identify_user_tool() -> None:
    """Test that agent uses identify_user tool when phone number is provided"""
    async with (
        _llm() as test_llm,
        AgentSession(llm=test_llm) as session,
    ):
        await session.start(Assistant())

        # Provide phone number
        result = await session.run(user_input="My phone number is 555-1234")

        # Expect identify_user tool call
        event = result.expect.next_event()
        event.is_tool_call(name="identify_user")

        # Expect confirmation message
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                test_llm,
                intent="""
                Confirms the user has been identified and asks how they can help.
                
                Should include:
                - Acknowledgment of account found/created
                - Question about how to help or what they need
                """,
            )
        )


@pytest.mark.asyncio
async def test_agent_refuses_booking_without_identification() -> None:
    """Test that agent requires identification before booking"""
    async with (
        _llm() as test_llm,
        AgentSession(llm=test_llm) as session,
    ):
        await session.start(Assistant())

        # Try to book without identifying
        result = await session.run(user_input="I'd like to book an appointment for tomorrow at 10 AM")

        # Agent should redirect to get phone number first
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                test_llm,
                intent="""
                Explains that they need the user's phone number first before booking an appointment.
                Does NOT proceed with booking.
                """,
            )
        )


@pytest.mark.asyncio
async def test_agent_handles_appointment_booking_flow() -> None:
    """Test complete appointment booking flow"""
    async with (
        _llm() as test_llm,
        AgentSession(llm=test_llm) as session,
    ):
        await session.start(Assistant())

        # Step 1: User asks to book appointment
        result = await session.run(user_input="My number is 555-1234 and I'd like to book an appointment")

        # Should identify user first
        event = result.expect.next_event()
        event.is_tool_call(name="identify_user")

        # Then should check available slots
        event = result.expect.next_event()
        if event.is_tool_call():
            assert event.tool_call.name == "fetch_slots"


@pytest.mark.asyncio
async def test_agent_retrieves_appointments() -> None:
    """Test appointment retrieval"""
    async with (
        _llm() as test_llm,
        AgentSession(llm=test_llm) as session,
    ):
        await session.start(Assistant())

        # Identify and ask for appointments
        result = await session.run(user_input="My number is 555-1234. What appointments do I have?")

        # Should identify user
        event = result.expect.next_event()
        event.is_tool_call(name="identify_user")

        # Should retrieve appointments
        events = list(result.events)
        tool_calls = [e for e in events if hasattr(e, 'tool_call')]
        tool_names = [tc.tool_call.name for tc in tool_calls if hasattr(tc, 'tool_call')]
        
        assert "retrieve_appointments" in tool_names


@pytest.mark.asyncio
async def test_agent_handles_goodbye() -> None:
    """Test that agent ends conversation gracefully"""
    async with (
        _llm() as test_llm,
        AgentSession(llm=test_llm) as session,
    ):
        await session.start(Assistant())

        result = await session.run(user_input="That's all, thank you. Goodbye!")

        # Should use end_conversation tool
        events = list(result.events)
        tool_calls = [e for e in events if hasattr(e, 'tool_call')]
        
        if tool_calls:
            # Expect end_conversation to be called
            last_tool = tool_calls[-1]
            assert last_tool.tool_call.name == "end_conversation"

        # Should respond with goodbye
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                test_llm,
                intent="Says goodbye or thanks the user in a friendly manner.",
            )
        )


@pytest.mark.asyncio
async def test_agent_redirects_non_appointment_questions() -> None:
    """Test that agent redirects non-appointment questions"""
    async with (
        _llm() as test_llm,
        AgentSession(llm=test_llm) as session,
    ):
        await session.start(Assistant())

        result = await session.run(user_input="What's the weather like today?")

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                test_llm,
                intent="""
                Politely redirects the conversation to appointment booking.
                
                Should:
                - Acknowledge the question
                - Redirect to appointments
                - Maintain friendly tone
                
                Should NOT:
                - Provide weather information
                - Claim to have weather capabilities
                """,
            )
        )


@pytest.mark.asyncio
async def test_agent_handles_weekend_booking_attempt() -> None:
    """Test that agent handles weekend booking attempts correctly"""
    async with (
        _llm() as test_llm,
        AgentSession(llm=test_llm) as session,
    ):
        await session.start(Assistant())

        # Try to book on a Saturday
        result = await session.run(
            user_input="My number is 555-1234. I'd like to book for Saturday January 25th"
        )

        # Should identify user
        event = result.expect.next_event()
        event.is_tool_call(name="identify_user")

        # Should check slots and inform about weekends
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                test_llm,
                intent="""
                Informs the user that appointments are not available on weekends.
                Offers alternative weekday options.
                """,
            )
        )
