# Voice Agent Backend - Appointment Booking System

A complete AI voice agent backend for appointment booking built with LiveKit Agents, using Deepgram (STT), Azure OpenAI (LLM), Cartesia (TTS), and Supabase for data persistence.

📚 **[Read the Architecture Documentation](ARCHITECTURE.md)** for detailed system design, data flow, and implementation details.

## Features

- 🎙️ **Voice Conversation**: Natural voice interaction with <3s response latency
- 👤 **User Identification**: Phone number-based user management
- 📅 **Appointment Management**: Book, retrieve, modify, and cancel appointments
- 🤖 **7 Function Tools**: Complete appointment workflow automation
- 📊 **Call Summaries**: Automatic conversation summaries with accurate cost tracking
- 🎯 **User Preferences**: Automatic tracking of preferred times and days (NEW)
- 💰 **Accurate Cost Tracking**: LiveKit metrics-based cost calculation (not estimates)
- 🎭 **Avatar Support**: Optional integration with Beyond Presence or Tavus
- 📡 **Frontend Events**: Real-time tool call events via LiveKit data messages
- 🗄️ **Supabase Database**: Persistent storage for users, appointments, slots, and conversation logs
- 🏗️ **Service Architecture**: Clean separation of business logic for maintainability

## Architecture

```
Frontend (React) ←→ LiveKit Room ←→ Python Voice Agent (This Repo)
                                            ↓
                                    ┌───────┴────────┐
                                    ↓                ↓
                            AI Services        Supabase DB
                            - Deepgram STT     - Users
                            - Azure OpenAI     - Appointments
                            - Cartesia TTS     - Conversation Logs
                            - Avatar (opt)
```

## Project Structure

```
src/
├── agent.py                        # Main agent entrypoint
├── config.py                       # Configuration management
├── prompts/
│   └── system_prompt.py           # Agent instructions
├── database/
│   ├── client.py                  # Supabase client
│   └── models.py                  # Pydantic models
├── services/                       # 🆕 Business logic layer
│   ├── call_service.py            # Call lifecycle management
│   ├── cost_service.py            # Cost calculation from metrics
│   ├── event_service.py           # Frontend event emission
│   ├── summary_service.py         # Summary generation
│   └── transcript_service.py      # Transcript extraction
├── tools/
│   ├── identify_user.py           # User identification
│   ├── fetch_slots.py             # Get available slots
│   ├── book_appointment.py        # Book appointments
│   ├── retrieve_appointments.py   # Get user appointments
│   ├── cancel_appointment.py      # Cancel appointments
│   ├── modify_appointment.py      # Modify appointments
│   └── end_conversation.py        # End call & summary
└── utils/
    ├── date_time_utils.py         # Date/time formatting (IST)
    ├── preference_tracker.py      # 🆕 User preference tracking
    └── shared_state.py            # Session state management
```

## Setup Instructions

### 1. Prerequisites

- Python 3.10 - 3.13
- [uv](https://docs.astral.sh/uv/) package manager
- LiveKit Cloud account (or self-hosted LiveKit)
- Supabase account
- API keys for:
  - Deepgram
  - Azure OpenAI
  - Cartesia
  - Beyond Presence or Tavus (optional)

### 2. Clone and Install Dependencies

```bash
cd voice-agent-backend
uv sync
```

### 3. Set Up Supabase Database

Create a Supabase project and run the SQL from `supabase_schema.sql`:

```bash
# Run the complete schema
psql -h your-project.supabase.co -U postgres -d postgres -f supabase_schema.sql
```

**Or** run it manually in Supabase SQL Editor. The schema includes:

**Tables:**
- `users`: User profiles (phone number, name)
- `slots`: Available appointment slots (date, time, availability)
- `appointments`: Booked appointments (with race condition prevention)
- `conversation_logs`: Call transcripts and summaries

**Key Features:**
- `UNIQUE(slot_id)` in `appointments`: Prevents double-booking at database level
- `user_preferences JSONB`: Stores learned preferences
- `cost_breakdown JSONB`: Accurate cost tracking
- Comprehensive indexes for performance

**See `supabase_schema.sql` for the complete schema with indexes and sample data.**

### 4. Configure Environment Variables

Create a `.env.local` file in the root directory:

```bash
# LiveKit Configuration
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# AI Services
DEEPGRAM_API_KEY=your-deepgram-key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
CARTESIA_API_KEY=your-cartesia-key

# Avatar (optional)
AVATAR_PROVIDER=beyond_presence
BEYOND_PRESENCE_API_KEY=your-avatar-key
AVATAR_ID=your-avatar-id

# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
```

You can use the LiveKit CLI to set up LiveKit credentials:

```bash
lk cloud auth
lk app env -w -d .env.local
```

### 5. Download Required Models

Before first run, download VAD and turn detector models:

```bash
uv run python src/agent.py download-files
```

### 6. Run the Agent

**For development with terminal interaction:**

```bash
uv run python src/agent.py console
```

**For development with frontend:**

```bash
uv run python src/agent.py dev
```

**For production:**

```bash
uv run python src/agent.py start
```

## Conversation Flow

The agent follows this strict conversation flow:

1. **User Identification** (Mandatory First Step)
   - Greets user
   - Asks for phone number
   - Calls `identify_user` tool
   - Confirms account found/created

2. **Discover Intent**
   - Asks how to help
   - Listens for: book, modify, cancel, or retrieve appointments

3. **Handle Request**
   - Uses appropriate tools based on user intent
   - Confirms all actions verbally

4. **Check for More Requests**
   - Asks if user needs anything else
   - Returns to step 3 if yes

5. **End Conversation**
   - Calls `end_conversation` tool
   - Generates and emits summary
   - Says goodbye

## Available Tools

### 1. `identify_user(contact_number)`
Identifies or creates a user by phone number. **Must be called first.**

### 2. `fetch_slots(appointment_date)`
Returns available appointment slots for a given date. Hard-coded slots:
- Monday-Friday: 9 AM, 10 AM, 11 AM, 2 PM, 3 PM, 4 PM
- No weekends
- 30-minute appointments

### 3. `book_appointment(appointment_date, appointment_time, notes)`
Books an appointment with double-booking prevention.

### 4. `retrieve_appointments()`
Retrieves all appointments for the identified user.

### 5. `cancel_appointment(appointment_id)`
Cancels an appointment (marks as cancelled, doesn't delete).

### 6. `modify_appointment(appointment_id, new_date, new_time)`
Modifies an existing appointment to a new date/time.

### 7. `end_conversation()`
Ends conversation, generates summary, calculates costs, emits to frontend.

## Frontend Integration

### Event Protocol

The backend emits events to the frontend via LiveKit data messages:

**Tool Call Event:**
```json
{
  "type": "tool_call",
  "tool": "book_appointment",
  "status": "started|success|error",
  "data": {...},
  "timestamp": "2026-01-24T10:30:00Z"
}
```

**Call Summary Event:**
```json
{
  "type": "call_summary",
  "summary": "User booked 2 appointments...",
  "appointments": [...],
  "cost_breakdown": {...},
  "timestamp": "2026-01-24T10:35:00Z"
}
```

### Frontend Implementation (React)

```typescript
import { Room, RoomEvent } from 'livekit-client';

room.on(RoomEvent.DataReceived, (payload: Uint8Array) => {
  const decoder = new TextDecoder();
  const event = JSON.parse(decoder.decode(payload));
  
  if (event.type === 'tool_call') {
    // Display tool call in UI
    displayToolCall(event.tool, event.status, event.data);
  } else if (event.type === 'call_summary') {
    // Display call summary
    displaySummary(event.summary, event.appointments, event.cost_breakdown);
  }
});
```

## Testing

### Run Unit Tests

```bash
uv run pytest tests/test_tools.py -v
```

### Run Integration Tests

```bash
uv run pytest tests/test_agent.py -v
```

### Run All Tests

```bash
uv run pytest
```

## User Preferences Tracking

The agent automatically learns and tracks user preferences based on their booking behavior:

**Tracked Preferences:**
- **Preferred Time of Day**: Morning (6-12), Afternoon (12-17), Evening (17+)
- **Preferred Days**: Last 3 days user has booked appointments
- **Last Appointment**: Most recent booking details

**Where Preferences are Captured:**
- When booking an appointment
- When modifying an appointment

**Where Preferences are Stored:**
- In-memory during call: `SharedState.user_preferences`
- Database on call end: `conversation_logs.user_preferences` (JSONB)
- Frontend summary event: Included in call summary

**Example Preferences:**
```json
{
  "preferred_time": "afternoon",
  "preferred_days": ["Monday", "Friday"],
  "last_appointment_date": "2026-01-27",
  "last_appointment_time": "14:00"
}
```

**Future Use Cases:**
- Pre-filter slots by preferred time
- Suggest similar times: "You usually prefer morning appointments..."
- Analytics: Understand user booking patterns

## Cost Tracking

The agent uses **LiveKit's metrics system** for accurate cost tracking (not estimates):

**Pricing (as of 2026):**
- **Deepgram STT**: $0.0043/minute
- **Azure OpenAI**: $0.0015/1K input tokens, $0.002/1K output tokens
- **Cartesia TTS**: $0.00001/character
- **Avatar**: $0.006/minute (if enabled)

**How It Works:**
1. LiveKit collects usage metrics via `@session.on("metrics_collected")`
2. `CostService` applies pricing to actual usage
3. Cost breakdown is included in call summaries
4. Stored in `conversation_logs.cost_breakdown` (JSONB)

**Metrics Tracked:**
- STT audio duration (seconds)
- LLM prompt tokens (with cache detection)
- LLM completion tokens
- TTS character count
- Session duration (for avatar cost)

## Deployment

### Deploy to LiveKit Cloud

```bash
lk app deploy
```

### Docker Deployment

The included Dockerfile is production-ready:

```bash
docker build -t voice-agent-backend .
docker push your-registry/voice-agent-backend
```

Set environment variables in your deployment platform.

## Known Limitations

1. **Hard-coded Appointment Slots**
   - Fixed times: 9 AM, 10 AM, 11 AM, 2 PM, 3 PM, 4 PM
   - Monday-Friday only
   - No external calendar integration

2. **Basic Phone Number Validation**
   - Simple cleaning of phone numbers
   - No international format validation

3. **Simplified User Model**
   - Only contact_number required
   - Optional name field not actively collected

4. **Avatar Sync Delay**
   - May have 100-500ms lip-sync delay
   - Avatar is optional and can be disabled

5. **Cost Estimates**
   - Based on approximate pricing
   - Actual costs may vary

6. **Transcript Storage**
   - Currently stores basic metadata
   - Full transcript recording to be implemented

## Troubleshooting

### Agent won't start

- Check all API keys are set in `.env.local`
- Verify Supabase tables are created
- Run `uv run python src/agent.py download-files`

### Database connection errors

- Verify Supabase URL and key
- Check network connectivity
- Ensure tables exist with correct schema

### Tools not working

- Check Supabase credentials
- Verify user is identified first (contact_number in context)
- Check logs for specific error messages

### No audio/voice issues

- Verify Deepgram, Azure OpenAI, and Cartesia API keys
- Check API quotas and billing
- Test with console mode first

## Development

### Code Formatting

```bash
uv run ruff format
```

### Linting

```bash
uv run ruff check
```

### Adding New Tools

1. Create tool file in `src/tools/`
2. Use `@function_tool` decorator
3. Import in `src/tools/__init__.py`
4. Import in `src/agent.py`
5. Tool will be automatically registered

## Frontend Repository

The React frontend for this agent is in a separate repository.

## License

MIT License - see LICENSE file for details

## Support

For issues or questions:
- Check the [LiveKit Agents Documentation](https://docs.livekit.io/agents/)
- Review the conversation flow in `src/prompts/system_prompt.py`
- Check logs for detailed error messages

## Acknowledgments

Built with:
- [LiveKit Agents](https://github.com/livekit/agents)
- [Deepgram](https://deepgram.com/)
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
- [Cartesia](https://cartesia.ai/)
- [Supabase](https://supabase.com/)
