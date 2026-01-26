# API Reference - Voice Agent Tools

This document provides detailed documentation for all 7 function tools available to the voice agent.

## Table of Contents

1. [Tool Overview](#tool-overview)
2. [identify_user](#identify_user)
3. [fetch_slots](#fetch_slots)
4. [book_appointment](#book_appointment)
5. [retrieve_appointments](#retrieve_appointments)
6. [cancel_appointment](#cancel_appointment)
7. [modify_appointment](#modify_appointment)
8. [end_conversation](#end_conversation)
9. [Error Handling](#error-handling)
10. [Frontend Event Protocol](#frontend-event-protocol)

---

## Tool Overview

All tools are implemented as LiveKit function tools using the `@function_tool` decorator. The LLM decides when to call each tool based on the conversation context and system instructions.

### Common Patterns

**All tools:**
- Return natural language strings for the LLM to read to the user
- Emit events to the frontend via `EventService`
- Log operations for debugging
- Handle errors gracefully without crashing
- Update `SharedState` for session tracking

**Tool Execution Flow:**
1. LLM decides to call tool
2. Tool emits "started" event to frontend
3. Tool executes business logic
4. Tool updates shared state
5. Tool emits "success" or "error" event
6. Tool returns natural language response to LLM
7. LLM reads response to user

---

## identify_user

**Purpose**: Identify or create a user by phone number. This must be called before any other tools.

**File**: `src/tools/identify_user.py`

### Function Signature

```python
@function_tool
async def identify_user(
    context: RunContext,
    contact_number: str
) -> str
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `contact_number` | str | Yes | User's phone number (10 digits, no special characters) |

### Returns

Natural language string indicating success or error:
- Success: `"User found with contact number {number}"`
- New user: `"New user created with contact number {number}"`
- Error: `"I'm sorry, I encountered an error..."`

### Behavior

1. **Input Cleaning**: Removes spaces, hyphens, and `+91` prefix
2. **Database Lookup**: Queries `users` table by `contact_number`
3. **User Creation**: If not found, creates new user record
4. **State Update**: Stores `contact_number` in `SharedState`
5. **Event Emission**: Sends tool_call event with status

### Database Operations

**Query**:
```sql
SELECT * FROM users WHERE contact_number = ?
```

**Insert** (if not found):
```sql
INSERT INTO users (contact_number, created_at, updated_at) 
VALUES (?, NOW(), NOW())
```

### Example Conversation

```
User: "My phone number is 886-014-1821"
Agent: (calls identify_user with "8860141821")
Tool: Returns "User found with contact number 8860141821"
Agent: "Great! I found your account."
```

### Frontend Event

```json
{
  "type": "tool_call",
  "tool": "identify_user",
  "status": "success",
  "data": {
    "user": {
      "contact_number": "8860141821",
      "name": null,
      "created_at": "2026-01-26T10:00:00Z"
    }
  },
  "timestamp": "2026-01-26T10:30:15.123Z"
}
```

### Error Cases

| Error | Cause | Agent Response |
|-------|-------|----------------|
| Database connection failure | Supabase unreachable | "I'm having trouble connecting. Please try again." |
| Invalid phone format | After cleaning, not 10 digits | "Please provide a 10-digit phone number." |

---

## fetch_slots

**Purpose**: Retrieve all available appointment slots, sorted by date and time.

**File**: `src/tools/fetch_slots.py`

### Function Signature

```python
@function_tool
async def fetch_slots(
    context: RunContext
) -> str
```

### Parameters

None. Fetches all available future slots.

### Returns

Natural language string with available slots:
- Success: `"I have the nearest slots available at: today at 2 PM, tomorrow at 10 AM, tomorrow at 4 PM"`
- No slots: `"I'm sorry, I don't have any available slots at the moment."`
- Error: `"I'm sorry, I'm having trouble checking available slots..."`

### Behavior

1. **Get Current Date/Time**: Uses IST timezone
2. **Database Query**: Fetches ALL available slots where `is_available = true` and slot is in the future
3. **Time Filtering**: For today's date, filters out past time slots
4. **Sorting**: Orders by date, then by time (morning → afternoon → evening)
5. **LLM Strategy**: Returns all slots to LLM, but system prompt instructs LLM to only present 3 nearest slots initially
6. **Event Emission**: Sends all slots to frontend for display

### Database Operations

**Query**:
```sql
SELECT * FROM slots 
WHERE is_available = true 
AND slot_date >= CURRENT_DATE
ORDER BY slot_date ASC, slot_time ASC
```

**Additional Filtering** (in Python):
- If `slot_date == today`: Filter out `slot_time < current_time`

### Example Conversation

```
User: "What times are available?"
Agent: (calls fetch_slots)
Tool: Returns all 20 future slots
Agent: (following system prompt) "I have the nearest slots available at: today at 2 PM, tomorrow at 10 AM, and tomorrow at 4 PM. Would any of these work for you?"
User: "Do you have anything on Monday morning?"
Agent: (already has all slots) "Yes! I have Monday at 9 AM and Monday at 11 AM available."
```

### Frontend Event

```json
{
  "type": "tool_call",
  "tool": "fetch_slots",
  "status": "success",
  "data": {
    "available_slots": [
      {
        "id": "uuid-1",
        "slot_date": "2026-01-27",
        "slot_time": "14:00",
        "formatted": "today at 2 PM"
      },
      {
        "id": "uuid-2",
        "slot_date": "2026-01-28",
        "slot_time": "10:00",
        "formatted": "tomorrow at 10 AM"
      }
      // ... all available slots
    ]
  },
  "timestamp": "2026-01-26T10:31:00.123Z"
}
```

### LLM Presentation Strategy

The system prompt instructs the LLM to:
1. **Initial Presentation**: Show only 3 nearest slots
2. **User Mentions Specific Day/Time**: Narrow down to relevant slots
3. **User Wants More Options**: Show next 3 slots
4. **User Satisfied**: Proceed to booking

---

## book_appointment

**Purpose**: Book an appointment for the identified user.

**File**: `src/tools/book_appointment.py`

### Function Signature

```python
@function_tool
async def book_appointment(
    context: RunContext,
    appointment_date: str,
    appointment_time: str,
    notes: str = ""
) -> str
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `appointment_date` | str | Yes | Date in YYYY-MM-DD format (e.g., "2026-01-27") |
| `appointment_time` | str | Yes | Time in HH:MM format (e.g., "14:00") |
| `notes` | str | No | Optional notes about the appointment |

### Returns

Natural language confirmation or error:
- Success: `"Great! I've booked your appointment for {formatted_date} at {formatted_time}. You'll receive a confirmation shortly."`
- Slot already booked: `"I'm sorry, that slot at {time} on {date} was just booked by someone else. Let me check other available times for you."`
- User not identified: `"I need to verify your phone number first..."`

### Behavior

1. **Prerequisites Check**: Verifies user is identified
2. **Slot Lookup**: Finds slot by date and time
3. **Availability Check**: Verifies slot is still available
4. **Double-Booking Prevention**: Uses database UNIQUE constraint on `slot_id`
5. **Appointment Creation**: Inserts appointment record
6. **Slot Marking**: Marks slot as unavailable
7. **Preference Tracking**: Updates user preferences (time of day, day of week)
8. **Event Emission**: Sends appointment details to frontend

### Database Operations

**Find Slot**:
```sql
SELECT * FROM slots 
WHERE slot_date = ? AND slot_time = ?
```

**Check Existing**:
```sql
SELECT * FROM appointments 
WHERE slot_id = ? AND status != 'cancelled'
```

**Insert Appointment**:
```sql
INSERT INTO appointments (
  contact_number, slot_id, appointment_date, 
  appointment_time, duration_minutes, status, notes
) VALUES (?, ?, ?, ?, 30, 'scheduled', ?)
```

**Mark Slot Unavailable**:
```sql
UPDATE slots SET is_available = false WHERE id = ?
```

### Race Condition Prevention

The `UNIQUE(slot_id)` constraint in the `appointments` table prevents double-booking at the database level. If two users try to book the same slot simultaneously:

1. First request succeeds
2. Second request fails with unique violation
3. Tool catches error and returns "slot already booked" message
4. LLM offers alternative slots

### User Preferences Tracking

After successful booking, the tool automatically tracks:

```python
{
  "preferred_time": "afternoon",  # Extracted from time
  "preferred_days": ["Monday"],    # Extracted from date
  "last_appointment_date": "2026-01-27",
  "last_appointment_time": "14:00"
}
```

### Example Conversation

```
User: "Book me for Monday at 2 PM"
Agent: (calls book_appointment with date="2026-01-27", time="14:00")
Tool: Returns success message
Agent: "Perfect! I've booked your appointment for Monday, January 27th at 2:00 PM. You'll receive a confirmation shortly."
```

### Frontend Event

```json
{
  "type": "tool_call",
  "tool": "book_appointment",
  "status": "success",
  "data": {
    "appointment": {
      "id": "uuid",
      "contact_number": "8860141821",
      "appointment_date": "2026-01-27",
      "appointment_time": "14:00",
      "duration_minutes": 30,
      "status": "scheduled",
      "notes": ""
    }
  },
  "timestamp": "2026-01-26T10:32:00.123Z"
}
```

---

## retrieve_appointments

**Purpose**: Retrieve all scheduled (not cancelled) appointments for the identified user.

**File**: `src/tools/retrieve_appointments.py`

### Function Signature

```python
@function_tool
async def retrieve_appointments(
    context: RunContext
) -> str
```

### Parameters

None. Retrieves appointments for the identified user.

### Returns

Natural language string with appointment details:
- Success with appointments: `"You have 2 appointments: [Appointment 1 with ID abc123] ..."`
- No appointments: `"You don't have any upcoming appointments."`
- User not identified: `"I need to verify your phone number first..."`

**Important**: Each appointment includes its UUID in the response for use with cancel/modify tools.

### Behavior

1. **Prerequisites Check**: Verifies user is identified
2. **Database Query**: Fetches all scheduled appointments (not cancelled)
3. **Format Response**: Includes appointment ID (UUID) in each entry
4. **Event Emission**: Sends appointment list to frontend

### Database Operations

**Query**:
```sql
SELECT * FROM appointments 
WHERE contact_number = ? 
AND status != 'cancelled'
ORDER BY appointment_date ASC, appointment_time ASC
```

### Response Format

The tool returns a formatted string with **IDs included**:

```
"You have 2 appointments:
- [Appointment 1 with ID 550e8400-e29b-41d4-a716-446655440000] Monday, January 27, 2026 at 2:00 PM
- [Appointment 2 with ID 6ba7b810-9dad-11d1-80b4-00c04fd430c8] Wednesday, January 29, 2026 at 10:00 AM"
```

**Why IDs are Included**: 
The LLM needs the UUID to call `cancel_appointment` or `modify_appointment`. The system prompt instructs the LLM to:
1. Call `retrieve_appointments` first
2. Extract the ID from the response
3. Pass the ID to cancel/modify tools

### Example Conversation

```
User: "What appointments do I have?"
Agent: (calls retrieve_appointments)
Tool: Returns formatted list with IDs
Agent: "You have 2 appointments: Monday, January 27th at 2 PM, and Wednesday, January 29th at 10 AM."

User: "Cancel the Monday one"
Agent: (extracts ID from previous response, calls cancel_appointment with that ID)
```

### Frontend Event

```json
{
  "type": "tool_call",
  "tool": "retrieve_appointments",
  "status": "success",
  "data": {
    "appointments": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "appointment_date": "2026-01-27",
        "appointment_time": "14:00",
        "status": "scheduled",
        "notes": ""
      }
    ],
    "count": 1
  },
  "timestamp": "2026-01-26T10:33:00.123Z"
}
```

---

## cancel_appointment

**Purpose**: Cancel an existing appointment.

**File**: `src/tools/cancel_appointment.py`

### Function Signature

```python
@function_tool
async def cancel_appointment(
    context: RunContext,
    appointment_id: str
) -> str
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `appointment_id` | str | Yes | UUID of the appointment to cancel (from `retrieve_appointments`) |

### Returns

Natural language confirmation or error:
- Success: `"I've successfully cancelled your appointment on {formatted_date} at {formatted_time}."`
- Not found: `"I couldn't find that appointment..."`
- User not identified: `"I need to verify your phone number first..."`

### Behavior

1. **Prerequisites Check**: Verifies user is identified
2. **UUID Validation**: Ensures appointment_id is a valid UUID format
3. **Appointment Lookup**: Fetches appointment by ID
4. **Ownership Verification**: Ensures appointment belongs to current user
5. **Status Update**: Marks appointment as 'cancelled' (soft delete)
6. **Slot Release**: Marks slot as available again
7. **Event Emission**: Sends cancellation confirmation to frontend

### Database Operations

**Find Appointment**:
```sql
SELECT * FROM appointments WHERE id = ?
```

**Update Status**:
```sql
UPDATE appointments 
SET status = 'cancelled' 
WHERE id = ?
```

**Mark Slot Available**:
```sql
UPDATE slots 
SET is_available = true 
WHERE id = ?
```

### Why Soft Delete?

Appointments are marked as 'cancelled' rather than deleted to:
- Maintain audit trail
- Allow analytics on cancellation rates
- Enable potential "undo" functionality
- Preserve conversation logs integrity

### Critical Workflow

The LLM **must** follow this workflow:

1. User: "Cancel my Monday appointment"
2. LLM calls `retrieve_appointments` → gets list with IDs
3. LLM identifies the Monday appointment and extracts its UUID
4. LLM calls `cancel_appointment(appointment_id="uuid-here")`

**Common Error**: If LLM passes a date/time instead of UUID:
```
Error: "invalid input syntax for type uuid: '2026-01-27 at 2 PM'"
```

The system prompt explicitly instructs the LLM to always call `retrieve_appointments` first.

### Example Conversation

```
User: "Cancel my appointment"
Agent: (calls retrieve_appointments to get ID)
Agent: "Which appointment would you like to cancel? You have Monday at 2 PM and Wednesday at 10 AM."
User: "The Monday one"
Agent: (extracts UUID for Monday appointment, calls cancel_appointment)
Tool: Returns success message
Agent: "I've successfully cancelled your appointment on Monday, January 27th at 2:00 PM."
```

### Frontend Event

```json
{
  "type": "tool_call",
  "tool": "cancel_appointment",
  "status": "success",
  "data": {
    "cancelled_appointment": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "appointment_date": "2026-01-27",
      "appointment_time": "14:00",
      "status": "cancelled"
    }
  },
  "timestamp": "2026-01-26T10:34:00.123Z"
}
```

---

## modify_appointment

**Purpose**: Change an existing appointment to a new date/time.

**File**: `src/tools/modify_appointment.py`

### Function Signature

```python
@function_tool
async def modify_appointment(
    context: RunContext,
    appointment_id: str,
    new_date: str,
    new_time: str
) -> str
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `appointment_id` | str | Yes | UUID of the appointment to modify (from `retrieve_appointments`) |
| `new_date` | str | Yes | New date in YYYY-MM-DD format |
| `new_time` | str | Yes | New time in HH:MM format |

### Returns

Natural language confirmation or error:
- Success: `"Perfect! I've rescheduled your appointment from {old_date} at {old_time} to {new_date} at {new_time}."`
- New slot unavailable: `"I'm sorry, the slot at {new_time} on {new_date} is already booked..."`
- Not found: `"I couldn't find that appointment..."`

### Behavior

1. **Prerequisites Check**: Verifies user is identified
2. **UUID Validation**: Ensures appointment_id is valid
3. **Appointment Lookup**: Fetches current appointment
4. **Ownership Verification**: Ensures appointment belongs to current user
5. **New Slot Lookup**: Finds the requested new slot
6. **Availability Check**: Verifies new slot is available
7. **Atomic Update**:
   - Update appointment with new slot_id, date, time
   - Mark old slot as available
   - Mark new slot as unavailable
8. **Preference Update**: Updates user preferences with new time/day
9. **Event Emission**: Sends modification details to frontend

### Database Operations

**Find Appointment**:
```sql
SELECT * FROM appointments WHERE id = ?
```

**Find New Slot**:
```sql
SELECT * FROM slots 
WHERE slot_date = ? AND slot_time = ?
```

**Check New Slot Availability**:
```sql
SELECT * FROM appointments 
WHERE slot_id = ? 
AND id != ? 
AND status != 'cancelled'
```

**Update Appointment**:
```sql
UPDATE appointments 
SET slot_id = ?, appointment_date = ?, appointment_time = ? 
WHERE id = ?
```

**Free Old Slot**:
```sql
UPDATE slots SET is_available = true WHERE id = ?
```

**Reserve New Slot**:
```sql
UPDATE slots SET is_available = false WHERE id = ?
```

### Critical Workflow

Same as cancel_appointment - LLM must:
1. Call `retrieve_appointments` first to get UUID
2. Call `fetch_slots` to show available times
3. User selects new time
4. Call `modify_appointment` with UUID and new date/time

### Example Conversation

```
User: "Move my Monday appointment to Wednesday"
Agent: (calls retrieve_appointments to get Monday appointment UUID)
Agent: (calls fetch_slots to check Wednesday availability)
Agent: "I have Wednesday at 10 AM and 2 PM available. Which would you prefer?"
User: "2 PM works"
Agent: (calls modify_appointment with UUID, new_date="2026-01-29", new_time="14:00")
Tool: Returns success message
Agent: "Perfect! I've rescheduled your appointment from Monday, January 27th at 2 PM to Wednesday, January 29th at 2 PM."
```

### Frontend Event

```json
{
  "type": "tool_call",
  "tool": "modify_appointment",
  "status": "success",
  "data": {
    "old_appointment": {
      "date": "2026-01-27",
      "time": "14:00"
    },
    "new_appointment": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "appointment_date": "2026-01-29",
      "appointment_time": "14:00",
      "status": "scheduled"
    }
  },
  "timestamp": "2026-01-26T10:35:00.123Z"
}
```

---

## end_conversation

**Purpose**: End the conversation gracefully, generate summary, calculate costs, and disconnect.

**File**: `src/tools/end_conversation.py`

### Function Signature

```python
@function_tool
async def end_conversation(
    context: RunContext
) -> str
```

### Parameters

None. Uses data from `SharedState` collected during the conversation.

### Returns

Natural language goodbye message:
- Success: `"Thank you for using our appointment booking service! Have a great day!"`

### Behavior

This is the most complex tool as it orchestrates the conversation end:

1. **Extract Transcript**: Uses `TranscriptService` to parse chat context
2. **Calculate Session Duration**: From `session_start_time` to now
3. **Calculate Costs**: Uses `CostService` with LiveKit metrics
4. **Retrieve Appointments**: Fetches scheduled appointments for summary
5. **Generate Summary**: Uses `SummaryService` to create professional summary
6. **Emit Summary Event**: Sends comprehensive summary to frontend
7. **Save to Database**: Stores transcript, summary, costs in `conversation_logs`
8. **Schedule Disconnect**: Waits 8 seconds, then disconnects WebRTC call

### Services Used

- `TranscriptService.extract_from_chat_context()`: Extract conversation
- `CostService.calculate_from_usage_summary()`: Calculate costs
- `SummaryService.generate_from_transcript()`: Generate summary
- `EventService.emit_summary()`: Send to frontend
- `CallService.schedule_disconnect()`: Graceful disconnect

### Database Operations

**Fetch User Appointments**:
```sql
SELECT * FROM appointments 
WHERE contact_number = ? 
AND status = 'scheduled'
ORDER BY appointment_date ASC, appointment_time ASC
```

**Save Conversation Log**:
```sql
INSERT INTO conversation_logs (
  session_id, contact_number, transcript, 
  summary, tool_calls, duration_seconds, 
  cost_breakdown, user_preferences
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
```

### Cost Calculation

Uses LiveKit's `UsageCollector` to get actual metrics:

```python
usage_summary = shared_state.usage_collector.get_summary()
# Contains:
# - stt_audio_duration: Seconds of audio transcribed
# - llm_prompt_tokens: Input tokens to LLM
# - llm_completion_tokens: Output tokens from LLM
# - tts_characters_count: Characters synthesized

costs = CostService.calculate_from_usage_summary(
    usage_summary, 
    session_duration
)
# Returns: {"total": 0.15, "speech_recognition": 0.01, ...}
```

### Summary Format

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

### Disconnect Timing

**Why 8 seconds?**
- ~3s for final TTS to complete
- ~2s for event delivery to frontend
- ~3s buffer for network latency

This ensures the user hears the goodbye and the frontend displays the summary before disconnect.

### Example Conversation

```
User: "That's all, thanks!"
Agent: (calls end_conversation)
Tool: 
  1. Extracts transcript
  2. Calculates costs
  3. Generates summary
  4. Emits summary event to frontend
  5. Saves to database
  6. Schedules disconnect in 8s
  7. Returns goodbye message
Agent: "Thank you for using our appointment booking service! Have a great day!"
[8 seconds later]
[Call disconnects]
```

### Frontend Event

```json
{
  "type": "call_summary",
  "summary": "User (phone: +918860141821) contacted the appointment booking service...",
  "appointments": [
    {
      "id": "uuid",
      "appointment_date": "2026-01-27",
      "appointment_time": "14:00",
      "status": "scheduled"
    }
  ],
  "user_preferences": {
    "preferred_time": "afternoon",
    "preferred_days": ["Monday"],
    "last_appointment_date": "2026-01-27",
    "last_appointment_time": "14:00"
  },
  "cost_breakdown": {
    "total": 0.1234,
    "speech_recognition": 0.0129,
    "ai_processing_input": 0.0421,
    "ai_processing_output": 0.0049,
    "voice_synthesis": 0.0058,
    "avatar": 0.0577
  },
  "duration_seconds": 120,
  "timestamp": "2026-01-26T10:36:00.123Z"
}
```

---

## Error Handling

All tools follow consistent error handling patterns:

### Error Hierarchy

```
try:
    # Business logic
except SpecificError as e:
    # Handle known errors
    logger.error(f"Specific error: {e}", exc_info=True)
    return "User-friendly message"
except Exception as e:
    # Handle unexpected errors
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return "Generic error message"
```

### Common Error Responses

| Scenario | LLM Response |
|----------|--------------|
| User not identified | "I need to verify your phone number first before I can help with that." |
| Database connection failure | "I'm having trouble connecting to our system. Could you please try again in a moment?" |
| Slot already booked | "I'm sorry, that time slot was just booked by someone else. Let me show you other available times." |
| Invalid input | "I didn't quite understand that. Could you please [specific request]?" |
| Appointment not found | "I couldn't find that appointment. Let me check your appointments again." |

### Logging

All errors are logged with full stack traces:

```python
logger.error(f"Error in tool_name: {e}", exc_info=True)
```

This provides debugging information without exposing technical details to users.

---

## Frontend Event Protocol

### Event Structure

All events follow this JSON structure:

```json
{
  "type": "tool_call" | "call_summary",
  "tool": "tool_name",           // Only for tool_call type
  "status": "started" | "success" | "error",  // Only for tool_call type
  "data": {...},                 // Event-specific payload
  "timestamp": "ISO 8601 timestamp"
}
```

### Event Types Summary

| Event Type | Sent By | Purpose |
|------------|---------|---------|
| tool_call (started) | All tools | Notify frontend tool execution began |
| tool_call (success) | All tools | Notify frontend tool completed successfully |
| tool_call (error) | All tools | Notify frontend tool failed |
| call_summary | end_conversation | Send final summary before disconnect |

### Frontend Implementation Example

```typescript
import { Room, RoomEvent, DataPacket } from 'livekit-client';

room.on(RoomEvent.DataReceived, (
  payload: Uint8Array,
  participant: RemoteParticipant | undefined,
  kind: DataPacket_Kind
) => {
  const decoder = new TextDecoder();
  const event = JSON.parse(decoder.decode(payload));
  
  switch (event.type) {
    case 'tool_call':
      handleToolCall(event.tool, event.status, event.data);
      break;
    case 'call_summary':
      displaySummary(event.summary, event.appointments, event.cost_breakdown);
      break;
  }
});

function handleToolCall(tool: string, status: string, data: any) {
  if (status === 'started') {
    showLoader(`${tool} in progress...`);
  } else if (status === 'success') {
    hideLoader();
    updateUI(tool, data);
  } else if (status === 'error') {
    hideLoader();
    showError(data.error);
  }
}

function displaySummary(summary: string, appointments: any[], costs: any) {
  // Show summary page
  // Display appointments list
  // Show cost breakdown
  // Allow user to download/print
}
```

---

## Best Practices

### For Tool Development

1. **Always emit events**: Start, success, and error
2. **Return natural language**: LLM reads response to user
3. **Update shared state**: Track important data
4. **Log extensively**: Debug info without user exposure
5. **Handle errors gracefully**: Never crash the agent
6. **Validate prerequisites**: Check user identification, etc.

### For LLM Integration

1. **Clear docstrings**: LLM reads function docstrings
2. **Type hints**: Help LLM understand parameter types
3. **Examples in prompts**: Show LLM how to use tools
4. **Error feedback**: Return actionable error messages

### For Frontend Integration

1. **Subscribe to all events**: Don't miss tool execution updates
2. **Handle missing data**: Events may arrive out of order
3. **Show loading states**: Improve perceived performance
4. **Display errors gracefully**: Don't break UI on errors

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-26  
**Maintainer**: Voice Agent Team
