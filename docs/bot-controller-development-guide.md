# Bot Controller Development Guide

## Adding a New Meeting Platform

### 1. Create Platform Adapter

Create a new adapter class that inherits from the appropriate base class:

```python
# bots/new_platform_bot_adapter/new_platform_bot_adapter.py
from bots.web_bot_adapter import WebBotAdapter  # for browser-based
# OR from bots.bot_adapter import BotAdapter  # for SDK-based

class NewPlatformBotAdapter(WebBotAdapter):
    def __init__(self, display_name, send_message_callback, 
                 add_audio_chunk_callback, meeting_url, **kwargs):
        # Initialize platform-specific components
        self.meeting_url = meeting_url
        # ... other initialization
    
    def init(self):
        """Join the meeting"""
        # Platform-specific join logic
        pass
    
    def leave(self):
        """Leave the meeting"""
        # Platform-specific leave logic
        pass
    
    def send_chat_message(self, text):
        """Send chat message to meeting"""
        # Platform-specific chat logic
        pass
```

### 2. Add Meeting Type

Update the meeting types enum:

```python
# bots/models.py
class MeetingTypes(models.TextChoices):
    ZOOM = "zoom"
    GOOGLE_MEET = "google_meet"
    TEAMS = "teams"
    NEW_PLATFORM = "new_platform"  # Add your platform
```

### 3. Update URL Detection

Add URL pattern matching:

```python
# bots/utils.py
def meeting_type_from_url(url):
    if "zoom.us" in url:
        return MeetingTypes.ZOOM
    elif "meet.google.com" in url:
        return MeetingTypes.GOOGLE_MEET
    elif "teams.microsoft.com" in url:
        return MeetingTypes.TEAMS
    elif "newplatform.com" in url:  # Add your pattern
        return MeetingTypes.NEW_PLATFORM
    return None
```

### 4. Update Bot Controller

Add adapter creation logic:

```python
# bot_controller/bot_controller.py
def get_new_platform_bot_adapter(self):
    return NewPlatformBotAdapter(
        display_name=self.bot_in_db.name,
        send_message_callback=self.on_message_from_adapter,
        add_audio_chunk_callback=self.per_participant_audio_input_manager().add_chunk,
        meeting_url=self.bot_in_db.meeting_url,
        # ... other required parameters
    )

def get_bot_adapter(self):
    meeting_type = self.get_meeting_type()
    if meeting_type == MeetingTypes.NEW_PLATFORM:
        return self.get_new_platform_bot_adapter()
    # ... existing logic
```

### 5. Configure Audio/Video Settings

Add platform-specific settings:

```python
def get_per_participant_audio_sample_rate(self):
    meeting_type = self.get_meeting_type()
    if meeting_type == MeetingTypes.NEW_PLATFORM:
        return 48000  # or appropriate sample rate
    # ... existing logic

def get_audio_format(self):
    meeting_type = self.get_meeting_type()
    if meeting_type == MeetingTypes.NEW_PLATFORM:
        return GstreamerPipeline.AUDIO_FORMAT_FLOAT
    # ... existing logic
```

## Modifying Pipeline Configurations

### Adding New Configuration

```python
# bot_controller/pipeline_configuration.py
@classmethod
def new_configuration_type(cls) -> "PipelineConfiguration":
    return cls(
        record_video=True,
        record_audio=False,
        transcribe_audio=True,
        rtmp_stream_audio=False,
        rtmp_stream_video=True,  # New combination
        websocket_stream_audio=False,
    )
```

Update valid configurations:

```python
def __post_init__(self):
    valid_configurations: FrozenSet[FrozenSet[str]] = frozenset({
        # ... existing configurations
        frozenset({"record_video", "transcribe_audio", "rtmp_stream_video"}),  # Add new
    })
```

### Configuration Selection

Update the selection logic in `BotController.get_pipeline_configuration()`:

```python
def get_pipeline_configuration(self):
    # Add new condition
    if self.bot_in_db.some_new_setting():
        return PipelineConfiguration.new_configuration_type()
    # ... existing logic
```

## Adding New Transcription Providers

### 1. Define Provider

```python
# bots/models.py
class TranscriptionProviders(models.TextChoices):
    # ... existing providers
    NEW_PROVIDER = "new_provider"
```

### 2. Implement Provider Logic

Create provider-specific handling:

```python
# bots/transcription_providers/new_provider/new_provider.py
class NewProviderTranscription:
    def __init__(self, api_key):
        self.api_key = api_key
    
    def transcribe_audio(self, audio_data, sample_rate):
        # Implement transcription logic
        return {"transcript": "transcribed text"}
```

### 3. Update Audio Managers

For streaming providers, modify `PerParticipantStreamingAudioInputManager`:

```python
def get_transcription_client(self):
    if self.transcription_provider == TranscriptionProviders.NEW_PROVIDER:
        return NewProviderTranscription(api_key=...)
    # ... existing logic
```

For batch providers, modify utterance size limits:

```python
def non_streaming_audio_utterance_size_limit(self):
    if self.get_recording_transcription_provider() == TranscriptionProviders.NEW_PROVIDER:
        return 2400000  # Custom limit for new provider
    # ... existing logic
```

## Error Handling Best Practices

### 1. Define Error Events

Add new error types:

```python
# bots/models.py
class BotEventSubTypes(models.TextChoices):
    # ... existing types
    FATAL_ERROR_NEW_PLATFORM_ERROR = "fatal_error_new_platform_error"
```

### 2. Handle Platform Errors

In your adapter:

```python
def handle_platform_error(self, error):
    if error.type == "authentication_failed":
        self.send_message_callback({
            "message": BotAdapter.Messages.LOGIN_REQUIRED
        })
    elif error.type == "meeting_not_found":
        self.send_message_callback({
            "message": BotAdapter.Messages.MEETING_NOT_FOUND
        })
```

### 3. Add Error Recovery

```python
def take_action_based_on_message_from_adapter(self, message):
    if message.get("message") == "NEW_PLATFORM_SPECIFIC_ERROR":
        BotEventManager.create_event(
            bot=self.bot_in_db,
            event_type=BotEventTypes.FATAL_ERROR,
            event_sub_type=BotEventSubTypes.FATAL_ERROR_NEW_PLATFORM_ERROR,
            event_metadata={"error_details": message.get("details")}
        )
        self.cleanup()
```

## Testing and Debugging

### 1. Enable Debug Features

```python
# For new adapters, implement debug capabilities
def create_debug_recording(self):
    return self.bot_in_db.create_debug_recording()

def take_debug_screenshot(self, step_name):
    if self.create_debug_recording():
        # Save screenshot with context
        self.save_debug_screenshot(step_name)
```

### 2. Add Logging

```python
import logging
logger = logging.getLogger(__name__)

def critical_operation(self):
    logger.info(f"Starting critical operation for bot {self.bot_id}")
    try:
        # Operation logic
        logger.info("Critical operation completed successfully")
    except Exception as e:
        logger.error(f"Critical operation failed: {e}")
        raise
```

### 3. Monitor Performance

```python
def monitor_audio_processing(self):
    """Track audio processing metrics"""
    if hasattr(self, 'audio_stats'):
        chunks_processed = self.audio_stats.get('chunks_processed', 0)
        logger.info(f"Processed {chunks_processed} audio chunks")
```

## Common Pitfalls and Solutions

### 1. Audio Timing Issues

**Problem**: Audio and video out of sync
**Solution**: Ensure consistent timestamp handling

```python
def add_mixed_audio_chunk_callback(self, chunk: bytes):
    # Use consistent timestamp source
    current_time_ns = time.time_ns()
    if self.gstreamer_pipeline:
        self.gstreamer_pipeline.on_mixed_audio_raw_data_received_callback(
            chunk, timestamp=current_time_ns
        )
```

### 2. Memory Leaks

**Problem**: Bot processes consuming excessive memory
**Solution**: Proper cleanup and resource management

```python
def cleanup(self):
    # Clean up all resources in proper order
    if self.audio_processor:
        self.audio_processor.stop()
        self.audio_processor = None
    
    if self.video_processor:
        self.video_processor.cleanup()
        self.video_processor = None
```

### 3. Race Conditions

**Problem**: Components accessing shared state concurrently
**Solution**: Use GLib.idle_add for thread-safe operations

```python
def on_new_chat_message(self, chat_message):
    # Schedule in main thread
    GLib.idle_add(lambda: self.upsert_chat_message(chat_message))
```

### 4. Platform-Specific Timing

**Problem**: Different platforms have different timing requirements
**Solution**: Platform-specific delays and timeouts

```python
def get_platform_specific_delay(self):
    meeting_type = self.get_meeting_type()
    if meeting_type == MeetingTypes.TEAMS:
        return 2000  # Teams needs 2s delay
    elif meeting_type == MeetingTypes.NEW_PLATFORM:
        return 1500  # Custom delay for new platform
    return 0
```

## Performance Optimization

### 1. Audio Processing

- Use appropriate buffer sizes for platform
- Implement backpressure handling
- Monitor queue depths

### 2. Video Processing

- Optimize encoding settings for use case
- Monitor frame drops
- Handle resolution changes

### 3. Network Operations

- Implement retry logic with exponential backoff
- Use connection pooling where applicable
- Monitor bandwidth usage

## Security Considerations

### 1. Credential Management

```python
def get_platform_credentials(self):
    credentials = self.bot_in_db.project.credentials.filter(
        credential_type=Credentials.CredentialTypes.NEW_PLATFORM
    ).first()
    
    if not credentials:
        raise Exception("Platform credentials not found")
    
    return credentials.get_credentials()  # Returns decrypted credentials
```

### 2. Input Validation

```python
def validate_meeting_url(self, url):
    # Validate URL format and domain
    parsed = urlparse(url)
    if parsed.netloc not in ALLOWED_DOMAINS:
        raise ValueError("Invalid meeting domain")
    return url
```

### 3. Resource Limits

```python
def check_resource_limits(self):
    # Implement limits on recording duration, file size, etc.
    if self.recording_duration > MAX_RECORDING_DURATION:
        self.cleanup_with_reason("Recording duration limit exceeded")
```

This development guide provides the foundation for extending the bot controller system while maintaining consistency and reliability.
