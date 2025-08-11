# Bot Controller Documentation

## Overview

This documentation provides comprehensive technical documentation for developers working with the bot controller system. The bot controller is responsible for managing meeting bots across different video conferencing platforms (Zoom, Google Meet, Teams) with capabilities for recording, transcription, and real-time interaction.

## Documentation Structure

### [🏗️ Architecture Overview](bot-controller-architecture.md)
**Core system architecture and component relationships**

Covers the complete bot controller architecture including:
- BotController class and its responsibilities
- Pipeline configuration system with predefined configurations
- Platform adapter hierarchy (Google Meet, Teams, Zoom variants)
- Media processing pipeline (audio/video recording and streaming)
- Real-time communication (Redis, WebSocket)
- Error handling and recovery mechanisms

**Target Audience**: Developers new to the codebase, architects planning system changes

---

### [🛠️ Development Guide](bot-controller-development-guide.md)  
**Practical guide for extending and modifying the system**

Step-by-step instructions for:
- Adding new meeting platforms and adapters
- Creating custom pipeline configurations
- Implementing new transcription providers
- Error handling best practices
- Testing and debugging strategies
- Performance optimization techniques

**Target Audience**: Developers actively working on the codebase

---

### [🔌 Bot Adapters Guide](bot-adapters-guide.md)
**Platform-specific adapter implementations**

Detailed documentation for each platform adapter:
- **WebBotAdapter**: Browser-based platforms (Google Meet, Teams, Zoom Web)
- **GoogleMeetBotAdapter**: Video sending, closed captions, UI automation
- **TeamsBotAdapter**: Bot login support, utterance delays, Teams-specific features
- **ZoomWebBotAdapter**: Meeting SDK integration, JWT authentication
- **ZoomBotAdapter**: Native SDK with direct media access

Includes adapter selection logic, platform comparison matrix, and implementation best practices.

**Target Audience**: Developers working on platform integrations

---

### [🎥 Audio/Video Processing Guide](audio-video-processing-guide.md)
**Media processing pipeline and components**

Comprehensive coverage of media processing:
- **Audio Input**: Per-participant streaming vs. non-streaming managers
- **Audio Output**: Bot speech (TTS), real-time audio injection
- **Video Processing**: GStreamer pipeline, encoding, recording
- **Closed Captions**: Platform caption processing and management
- **RTMP Streaming**: Real-time streaming to external endpoints
- **Performance Optimization**: Sample rate handling, timing considerations

**Target Audience**: Developers working on media processing features

---

### [🎤 Transcription Providers Guide](transcription-providers-guide.md)
**Speech-to-text provider integrations**

Complete documentation for transcription system:
- **Available Providers**: Deepgram (streaming), OpenAI Whisper, AssemblyAI, Gladia, Sarvam, Platform Captions
- **Provider Selection Logic**: Automatic selection based on platform and configuration
- **Workflow Patterns**: Streaming vs. batch processing workflows
- **Configuration Examples**: Provider-specific settings and optimizations
- **Error Handling**: Retry logic, failure classification, graceful degradation

**Target Audience**: Developers working on transcription features

---

## Quick Reference

### Key System Components

| Component | Purpose | Key Files |
|-----------|---------|-----------|
| **BotController** | Main orchestrator | `bot_controller/bot_controller.py` |
| **Pipeline Configuration** | Media processing setup | `bot_controller/pipeline_configuration.py` |
| **Platform Adapters** | Platform-specific integration | `*_bot_adapter/*.py` |
| **Audio Managers** | Audio input/output processing | `bot_controller/*audio*.py` |
| **GStreamer Pipeline** | Video encoding and muxing | `bot_controller/gstreamer_pipeline.py` |
| **Transcription Tasks** | Speech-to-text processing | `tasks/process_utterance_task.py` |

### Platform Support Matrix

| Platform | Adapter Type | Audio Sample Rate | Video Support | Transcription Default |
|----------|--------------|-------------------|---------------|----------------------|
| **Google Meet** | Browser | 48kHz Float | ✓ | Platform Captions |
| **Teams** | Browser | 48kHz Float | ✗ | Platform Captions |
| **Zoom Web** | Browser + SDK | 48kHz Float | ✗ | Platform Captions |
| **Zoom Native** | Native SDK | 32kHz PCM | ✓ | Deepgram |

### Configuration Quick Start

```python
# Basic recording bot
pipeline = PipelineConfiguration.recorder_bot()

# Audio-only with real-time streaming
pipeline = PipelineConfiguration.audio_recorder_bot_with_websocket_audio()

# RTMP streaming bot
pipeline = PipelineConfiguration.rtmp_streaming_bot()

# Transcription-only bot
pipeline = PipelineConfiguration.pure_transcription_bot()
```

## Development Workflow

1. **Understanding the System**: Start with [Architecture Overview](bot-controller-architecture.md)
2. **Making Changes**: Follow [Development Guide](bot-controller-development-guide.md)
3. **Platform Work**: Reference [Bot Adapters Guide](bot-adapters-guide.md)
4. **Media Features**: Use [Audio/Video Processing Guide](audio-video-processing-guide.md)
5. **Transcription Work**: Consult [Transcription Providers Guide](transcription-providers-guide.md)

## Common Development Tasks

### Adding a New Meeting Platform
1. Create adapter class inheriting from `WebBotAdapter` or `BotAdapter`
2. Add meeting type to `MeetingTypes` enum
3. Update URL detection in `meeting_type_from_url()`
4. Add adapter creation method in `BotController`
5. Configure platform-specific settings (sample rates, timing, etc.)

### Adding a New Transcription Provider
1. Add provider to `TranscriptionProviders` enum
2. Implement provider-specific transcription logic
3. Update provider selection in `transcription_provider_from_bot_creation_data()`
4. Add provider handling in audio managers
5. Configure provider-specific optimizations (chunk sizes, limits)

### Modifying Pipeline Configuration
1. Define new configuration in `PipelineConfiguration` class
2. Add to valid configurations list
3. Update selection logic in `get_pipeline_configuration()`
4. Test with different platforms and scenarios

## Contributing

When contributing to the bot controller system:

1. **Read the relevant documentation** before making changes
2. **Follow existing patterns** for consistency
3. **Test across platforms** as behavior varies significantly
4. **Update documentation** when adding new features
5. **Consider backwards compatibility** for configuration changes

## Support

For technical questions about the bot controller system:
- Reference the appropriate guide above
- Check existing code patterns in similar components
- Test changes thoroughly across different platforms and configurations

This documentation is maintained alongside the codebase and should be updated when significant architectural changes are made.
