# Bot Adapters Guide

## Overview

Bot adapters handle platform-specific integration for different video conferencing platforms. Each adapter implements the required methods for joining meetings, capturing media, and sending messages while handling platform-specific quirks and requirements.

## Adapter Hierarchy

```
BotAdapter (base class)
├── WebBotAdapter (browser-based platforms)
│   ├── GoogleMeetBotAdapter
│   ├── TeamsBotAdapter  
│   └── ZoomWebBotAdapter
└── ZoomBotAdapter (native SDK)
```

## WebBotAdapter Base Class

### Technology Stack
- **Browser**: Selenium WebDriver with Chrome
- **Display**: Virtual X11 display via pyvirtualdisplay
- **Media Capture**: JavaScript WebRTC APIs
- **Communication**: WebSocket for real-time data transfer

### Core Components

#### Virtual Display Management
```python
def setup_virtual_display(self):
    """Create isolated virtual display for browser"""
    self.display = Display(visible=0, size=self.video_frame_size)
    self.display.start()
```

#### WebSocket Server
- **Purpose**: Real-time communication between browser and bot controller
- **Protocol**: JSON messages over WebSocket
- **Data Types**: Audio chunks, video frames, captions, chat messages

#### Media Processing Pipeline
```javascript
// Browser-side media capture
navigator.mediaDevices.getDisplayMedia() // Screen capture
navigator.mediaDevices.getUserMedia()    // Audio capture
```

### Common WebBotAdapter Features

#### Screen Recording Integration
```python
def start_recording_screen(self):
    """Start FFmpeg-based screen recording"""
    if self.start_recording_screen_callback:
        display_var = f":{self.display.display}"
        self.start_recording_screen_callback(display_var)
```

#### Auto-Leave Detection
- **Silence Detection**: Monitor for periods without audio activity
- **Participant Count**: Leave when bot is only participant
- **Maximum Uptime**: Enforce time-based limits

#### Debug Capabilities
- **Screenshot Capture**: Save browser state on errors
- **Debug Recording**: Continuous screen recording for troubleshooting
- **MHTML Export**: Full page state preservation

## Platform-Specific Adapters

### GoogleMeetBotAdapter

#### Unique Features
- **Video Sending Support**: Can display videos to other participants
- **Closed Captions**: Platform-native caption integration
- **UI Automation**: Google Meet-specific element interactions

#### Configuration
```python
GoogleMeetBotAdapter(
    display_name="Bot Name",
    google_meet_closed_captions_language="en",  # Optional
    meeting_url="https://meet.google.com/xxx-xxxx-xxx",
    recording_view=RecordingViews.GALLERY_VIEW,
    # ... other parameters
)
```

#### Specialized Methods
```python
def send_video(self, video_url):
    """Display video in meeting using botOutputManager"""
    self.driver.execute_script(
        f"window.botOutputManager.playVideo({json.dumps(video_url)})"
    )

def is_sent_video_still_playing(self):
    """Check if bot-sent video is currently playing"""
    return self.driver.execute_script(
        "return window.botOutputManager.isVideoPlaying();"
    )
```

#### Audio Processing
- **Sample Rate**: 48kHz float format
- **Source**: Web Audio API via getDisplayMedia
- **Processing**: Real-time chunking with participant detection

#### Join Process
1. Navigate to meeting URL
2. Handle potential waiting room
3. Accept permissions (camera/microphone)
4. Set display name
5. Configure recording view
6. Enable closed captions (if configured)

#### Error Handling
- **Request to Join Denied**: Waiting room rejection
- **Meeting Not Found**: Invalid/expired URL
- **Permission Issues**: Browser permission prompts

### TeamsBotAdapter

#### Unique Features
- **Bot Login Support**: Authentication with dedicated bot credentials
- **Utterance Delay**: 2-second delay compensation for Teams timing
- **Limited Video Support**: No video sending capabilities

#### Configuration
```python
TeamsBotAdapter(
    teams_closed_captions_language="en",
    teams_bot_login_credentials={
        "username": "bot@company.com",
        "password": "bot_password"
    },
    # ... other parameters
)
```

#### Authentication Flow
```python
def handle_bot_login(self):
    """Authenticate using bot credentials if provided"""
    if self.teams_bot_login_credentials:
        # Enter username/password
        # Handle MFA if required
        # Navigate to meeting
```

#### Chat Message Implementation
```python
def send_chat_message(self, text):
    """Send message using Teams-specific chat input"""
    chat_input = self.driver.execute_script(
        'return document.querySelector(\'[aria-label="Type a message"]\')'
    )
    if chat_input:
        chat_input.send_keys(text)
        chat_input.send_keys(Keys.ENTER)
```

#### Teams-Specific Timing
- **Join Delay**: 10 seconds (longer than other platforms)
- **Utterance Delay**: 2000ms compensation for platform lag
- **WebSocket Port**: 8097 (different from other platforms)

#### Limitations
- **No Video Sending**: `send_video()` returns without action
- **No Video Playback Detection**: Always returns `False`

### ZoomWebBotAdapter

#### Unique Features  
- **Meeting SDK Integration**: Uses Zoom Meeting SDK in browser
- **JWT Authentication**: SDK signature generation
- **OAuth Integration**: Client ID/secret authentication

#### SDK Signature Generation
```python
def zoom_meeting_sdk_signature(meeting_number, role):
    """Generate JWT signature for Zoom Meeting SDK"""
    payload = {
        "appKey": sdk_key,
        "sdkKey": sdk_key, 
        "mn": str(meeting_number),
        "role": role,  # 0 = attendee, 1 = host
        "iat": int(datetime.utcnow().timestamp()),
        "exp": iat + expiration_seconds,
    }
    return jwt.encode(payload, sdk_secret, algorithm="HS256")
```

#### URL Parsing
```python
def parse_join_url(join_url):
    """Extract meeting ID and password from Zoom URL"""
    parsed = urlparse(join_url)
    meeting_id_match = re.search(r"(\d+)", parsed.path)
    meeting_id = meeting_id_match.group(1)
    
    query_params = parse_qs(parsed.query)
    password = query_params.get("pwd", [None])[0]
    
    return (meeting_id, password)
```

#### Initialization Data
```javascript
// Browser-side initialization
window.zoomInitialData = {
    signature: "<jwt_signature>",
    sdkKey: "<sdk_key>",
    meetingNumber: "<meeting_id>",
    meetingPassword: "<password>"
}
```

#### Error Handling
- **External Meeting Issues**: Special handling for error code 4011
- **Authorization Failures**: OAuth credential problems
- **Waiting Room Removal**: Distinct from other join failures

#### Limitations
- **No Video Sending**: Browser SDK limitations
- **Audio Only**: No video playback support

## ZoomBotAdapter (Native SDK)

### Technology Stack
- **Zoom Meeting SDK**: Native C++ SDK with Python bindings
- **Direct Media Access**: Raw audio/video data from SDK
- **OAuth 2.0**: Client credentials flow

### Key Differences from Web Adapters
- **No Browser**: Direct SDK integration
- **Raw Media**: Unprocessed audio/video streams
- **Better Performance**: Lower latency and overhead
- **Advanced Features**: Access to SDK-specific capabilities

### Media Processing
```python
# Audio callback from SDK
def on_audio_raw_data_received(self, data):
    """Process raw audio data from Zoom SDK"""
    # Data format: 32kHz, 16-bit PCM
    self.add_audio_chunk_callback(data)

# Video callback from SDK  
def on_video_frame_received(self, frame_data):
    """Process raw video frames from SDK"""
    # Convert to required format and forward
    self.add_video_frame_callback(frame_data)
```

### Authentication
```python
def authenticate_zoom_sdk(self):
    """Authenticate with Zoom using OAuth tokens"""
    auth_service = self.sdk.GetAuthService()
    auth_service.AuthorizeSDK(
        app_key=self.zoom_client_id,
        app_secret=self.zoom_client_secret
    )
```

### Meeting Operations
```python
def join_meeting(self):
    """Join meeting using SDK"""
    meeting_service = self.sdk.GetMeetingService()
    param = meeting_service.CreateJoinMeetingParam()
    param.meetingNumber = self.meeting_id
    param.password = self.meeting_password
    param.userName = self.display_name
    
    result = meeting_service.JoinMeeting(param)
```

## Adapter Selection Logic

The bot controller automatically selects the appropriate adapter based on:

1. **Meeting URL Pattern**: Detected platform type
2. **Configuration Settings**: Platform-specific preferences
3. **Available Credentials**: Required authentication methods

```python
def get_bot_adapter(self):
    """Select appropriate adapter for meeting platform"""
    meeting_type = meeting_type_from_url(self.meeting_url)
    
    if meeting_type == MeetingTypes.ZOOM:
        if self.bot_in_db.use_zoom_web_adapter():
            return self.get_zoom_web_bot_adapter()
        else:
            return self.get_zoom_bot_adapter()  # Native SDK
    elif meeting_type == MeetingTypes.GOOGLE_MEET:
        return self.get_google_meet_bot_adapter()
    elif meeting_type == MeetingTypes.TEAMS:
        return self.get_teams_bot_adapter()
```

## Platform Comparison Matrix

| Feature | Google Meet | Teams | Zoom Web | Zoom Native |
|---------|-------------|-------|----------|-------------|
| **Audio Capture** | 48kHz Float | 48kHz Float | 48kHz Float | 32kHz PCM |
| **Video Sending** | ✓ | ✗ | ✗ | ✓ |
| **Chat Messages** | ✓ | ✓ | ✓ | ✓ |
| **Closed Captions** | ✓ | ✓ | ✓ | ✓ |
| **Bot Login** | ✗ | ✓ | ✗ | ✗ |
| **Recording View** | Gallery/Speaker | Gallery/Speaker | Auto | Gallery/Speaker |
| **Join Delay** | 5s | 10s | 5s | 0s |
| **Utterance Delay** | 0ms | 2000ms | 0ms | 0ms |

## Best Practices for Adapter Development

### 1. Error Handling
```python
def handle_platform_error(self, error_type, context):
    """Standardized error handling pattern"""
    try:
        # Platform-specific error recovery
        self.attempt_recovery(error_type)
    except Exception as e:
        # Fall back to graceful exit
        self.send_message_callback({
            "message": self.Messages.MEETING_ENDED,
            "error_context": context
        })
```

### 2. Resource Management
```python
def cleanup(self):
    """Clean up platform-specific resources"""
    try:
        if self.websocket_server:
            self.websocket_server.shutdown()
        if self.driver:
            self.driver.quit()
        if self.display:
            self.display.stop()
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
```

### 3. Timing Considerations
```python
def get_platform_timing_config(self):
    """Platform-specific timing requirements"""
    return {
        "join_delay": self.get_staged_bot_join_delay_seconds(),
        "utterance_delay": self.get_utterance_delay_ms(), 
        "websocket_timeout": self.get_websocket_timeout_seconds()
    }
```

### 4. Media Quality Optimization
```python
def optimize_media_quality(self):
    """Adjust quality based on platform capabilities"""
    if self.platform_supports_hd_video():
        self.set_video_quality("HD")
    else:
        self.set_video_quality("SD")
```

This guide provides comprehensive coverage of all bot adapters, their capabilities, limitations, and implementation details for developers working with the meeting bot system.
