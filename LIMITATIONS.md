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

## LiveKit Cloud Worker Cold Starts

### Overview

When deploying the agent to LiveKit Cloud, workers are automatically shut down after periods of inactivity to optimize resource usage and costs. This can cause delays when starting a new conversation if the worker is not already running.

### Why Cold Starts Occur

1. **Automatic Shutdown**
   - LiveKit Cloud shuts down idle workers after a period of inactivity
   - This is a cost-saving and resource optimization feature
   - Workers are started on-demand when a new job request arrives

2. **Worker Initialization Time**
   - When a worker is shut down, it must be restarted before processing requests
   - This includes:
     - Container initialization
     - Dependency loading
     - Agent process startup
     - Plugin initialization (STT, TTS, LLM, Avatar)
   - This process typically takes 2-5 seconds

3. **Network Latency**
   - Additional network round-trips for worker registration
   - Connection establishment to LiveKit Cloud
   - Room creation and participant joining

### Impact on User Experience

#### Initial Load Delay
- **First request after inactivity**: 3-8 seconds delay before agent responds
- **Subsequent requests**: Immediate (worker is already running)
- **User sees**: "Initializing..." or loading state for several seconds

#### Potential Solutions

1. **Page Reload**
   - If the agent doesn't respond after 10-15 seconds, users can reload the page
   - This will trigger a new job request and worker initialization
   - **Note**: This is a workaround, not a permanent solution

2. **Keep-Alive Mechanism** (Future Enhancement)
   - Implement periodic health checks to keep workers warm
   - Use scheduled jobs to ping the agent periodically
   - Trade-off: Increased costs vs. better user experience

3. **User Communication**
   - Show a clear loading message: "Starting agent, please wait..."
   - Set user expectations about potential delays
   - Consider a timeout indicator

### Typical Timing

- **Cold start (worker down)**: 3-8 seconds
- **Warm start (worker running)**: <1 second
- **Timeout threshold**: If no response after 15 seconds, consider reloading

### Best Practices

1. **Set Realistic Expectations**: Inform users that the first request may take a few seconds
2. **Implement Timeouts**: Show a timeout message if initialization takes too long
3. **Provide Reload Option**: Allow users to manually reload if stuck
4. **Monitor Worker Status**: Track cold start frequency and duration
5. **Consider Keep-Alive**: For production systems with high traffic, consider implementing keep-alive mechanisms

### References

- [LiveKit Cloud Documentation](https://docs.livekit.io/cloud/)
- [LiveKit Agents Deployment](https://docs.livekit.io/agents/deploy/)

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
