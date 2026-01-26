import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    room_io,
    metrics,
    MetricsCollectedEvent,
)
from livekit.plugins import noise_cancellation, silero, deepgram, openai, cartesia
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Import configuration
from config import config

# Import system prompt
from prompts.system_prompt import SYSTEM_INSTRUCTIONS

# Import all tools
from tools import (
    identify_user,
    fetch_slots,
    book_appointment,
    retrieve_appointments,
    cancel_appointment,
    modify_appointment,
    end_conversation,
)

# Import utilities
from utils.shared_state import SharedState

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self) -> None:
        # Register all tools with the agent
        # Note: tools are already FunctionTool objects from the import
        tools = [
            identify_user,
            fetch_slots,
            book_appointment,
            retrieve_appointments,
            cancel_appointment,
            modify_appointment,
            end_conversation,
        ]
        
        super().__init__(
            instructions=SYSTEM_INSTRUCTIONS,
            tools=tools,
        )
    
    async def on_agent_response(self, response):
        """
        Override agent response to disable interruptions when agent speaks.
        Reference: https://docs.livekit.io/agents/logic/tools/#interruptions
        """
        # Get session from shared state
        shared_state = SharedState.get_instance()
        session = shared_state.get_session()
        
        if session and hasattr(response, 'text') and response.text:
            # Disable interruptions for all agent speech
            # This ensures user cannot interrupt during tool execution or agent responses
            await session.say(response.text, allow_interruptions=False)
            return True  # Indicate we handled the response
        
        # Let default behavior handle it (shouldn't happen, but fallback)
        return False


server = AgentServer()


def prewarm(proc: JobProcess):
    """Prewarm models for faster startup"""
    # Prewarm VAD (Voice Activity Detection)
    proc.userdata["vad"] = silero.VAD.load()
    # Note: MultilingualModel cannot be prewarmed (requires JobContext)
    # It will be created in entrypoint() when needed


server.setup_fnc = prewarm


def setup_cost_tracking(session: AgentSession, usage_collector: metrics.UsageCollector, shared_state: SharedState):
    """
    Set up metrics-based cost tracking using LiveKit's built-in metrics system.
    
    This uses the official LiveKit metrics API which provides accurate usage data
    for STT, LLM, TTS, and other services. The metrics are automatically collected
    and can be aggregated for cost estimation.
    
    Reference: https://docs.livekit.io/deploy/observability/data/#metrics
    """
    
    # Use LiveKit's metrics_collected event for accurate usage tracking
    @session.on("metrics_collected")
    def on_metrics_collected(ev: MetricsCollectedEvent):
        """
        Collect metrics from LiveKit's built-in metrics system.
        
        This provides accurate data for:
        - STT: audio_duration from STTMetrics
        - LLM: prompt_tokens, completion_tokens from LLMMetrics
        - TTS: characters_count from TTSMetrics
        - Latency: ttft (time to first token), ttfb (time to first byte)
        """
        try:
            # Collect usage metrics
            usage_collector.collect(ev.metrics)
        except Exception:
            pass


async def entrypoint(ctx: JobContext):
    """Main agent session handler - Optimized for fast initialization"""
    # Initialize shared state for this session
    SharedState.reset()  # Clear any previous session data
    shared_state = SharedState.get_instance()
    shared_state.set_room(ctx.room)
    shared_state.session_start_time = datetime.utcnow()
    
    # Initialize usage collector for metrics-based cost tracking
    usage_collector = metrics.UsageCollector()
    shared_state.usage_collector = usage_collector

    # Create assistant instance early (lightweight, no I/O)
    assistant = Assistant()

    try:
        # Create turn detection model (cannot be prewarmed - requires JobContext)
        turn_detection_model = MultilingualModel()

        # Set up voice AI pipeline with custom models
        # Models are created synchronously (no I/O), so direct creation is fastest
        session = AgentSession(
            # Deepgram STT - Speech-to-text
            stt=deepgram.STT(
                model="nova-2-conversationalai",
                language="en-US",
                api_key=config.deepgram_api_key,
            ),
            # Azure OpenAI LLM - Language model
            llm=openai.LLM.with_azure(
                azure_deployment=config.azure_openai_deployment,
                azure_endpoint=config.azure_openai_endpoint,
                api_key=config.azure_openai_api_key,
                api_version=config.azure_openai_api_version,
                temperature=0,  # Deterministic responses, strict tool calling
            ),
            # Cartesia TTS - Text-to-speech
            tts=cartesia.TTS(
                model="sonic-3",
                voice="95d51f79-c397-46f9-b49a-23763d3eaa2d",
                api_key=config.cartesia_api_key,
            ),
            # Turn detection and VAD (using prewarmed models)
            turn_detection=turn_detection_model,
            vad=ctx.proc.userdata["vad"],
            allow_interruptions=False
        )

        # Optional: Configure avatar if credentials provided
        avatar_session = None
        if config.avatar_api_key and config.avatar_id:
            try:
                from livekit.plugins import bey
                
                # Convert LiveKit URL to WebSocket format if needed
                # Beyond Presence API requires wss:// format, not https://
                # The bey plugin reads LIVEKIT_URL from environment, so we need to set it
                livekit_url = config.livekit_url
                if livekit_url.startswith("https://"):
                    # Convert https:// to wss://
                    livekit_url = livekit_url.replace("https://", "wss://", 1)
                elif not livekit_url.startswith(("ws://", "wss://")):
                    # If it's not already a WebSocket URL, assume wss://
                    if livekit_url.startswith("http://"):
                        livekit_url = livekit_url.replace("http://", "ws://", 1)
                    else:
                        # If no protocol, assume wss://
                        livekit_url = f"wss://{livekit_url}"
                
                # Set the environment variable so bey plugin can read it
                # This ensures the avatar API gets the correct WebSocket URL format
                os.environ["LIVEKIT_URL"] = livekit_url
                
                avatar_session = bey.AvatarSession(
                    avatar_id=config.avatar_id,
                    api_key=config.avatar_api_key,
                )
            except (ImportError, Exception):
                pass

        # ✅ CONNECT IMMEDIATELY - Signal readiness to LiveKit
        await ctx.connect()

        # ✅ OPTIMIZATION: Wait for participant FIRST (before creating expensive session)
        # This ensures we don't waste resources if participant never joins
        participant = await ctx.wait_for_participant()
        shared_state.set_participant(participant)
        
        # Track session start time after participant joins
        shared_state.session_start_time = datetime.utcnow()

        # Start the agent session IMMEDIATELY (voice starts right away)
        await session.start(
            agent=assistant,
            room=ctx.room,
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(
                    noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC(),
                ),
            ),
        )

        # Store session in shared state (for chat context access)
        shared_state.set_session(session)
        
        # Set up metrics-based cost tracking
        setup_cost_tracking(session, usage_collector, shared_state)

        # ✅ Start avatar in BACKGROUND (non-blocking)
        # Avatar will join when ready and automatically take over audio/video
        # Reference: https://docs.livekit.io/agents/models/avatar/
        if avatar_session:
            async def start_avatar_background():
                try:
                    await avatar_session.start(session, room=ctx.room)
                except Exception:
                    pass
            
            # Start avatar in background task (non-blocking)
            asyncio.create_task(start_avatar_background())
        
        # ✅ Send greeting IMMEDIATELY (voice starts, avatar joins in background)
        await session.say(
            "Hello! I'm Alex, your appointment assistant. I can assist you in booking, cancelling, and modifying appointments. May I have your phone number to look up your account?",
            allow_interruptions=False  # Disallow interruptions - user should wait for agent to finish
        )
        
        # Note: Session will continue running until user ends the conversation
        # Final costs and avatar duration are logged in end_conversation tool

    except Exception:
        raise


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name="my-voice-agent"
        )
    )
