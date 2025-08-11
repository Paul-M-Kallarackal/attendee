# Bot Controller Architecture Documentation

## Overview

The Bot Controller is the core component that orchestrates meeting bots across different video conferencing platforms (Zoom, Google Meet, Teams). It manages audio/video recording, transcription, real-time streaming, and meeting interaction.

## Core Components

### 1. BotController Class (`bot_controller/bot_controller.py`)

The main orchestrator that coordinates all bot operations.

#### Key Responsibilities:
- **Bot Lifecycle Management**: Initialize, join, leave, and cleanup meeting bots
- **Media Pipeline Orchestration**: Configure and manage audio/video processing pipelines
- **Platform Adaptation**: Route to appropriate platform-specific adapters
- **Real-time Communication**: Handle Redis messages and WebSocket connections
- **Error Handling**: Manage failures and recovery scenarios

#### Important Methods:

```python
def __init__(self, bot_id):
    """Initialize bot controller with database bot instance"""

def run(self):
    """Main entry point - starts the GLib main loop and all components"""

def cleanup(self):
    """Graceful shutdown of all components with timeout protection"""

def get_bot_adapter(self):
    """Factory method to create platform-specific adapters"""
```

#### State Management:
- **READY**: Bot is created but not active
- **STAGED**: Bot is scheduled to join at a future time
- **JOINING**: Bot is attempting to join the meeting
- **IN_MEETING**: Bot has successfully joined and is recording
- **LEAVING**: Bot is leaving the meeting
- **POST_PROCESSING**: Bot has left, finalizing recordings and transcriptions

## 2. Pipeline Configuration System

### PipelineConfiguration (`bot_controller/pipeline_configuration.py`)

Defines how the bot processes media from meetings using a predefined set of valid configurations.

#### Configuration Types:

| Configuration | Record Video | Record Audio | Transcribe | RTMP Stream | WebSocket Stream |
|---------------|--------------|--------------|------------|-------------|------------------|
| **recorder_bot** | ✓ | ✓ | ✓ | ✗ | ✗ |
| **audio_recorder_bot** | ✗ | ✓ | ✓ | ✗ | ✗ |
| **rtmp_streaming_bot** | ✗ | ✗ | ✓ | ✓ (A+V) | ✗ |
| **pure_transcription_bot** | ✗ | ✗ | ✓ | ✗ | ✗ |
| ***_with_websocket_audio** | ± | ± | ✓ | ✗ | ✓ |

#### Configuration Selection Logic:
```python
def get_pipeline_configuration(self):
    if self.bot_in_db.rtmp_destination_url():
        return PipelineConfiguration.rtmp_streaming_bot()
    
    if self.bot_in_db.recording_type() == RecordingTypes.AUDIO_ONLY:
        if self.bot_in_db.websocket_audio_url():
            return PipelineConfiguration.audio_recorder_bot_with_websocket_audio()
        else:
            return PipelineConfiguration.audio_recorder_bot()
    # ... additional logic
```

## 3. Platform Adapters

### Bot Adapter Hierarchy

```
BotAdapter (base class)
├── WebBotAdapter (browser-based platforms)
│   ├── GoogleMeetBotAdapter
│   ├── TeamsBotAdapter
│   └── ZoomWebBotAdapter
└── ZoomBotAdapter (native SDK)
```

#### GoogleMeetBotAdapter
- **Technology**: Browser automation with Chrome DevTools
- **Audio Source**: Web Audio API (48kHz float)
- **Video Source**: MediaRecorder API
- **Transcription**: Platform closed captions or per-participant audio

#### TeamsBot Adapter
- **Technology**: Browser automation
- **Audio Source**: Web Audio API (48kHz float)  
- **Login Support**: Bot login credentials for authenticated access
- **Delay Compensation**: 2-second utterance delay for Teams-specific timing

#### ZoomBotAdapter (Native SDK)
- **Technology**: Zoom Meeting SDK (native)
- **Audio Source**: SDK audio callbacks (32kHz PCM)
- **Video Source**: SDK video frames
- **Authentication**: OAuth 2.0 with JWT tokens

#### ZoomWebBotAdapter
- **Technology**: Browser-based Zoom
- **Audio Source**: Web Audio API (48kHz float)
- **Authentication**: OAuth credentials

### Adapter Selection Logic:
```python
def get_bot_adapter(self):
    meeting_type = self.get_meeting_type()
    if meeting_type == MeetingTypes.ZOOM:
        if self.bot_in_db.use_zoom_web_adapter():
            return self.get_zoom_web_bot_adapter()
        else:
            return self.get_zoom_bot_adapter()
    elif meeting_type == MeetingTypes.GOOGLE_MEET:
        return self.get_google_meet_bot_adapter()
    elif meeting_type == MeetingTypes.TEAMS:
        return self.get_teams_bot_adapter()
```

## 4. Media Processing Pipeline

### Audio Processing

#### Per-Participant Audio Managers:
- **PerParticipantNonStreamingAudioInputManager**: Batch processing for providers like Whisper
- **PerParticipantStreamingAudioInputManager**: Real-time streaming for providers like Deepgram

#### Audio Output Management:
- **AudioOutputManager**: Handles bot speech (TTS and pre-recorded audio)
- **RealtimeAudioOutputManager**: Real-time audio injection from WebSocket

#### Sample Rate Handling:
```python
def get_per_participant_audio_sample_rate(self):
    meeting_type = self.get_meeting_type()
    if meeting_type == MeetingTypes.ZOOM:
        return 32000 if not self.bot_in_db.use_zoom_web_adapter() else 48000
    else:  # Google Meet, Teams
        return 48000
```

### Video Processing

#### GStreamer Pipeline (`bot_controller/gstreamer_pipeline.py`)

**Purpose**: Handle video encoding, muxing, and output for native Zoom SDK.

**Pipeline Structure**:
```
Video: appsrc → videoconvert → videorate → x264enc → muxer
Audio: appsrc → audioconvert → audiorate → voaacenc → muxer
Output: muxer → sink (file or RTMP)
```

**Output Formats**:
- **MP4**: Standard recording format
- **WEBM**: Alternative container format
- **MP3**: Audio-only recordings
- **FLV**: RTMP streaming format

#### Screen Recording (`bot_controller/screen_and_audio_recorder.py`)

**Purpose**: Handle screen capture for browser-based platforms.

**Technology**: FFmpeg-based screen capture
- **Video**: X11 screen grab with crop to meeting dimensions
- **Audio**: ALSA audio capture
- **Pause/Resume**: Overlay black screen and mute audio

## 5. Transcription System

### Closed Caption Management

#### ClosedCaptionManager
- **Purpose**: Process platform-provided closed captions
- **Grouping**: Optional consecutive caption merging

#### Utterance Processing:
```python
def save_closed_caption_utterance(self, message):
    # Create participant record
    participant, _ = Participant.objects.get_or_create(...)
    
    # Create utterance with transcription
    utterance = Utterance.objects.update_or_create(
        source=Utterance.Sources.CLOSED_CAPTION_FROM_PLATFORM,
        transcription={"transcript": message["text"]},
        timestamp_ms=message["timestamp_ms"]
    )
    
    # Trigger webhook
    trigger_webhook(WebhookTriggerTypes.TRANSCRIPT_UPDATE, ...)
```

### Audio-Based Transcription

#### Provider Integration:
- **Deepgram**: Streaming transcription
- **Whisper**: Batch transcription
- **Sarvam**: Batch with 30-second audio limits

#### Utterance Size Limits:
```python
def non_streaming_audio_utterance_size_limit(self):
    if self.get_recording_transcription_provider() == TranscriptionProviders.SARVAM:
        return 1920000  # 30 seconds at 32kHz
    else:
        return 19200000  # 300 seconds (5 minutes)
```

## 6. Real-time Communication

### Redis Integration
- **Purpose**: Command and control communication with bot instances
- **Commands**: sync, sync_media_requests, pause_recording, resume_recording
- **Channel**: `bot_{bot_id}`

### WebSocket Integration
- **Purpose**: Real-time audio streaming and bot control
- **Client**: `BotWebsocketClient` with auto-reconnection
- **Protocol**: JSON messages with base64 audio chunks

## 7. Error Handling and Recovery

### Bot Events System
```python
class BotEventTypes:
    BOT_JOINED_MEETING = "bot_joined_meeting"
    COULD_NOT_JOIN = "could_not_join" 
    FATAL_ERROR = "fatal_error"
    LEAVE_REQUESTED = "leave_requested"
    # ... more event types
```

### Recovery Mechanisms:
- **Automatic Restart**: For certain platform blocks
- **Graceful Degradation**: Continue with available components
- **Timeout Protection**: 10-minute hard shutdown limit

### Debug Capabilities:
- **Debug Screenshots**: Capture UI state on errors
- **Debug Recordings**: Save screen recordings
- **Resource Monitoring**: Track queue drops and performance

## 8. File Management and Upload

### Recording Output:
- **Local Storage**: `/tmp/{bot_id}-{recording_id}.{format}`
- **S3 Upload**: Automatic upload on completion
- **Seekable Optimization**: Move MOOV atom for web playback

### File Cleanup:
- **Debug Files**: Cleaned up after upload
- **Local Recordings**: Deleted after S3 upload
- **Temporary Files**: Cleanup on bot termination

## Configuration Examples

### Full Recording Bot:
```python
pipeline = PipelineConfiguration.recorder_bot()
# Records video + audio, transcribes, saves to S3
```

### RTMP Streaming Bot:
```python
pipeline = PipelineConfiguration.rtmp_streaming_bot() 
# Streams to RTMP endpoint, transcribes, no local recording
```

### Transcription-Only Bot:
```python
pipeline = PipelineConfiguration.pure_transcription_bot()
# Only transcribes, no recording or streaming
```

This architecture provides a flexible, scalable system for meeting bot operations across multiple platforms while maintaining clean separation of concerns and robust error handling.
