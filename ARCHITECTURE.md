# Voice Agent Architecture Documentation

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Layers](#architecture-layers)
3. [Data Flow](#data-flow)
4. [Core Components](#core-components)
5. [Service Layer](#service-layer)
6. [Tool System](#tool-system)
7. [State Management](#state-management)
8. [Database Schema](#database-schema)
9. [Event System](#event-system)
10. [Cost Tracking](#cost-tracking)
11. [Error Handling](#error-handling)
12. [Performance Optimizations](#performance-optimizations)

---

## System Overview

The Voice Agent is a production-ready appointment booking system built on LiveKit Agents framework. It provides natural voice interaction for scheduling, modifying, and canceling appointments.

### Key Design Principles

1. **Separation of Concerns**: Services, tools, and utilities are cleanly separated
2. **Fail-Safe Operations**: Graceful degradation when services are unavailable
3. **Real-time Communication**: Immediate feedback to frontend via LiveKit data messages
4. **Scalability**: Worker-based architecture for handling multiple concurrent calls
5. **Observability**: Comprehensive logging and metrics collection

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Speech-to-Text** | Deepgram Nova-3 | Transcribe user speech to text |
| **Language Model** | Azure OpenAI (GPT-4) | Natural language understanding & generation |
| **Text-to-Speech** | Cartesia Sonic 3 | Convert agent responses to natural speech |
| **Avatar** | Beyond Presence (optional) | Visual representation of the agent |
| **Database** | Supabase (PostgreSQL) | Persistent storage |
| **Framework** | LiveKit Agents | Voice agent orchestration |
| **Runtime** | Python 3.13 + uv | Execution environment |

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend Layer                            │
│                    (React + LiveKit Client)                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │ WebRTC + Data Messages
┌───────────────────────────▼─────────────────────────────────────┐
│                      LiveKit Cloud/Server                        │
│                    (Room & Media Routing)                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Job Dispatch
┌───────────────────────────▼─────────────────────────────────────┐
│                      Agent Layer (Python)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Agent Session                         │   │
│  │  STT Pipeline → LLM Pipeline → TTS Pipeline → Avatar    │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Service Layer                         │   │
│  │  • EventService    • CallService    • CostService        │   │
│  │  • SummaryService  • TranscriptService                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Tool Layer                            │   │
│  │  • identify_user        • fetch_slots                    │   │
│  │  • book_appointment     • retrieve_appointments          │   │
│  │  • cancel_appointment   • modify_appointment             │   │
│  │  • end_conversation                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌──────▼───────┐  ┌────────▼──────┐
│  AI Services   │  │  Supabase DB │  │  LiveKit APIs │
│  • Deepgram    │  │  • users     │  │  • Metrics    │
│  • Azure OpenAI│  │  • slots     │  │  • Room Mgmt  │
│  • Cartesia    │  │  • appts     │  │  • Data Msgs  │
│  • Avatar API  │  │  • logs      │  └───────────────┘
└────────────────┘  └──────────────┘
```

---

## Data Flow

### 1. Call Initialization Flow

```
User Connects → LiveKit creates room → Dispatches job to agent worker
                                            ↓
                                   prewarm() loads models
                                            ↓
                                   entrypoint() creates session
                                            ↓
                                   Agent greets user
```

### 2. Conversation Flow

```
User speaks → Deepgram STT → Text to LLM → GPT-4 processes
                                                ↓
                                    Decision: Response or Tool Call?
                                                ↓
                        ┌───────────────────────┴────────────────────┐
                        │                                            │
                   Tool Call                                    Text Response
                        │                                            │
                Tool executes                                 Cartesia TTS
                        │                                            │
                Updates database                              Audio to user
                        │                                            │
                Emits event to frontend                       Avatar animates
                        │                                            │
                Returns result to LLM ──────────────────────────────┘
                        │
                LLM generates confirmation
                        │
                Cartesia TTS → Audio to user
```

### 3. State Flow

```
SharedState (Singleton)
    ↓
Created at session start
    ↓
Populated by tools:
    • contact_number (identify_user)
    • tool_calls (all tools)
    • user_preferences (book_appointment, modify_appointment)
    • usage_collector (metrics_collected event)
    ↓
Read by end_conversation:
    • Generate summary
    • Calculate costs
    • Extract transcript
    • Emit to frontend
    • Save to database
```

---

## Core Components

### 1. Agent Session (`src/agent.py`)

**Responsibility**: Orchestrate the entire voice agent lifecycle

**Key Features**:
- Model prewarming (VAD, turn detection)
- STT/LLM/TTS pipeline configuration
- Event listener setup
- Metrics collection
- Tool registration

**Important Functions**:
```python
def prewarm(proc: JobProcess):
    """Load heavy models once per worker process"""
    # Loads VAD and turn detection models
    # Reduces per-call latency by ~2-3 seconds

async def entrypoint(ctx: JobContext):
    """Main entrypoint for each call"""
    # Configures session
    # Registers event listeners
    # Starts conversation
```

### 2. Assistant Class (`src/agent.py`)

**Responsibility**: Custom agent with tool registration

**Why Needed**: LiveKit requires tools to be passed to a custom `Agent` subclass

**Key Features**:
- Inherits from `Agent`
- Registers all 7 function tools
- Passes instructions to LLM

---

## Service Layer

The service layer encapsulates complex business logic, making tools simpler and more maintainable.

### 1. EventService (`src/services/event_service.py`)

**Purpose**: Send real-time events to frontend via LiveKit data messages

**Methods**:
- `emit_tool_call()`: Notify frontend of tool execution (started/success/error)
- `emit_summary()`: Send call summary with appointments, costs, and duration

**Why Important**: Enables real-time UI updates without polling

**Example**:
```python
await EventService.emit_tool_call(
    room=room,
    tool_name="book_appointment",
    status="success",
    data={"appointment": {...}}
)
```

### 2. CallService (`src/services/call_service.py`)

**Purpose**: Manage WebRTC call lifecycle

**Methods**:
- `schedule_disconnect()`: Gracefully end call after delay

**Why Needed**: 
- Ensures summary is delivered before disconnect
- Prevents abrupt call termination

**Implementation**:
```python
await CallService.schedule_disconnect(
    participant=participant,
    delay_seconds=8  # Time for summary delivery
)
```

### 3. CostService (`src/services/cost_service.py`)

**Purpose**: Calculate accurate API costs from LiveKit metrics

**Methods**:
- `calculate_costs()`: Parse UsageSummary and apply pricing

**Pricing (as of 2026)**:
- STT: $0.0043/minute
- LLM Input: $0.0015/1K tokens
- LLM Output: $0.002/1K tokens
- TTS: $0.00001/character
- Avatar: $0.006/minute

**Why Accurate**: Uses LiveKit's `metrics.UsageCollector` instead of manual estimates

### 4. SummaryService (`src/services/summary_service.py`)

**Purpose**: Generate professional call summaries

**Method**:
- `generate_summary()`: Create rule-based summary from appointments and preferences

**Output Format**:
```
📞 Call Summary
• User: +918860141821 (Existing customer)
• Duration: 2 minutes

Actions Taken:
• Booked 1 appointment

Booked Appointments:
• Monday, January 27, 2026 at 2:00 PM

User Preferences:
• Prefers afternoon appointments
• Typically books on Monday

Thank you for using our appointment booking service!
```

### 5. TranscriptService (`src/services/transcript_service.py`)

**Purpose**: Extract and format conversation transcripts from LiveKit's ChatContext

**Methods**:
- `extract_conversation_from_chat_ctx()`: Parse chat items into structured format
- `format_transcript_for_llm()`: Format for LLM consumption

**Why Needed**: ChatContext items are complex objects; this service normalizes them

**Output Format**:
```json
{
  "messages": [
    {
      "role": "user",
      "content": "I want to book an appointment",
      "timestamp": "2026-01-26T10:30:00Z"
    },
    {
      "role": "assistant",
      "content": "I'd be happy to help you book an appointment",
      "timestamp": "2026-01-26T10:30:01Z"
    },
    {
      "role": "function",
      "name": "fetch_slots",
      "params": {"appointment_date": "2026-01-27"},
      "result": "slots fetched",
      "timestamp": "2026-01-26T10:30:05Z"
    }
  ],
  "tool_calls_count": 1
}
```

---

## Tool System

### Design Pattern

All tools follow this pattern:

```python
@function_tool
async def tool_name(
    context: RunContext,
    param1: str,
    param2: int = 0
) -> str:
    """
    Tool description for LLM.
    
    Args:
        param1: Description (LLM reads this)
        param2: Description with default
        
    Returns:
        Natural language response for LLM to read to user
    """
    try:
        # 1. Get shared state
        shared_state = SharedState.get_instance()
        room = shared_state.room
        
        # 2. Validate prerequisites
        if not shared_state.contact_number:
            return "Error: User not identified"
        
        # 3. Emit "started" event
        await EventService.emit_tool_call(room, "tool_name", "started", {})
        
        # 4. Execute business logic
        result = perform_operation()
        
        # 5. Update shared state
        shared_state.tool_calls.append({...})
        
        # 6. Emit "success" event
        await EventService.emit_tool_call(room, "tool_name", "success", result)
        
        # 7. Return natural language response
        return "Success! I've completed the operation."
        
    except Exception as e:
        logger.error(f"Error in tool_name: {e}")
        await EventService.emit_tool_call(room, "tool_name", "error", {"error": str(e)})
        return "I'm sorry, I encountered an error. Please try again."
```

### Tool Catalog

| Tool | Purpose | Prerequisites | Side Effects |
|------|---------|---------------|--------------|
| `identify_user` | Find/create user by phone | None (always first) | Sets `contact_number` in state |
| `fetch_slots` | Get available time slots | User identified | None |
| `book_appointment` | Create appointment | User identified, slot available | Marks slot unavailable, updates preferences |
| `retrieve_appointments` | List user's appointments | User identified | None |
| `cancel_appointment` | Cancel appointment | User identified, appointment exists | Marks slot available |
| `modify_appointment` | Change appointment time | User identified, appointment exists, new slot available | Frees old slot, marks new slot unavailable, updates preferences |
| `end_conversation` | End call & generate summary | None | Saves transcript, emits summary, schedules disconnect |

---

## State Management

### SharedState Singleton

**Location**: `src/utils/shared_state.py`

**Purpose**: Share data across tools within a single session

**Why Singleton**: Tools don't share scope; need centralized state

**Fields**:
```python
class SharedState:
    contact_number: Optional[str]              # Identified user's phone
    room: Optional[rtc.Room]                   # LiveKit room instance
    participant: Optional[rtc.RemoteParticipant] # Remote participant
    session: Optional[AgentSession]            # Agent session
    session_start_time: Optional[datetime]     # Call start time
    tool_calls: List[Dict]                     # Tool execution history
    conversation_messages: List[Dict]          # Fallback message store
    user_preferences: Dict[str, Any]           # Learned preferences
    usage_collector: Optional[UsageCollector]  # Metrics collector
    data: Dict[str, Any]                       # Generic key-value store
```

**Lifecycle**:
1. Created at session start (singleton)
2. Populated by tools throughout call
3. Read by `end_conversation`
4. Cleared on session end (worker process persists)

**Thread Safety**: Not needed (single-threaded async runtime)

---

## Database Schema

### Tables

#### 1. `users`
```sql
CREATE TABLE users (
    contact_number TEXT PRIMARY KEY,  -- Phone number (unique identifier)
    name TEXT,                         -- User's name (optional)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 2. `slots`
```sql
CREATE TABLE slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slot_date DATE NOT NULL,
    slot_time TIME NOT NULL,
    duration_minutes INTEGER DEFAULT 30,
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(slot_date, slot_time)  -- Prevent duplicate slots
);
```

#### 3. `appointments`
```sql
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_number TEXT REFERENCES users(contact_number),
    slot_id UUID REFERENCES slots(id),
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    duration_minutes INTEGER DEFAULT 30,
    status TEXT DEFAULT 'scheduled',  -- scheduled, cancelled
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(slot_id),                  -- Race condition prevention
    UNIQUE(appointment_date, appointment_time)
);
```

**Race Condition Prevention**: `UNIQUE(slot_id)` ensures database-level double-booking prevention

#### 4. `conversation_logs`
```sql
CREATE TABLE conversation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    contact_number TEXT REFERENCES users(contact_number),
    transcript JSONB NOT NULL DEFAULT '{}',
    summary TEXT,
    tool_calls JSONB,
    duration_seconds INTEGER,
    cost_breakdown JSONB,
    user_preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Event System

### Frontend Event Protocol

**Transport**: LiveKit data messages (WebRTC data channel)

**Format**: JSON strings encoded as UTF-8

### Event Types

#### 1. Tool Call Event
```json
{
  "type": "tool_call",
  "tool": "book_appointment",
  "status": "started" | "success" | "error",
  "data": {
    "appointment": {...} | "error": "..."
  },
  "timestamp": "2026-01-26T10:30:00.123Z"
}
```

**Use Case**: Real-time UI updates during tool execution

#### 2. Call Summary Event
```json
{
  "type": "call_summary",
  "summary": "User booked 1 appointment...",
  "appointments": [
    {
      "id": "uuid",
      "date": "2026-01-27",
      "time": "14:00",
      "status": "scheduled"
    }
  ],
  "user_preferences": {
    "preferred_time": "afternoon",
    "preferred_days": ["Monday"]
  },
  "cost_breakdown": {
    "stt": 0.0129,
    "llm_input": 0.0421,
    "llm_output": 0.0049,
    "tts": 0.0058,
    "avatar": 0.0120,
    "total": 0.0777
  },
  "duration_seconds": 120,
  "timestamp": "2026-01-26T10:35:00.123Z"
}
```

**Use Case**: Display final call summary to user

---

## Cost Tracking

### Implementation

**Collector**: `metrics.UsageCollector` (LiveKit SDK)

**Event**: `@session.on("metrics_collected")`

**Metrics Available**:
- `stt_audio_duration`: Seconds of transcribed audio
- `llm_prompt_tokens`: Input tokens to LLM
- `llm_prompt_cached_tokens`: Cached input tokens (cheaper)
- `llm_completion_tokens`: Output tokens from LLM
- `tts_characters_count`: Characters synthesized
- `tts_audio_duration`: Not used for avatar (use session duration)

### Cost Calculation

```python
# STT: Deepgram Nova-3
stt_cost = (stt_audio_duration / 60) * 0.0043

# LLM: Azure OpenAI GPT-4
llm_input_cost = (llm_prompt_tokens / 1000) * 0.0015
llm_output_cost = (llm_completion_tokens / 1000) * 0.002

# TTS: Cartesia Sonic 3
tts_cost = tts_characters_count * 0.00001

# Avatar: Beyond Presence
avatar_cost = (session_duration / 60) * 0.006

# Total
total_cost = stt_cost + llm_input_cost + llm_output_cost + tts_cost + avatar_cost
```

---

## Error Handling

### Principles

1. **Fail Gracefully**: Never crash the agent
2. **User-Friendly Messages**: LLM reads errors to user naturally
3. **Detailed Logging**: Log full tracebacks for debugging
4. **Emit Events**: Notify frontend of errors

### Pattern

```python
try:
    # Risky operation
    result = database_call()
except SpecificError as e:
    logger.error(f"Specific error: {e}", exc_info=True)
    await EventService.emit_tool_call(room, "tool", "error", {"error": str(e)})
    return "I'm sorry, something went wrong. Could you try again?"
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    await EventService.emit_tool_call(room, "tool", "error", {"error": "Unknown error"})
    return "I apologize, I encountered an unexpected issue. Let me try again."
```

### Common Error Scenarios

| Scenario | Handling |
|----------|----------|
| Database connection failure | Log error, return generic message to user |
| Slot already booked (race condition) | Caught by UNIQUE constraint, offer alternatives |
| User not identified | Check `contact_number` before operations |
| Invalid appointment ID | Validate UUID format, query database |
| Network timeout | Retry with exponential backoff (LiveKit handles) |

---

## Performance Optimizations

### 1. Model Prewarming

**Problem**: Loading VAD and turn detection models takes ~2-3 seconds per call

**Solution**: Load once per worker process in `prewarm()`

```python
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()
    # Turn detection loaded in entrypoint (needs job context)
```

**Impact**: Reduces per-call startup latency from ~5s to ~2s

### 2. Database Indexing

**Indexes**:
```sql
CREATE INDEX idx_slots_date ON slots(slot_date);
CREATE INDEX idx_slots_date_time ON slots(slot_date, slot_time);
CREATE INDEX idx_slots_available ON slots(is_available);
CREATE INDEX idx_appointments_contact ON appointments(contact_number);
CREATE INDEX idx_appointments_date ON appointments(appointment_date);
CREATE INDEX idx_appointments_status ON appointments(status);
CREATE INDEX idx_appointments_slot ON appointments(slot_id);
CREATE INDEX idx_conversation_logs_session ON conversation_logs(session_id);
```

**Impact**: Query times < 10ms for typical operations

### 3. Async I/O

**Pattern**: All I/O operations are async

```python
# Database calls
result = await asyncio.to_thread(client.table("users").select("*").execute)

# Event emission
await EventService.emit_tool_call(...)
```

**Impact**: Non-blocking operations, better concurrency

### 4. Fire-and-Forget Tasks

**Use Case**: Non-critical operations that shouldn't block user flow

```python
asyncio.create_task(update_memory_task())  # Don't await
```

**Examples**:
- Memory updates
- Analytics logging
- Leadquare pushes (if applicable)

---

## Deployment Architecture

### Worker Processes

```
LiveKit Server
    ↓
Dispatches jobs to agent workers
    ↓
┌─────────────┬─────────────┬─────────────┐
│  Worker 1   │  Worker 2   │  Worker 3   │
│  (Process)  │  (Process)  │  (Process)  │
│             │             │             │
│  prewarm()  │  prewarm()  │  prewarm()  │
│  loaded     │  loaded     │  loaded     │
│             │             │             │
│  ┌──────┐   │  ┌──────┐   │  ┌──────┐   │
│  │Call A│   │  │Call C│   │  │Call E│   │
│  └──────┘   │  └──────┘   │  └──────┘   │
│  ┌──────┐   │  ┌──────┐   │             │
│  │Call B│   │  │Call D│   │             │
│  └──────┘   │  └──────┘   │             │
└─────────────┴─────────────┴─────────────┘
```

**Scaling**: Add more workers to handle more concurrent calls

---

## Security Considerations

### 1. API Keys

- Never commit to version control
- Use environment variables
- Rotate regularly

### 2. Database Access

- Use connection pooling
- Sanitize inputs (Supabase client handles)
- Use parameterized queries

### 3. Phone Number Privacy

- Hash before logging (if needed)
- Don't expose in frontend events
- GDPR compliance: allow user data deletion

### 4. Rate Limiting

- Implement at API gateway level
- Prevent abuse of expensive LLM calls

---

## Monitoring & Observability

### Logging Levels

```python
logger.debug()   # Detailed trace (development)
logger.info()    # Important events (production)
logger.warning() # Recoverable issues
logger.error()   # Errors that need attention
```

### Key Metrics to Track

1. **Call Metrics**
   - Total calls
   - Average duration
   - Success rate

2. **Tool Metrics**
   - Tool call frequency
   - Error rates per tool
   - Execution times

3. **Cost Metrics**
   - Daily spend
   - Cost per call
   - Cost by service (STT/LLM/TTS/Avatar)

4. **User Metrics**
   - New users
   - Repeat users
   - Appointments booked

---

## Future Enhancements

### Potential Improvements

1. **Calendar Integration**
   - Google Calendar sync
   - Outlook integration

2. **Advanced Scheduling**
   - Recurring appointments
   - Multi-timezone support
   - Appointment reminders

3. **Enhanced AI**
   - Context from previous calls
   - Sentiment analysis
   - Language detection

4. **Analytics Dashboard**
   - Real-time metrics
   - Cost tracking
   - User behavior insights

5. **Multi-tenancy**
   - Multiple clinics/practices
   - Custom branding per tenant

---

## Appendix

### File Structure Reference

```
src/
├── agent.py                        # Main entrypoint
├── config.py                       # Configuration
├── database/
│   ├── client.py                   # Supabase client
│   └── models.py                   # Pydantic models
├── prompts/
│   └── system_prompt.py            # LLM instructions
├── services/
│   ├── call_service.py             # Call lifecycle management
│   ├── cost_service.py             # Cost calculation
│   ├── event_service.py            # Frontend event emission
│   ├── summary_service.py          # Summary generation
│   └── transcript_service.py       # Transcript extraction
├── tools/
│   ├── identify_user.py            # User identification
│   ├── fetch_slots.py              # Slot fetching
│   ├── book_appointment.py         # Appointment booking
│   ├── retrieve_appointments.py    # Appointment retrieval
│   ├── cancel_appointment.py       # Appointment cancellation
│   ├── modify_appointment.py       # Appointment modification
│   └── end_conversation.py         # Call ending & summary
└── utils/
    ├── date_time_utils.py          # Date/time helpers
    ├── preference_tracker.py       # User preference tracking
    └── shared_state.py             # Singleton state management
```

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-26  
**Author**: Voice Agent Team
