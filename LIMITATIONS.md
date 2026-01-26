# Limitations

This document outlines known limitations and constraints of the voice agent system.

## Avatar Initialization

### Overview

The voice agent uses Beyond Presence (bey) for virtual avatar functionality. The avatar provides lifelike video output synchronized with the agent's audio.

### Why Avatar Takes Time to Load

1. **External API Dependency**
   - The avatar is powered by Beyond Presence's cloud service
   - Initial connection to their API requires network round-trips
   - API authentication and session establishment takes time

2. **Avatar Worker Initialization**
   - The avatar joins the LiveKit room as a separate participant (avatar worker)
   - The worker must establish WebRTC connections for audio/video streaming
   - Video encoding and streaming setup adds latency

3. **Resource Allocation**
   - Beyond Presence allocates compute resources for the avatar session
   - This allocation happens on-demand and can take several seconds
   - Network conditions affect initialization time

4. **Typical Load Times**
   - **Best case**: 2-5 seconds
   - **Average case**: 5-10 seconds
   - **Worst case**: 10-15+ seconds (network issues, API delays)

### Problems with Blocking Avatar Initialization

When avatar initialization is made **blocking** (waiting for avatar to be ready before starting the agent session), several issues occur:

#### 1. **Delayed User Experience**
- **Problem**: User must wait for avatar to fully initialize before hearing the greeting
- **Impact**: 
  - User sees "Initializing..." or blank screen for 5-15 seconds
  - No audio feedback during this time
  - Poor first impression and perceived system lag

#### 2. **Frontend Lag**
- **Problem**: Frontend waits for avatar participant to join before showing "ready" state
- **Impact**:
  - UI appears frozen or unresponsive
  - User may think the system is broken
  - Increased bounce rate

#### 3. **Premature Responses**
- **Problem**: If avatar takes too long, agent might start speaking before avatar is ready
- **Impact**:
  - Audio plays but no video/avatar visible
  - Desynchronized experience
  - User confusion

#### 4. **API Concurrency Limits**
- **Problem**: Beyond Presence API has concurrency limits (429 errors)
- **Impact**:
  - If limit is reached, avatar fails to start
  - Blocking approach means entire agent session fails
  - No graceful degradation

#### 5. **Resource Waste**
- **Problem**: If user disconnects during avatar initialization, resources are wasted
- **Impact**:
  - Unnecessary API calls
  - Wasted compute resources
  - Potential billing for unused sessions

### Current Solution

The system uses a **non-blocking approach**:

1. **Agent session starts immediately** - Voice begins right away
2. **Avatar starts in background** - Initializes asynchronously
3. **Avatar joins when ready** - Automatically takes over audio/video when it joins
4. **Graceful degradation** - System continues without avatar if initialization fails

**Benefits:**
- ✅ User hears greeting immediately (no delay)
- ✅ No frontend lag
- ✅ Avatar appears when ready (seamless transition)
- ✅ System works even if avatar fails

**Trade-offs:**
- ⚠️ Avatar may appear a few seconds after greeting starts
- ⚠️ Brief period where audio plays without avatar (acceptable UX)

### Best Practices

1. **Don't block on avatar initialization** - Always start agent session first
2. **Handle failures gracefully** - Continue without avatar if initialization fails
3. **Monitor API limits** - Track Beyond Presence concurrency usage
4. **Set timeouts** - Don't wait indefinitely for avatar to join
5. **User communication** - Consider informing users that avatar is loading (optional)

### References

- [LiveKit Avatar Documentation](https://docs.livekit.io/agents/models/avatar/)
- [Beyond Presence Plugin](https://docs.livekit.io/agents/models/avatar/plugins/bey/)

---

## Other Limitations

### Database Constraints

- **Unique Constraints**: The `appointments` table has `UNIQUE(slot_id)` and `UNIQUE(appointment_date, appointment_time)` constraints
- **Cancelled Appointments**: Cancelled appointments are deleted (not marked as cancelled) to allow rebooking the same slot

### API Rate Limits

- **Beyond Presence**: Concurrency limits based on subscription plan
- **Supabase**: Rate limits based on project tier
- **Deepgram/OpenAI/Cartesia**: Rate limits based on API tier

### Session Management

- **Single Session**: One agent session per LiveKit room
- **State Management**: Session state is not persisted across disconnects
- **Tool Execution**: Tools cannot be interrupted once started (by design)

---

## Future Improvements

1. **Avatar Pre-warming**: Pre-initialize avatar workers to reduce startup time
2. **Caching**: Cache avatar sessions for faster reconnection
3. **Partial Unique Index**: Use PostgreSQL partial unique indexes to allow cancelled appointments without deletion
4. **Retry Logic**: Implement exponential backoff for avatar initialization failures
5. **Monitoring**: Add metrics for avatar initialization success rates and timing
