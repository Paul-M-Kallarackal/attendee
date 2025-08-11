# Audio/Video Processing Guide

## Overview

The bot controller implements a sophisticated audio/video processing pipeline that handles:
- **Per-participant audio capture and transcription**
- **Mixed audio streaming and recording** 
- **Video capture and encoding**
- **Real-time audio output and TTS**
- **Closed caption processing**
- **RTMP streaming**

## Audio Input Processing

### Per-Participant Audio Management

The system provides two complementary approaches for handling per-participant audio:

#### 1. Non-Streaming Audio Input Manager

**Purpose**: Batch processing for transcription providers that require complete audio files.

**File**: `per_participant_non_streaming_audio_input_manager.py`

**Key Features**:
- **Buffer Management**: Accumulates audio chunks per speaker
- **Voice Activity Detection (VAD)**: Uses WebRTC VAD + RMS analysis
- **Utterance Segmentation**: Breaks speech into logical units
- **Provider Optimization**: Tailors chunk sizes for specific transcription providers

**Core Algorithm**:
```python
def process_chunk(self, speaker_id, chunk_time, chunk_bytes):
    audio_is_silent = self.silence_detected(chunk_bytes)
    
    # Initialize buffer for new speaker
    if speaker_id not in self.utterances:
        if audio_is_silent:
            return  # Ignore leading silence
        self.utterances[speaker_id] = bytearray()
        self.first_nonsilent_audio_time[speaker_id] = chunk_time
    
    # Add audio to buffer
    if chunk_bytes:
        self.utterances[speaker_id].extend(chunk_bytes)
    
    # Check flush conditions
    should_flush = (
        len(self.utterances[speaker_id]) >= self.UTTERANCE_SIZE_LIMIT or
        (audio_is_silent and silence_duration >= self.SILENCE_DURATION_LIMIT)
    )
    
    if should_flush:
        self.save_utterance_callback({
            "participant_uuid": speaker_id,
            "audio_data": bytes(self.utterances[speaker_id]),
            "timestamp_ms": int(self.first_nonsilent_audio_time[speaker_id].timestamp() * 1000),
            "sample_rate": self.sample_rate
        })
```

**Silence Detection**:
```python
def silence_detected(self, chunk_bytes):
    # RMS-based silence detection (low amplitude)
    if calculate_normalized_rms(chunk_bytes) < 0.01:
        return True
    
    # WebRTC VAD for speech detection
    return not self.vad.is_speech(chunk_bytes, self.sample_rate)

def calculate_normalized_rms(audio_bytes):
    samples = np.frombuffer(audio_bytes, dtype=np.int16)
    rms = np.sqrt(np.mean(np.square(samples)))
    return rms / 32768  # Normalize by max 16-bit value
```

**Provider-Specific Optimizations**:
- **Whisper**: 300-second utterances, 3-second silence limit
- **Sarvam**: 30-second utterances, 1-second silence limit
- **Other providers**: Configurable limits based on API constraints

#### 2. Streaming Audio Input Manager

**Purpose**: Real-time streaming transcription for providers like Deepgram.

**File**: `per_participant_streaming_audio_input_manager.py`

**Key Features**:
- **Live Transcription**: Immediate streaming to transcription API
- **Multi-Speaker Support**: Independent streams per participant
- **Resource Management**: Automatic cleanup of idle streams
- **Metadata Integration**: Bot and participant context in transcriptions

**Streaming Lifecycle**:
```python
def add_chunk(self, speaker_id, chunk_time, chunk_bytes):
    audio_is_silent = self.silence_detected(chunk_bytes)
    
    if not audio_is_silent:
        self.last_nonsilent_audio_time[speaker_id] = time.time()
    
    # Skip creating stream for silent audio
    if audio_is_silent and speaker_id not in self.streaming_transcribers:
        return
    
    # Create or get existing stream
    streaming_transcriber = self.find_or_create_streaming_transcriber_for_speaker(speaker_id)
    streaming_transcriber.send(chunk_bytes)

def monitor_transcription(self):
    """Clean up idle streams and enforce resource limits"""
    speakers_to_remove = []
    
    # Remove streams that have been silent too long
    for speaker_id, transcriber in self.streaming_transcribers.items():
        if time.time() - self.last_nonsilent_audio_time[speaker_id] > self.SILENCE_DURATION_LIMIT:
            transcriber.finish()
            speakers_to_remove.append(speaker_id)
    
    # Enforce maximum concurrent streams (4)
    if len(self.streaming_transcribers) > 4:
        oldest_transcriber = min(self.streaming_transcribers.values(), 
                                key=lambda x: x.last_send_time)
        oldest_transcriber.finish()
        del self.streaming_transcribers[oldest_transcriber.speaker_id]
```

**Deepgram Integration**:
```python
def create_streaming_transcriber(self, speaker_id, metadata):
    if self.transcription_provider == TranscriptionProviders.DEEPGRAM:
        return DeepgramStreamingTranscriber(
            deepgram_api_key=self.deepgram_api_key,
            interim_results=True,
            language=self.bot.deepgram_language(),
            model=self.bot.deepgram_model(),
            callback=self.bot.deepgram_callback(),
            sample_rate=self.sample_rate,
            metadata=metadata_list,
            redaction_settings=self.bot.deepgram_redaction_settings()
        )
```

### Closed Caption Processing

**Purpose**: Handle platform-provided closed captions as an alternative to audio transcription.

**File**: `closed_caption_manager.py`

**Features**:
- **In-Memory Buffering**: Captions stored temporarily for processing
- **Update Handling**: Captions can be modified until finalized
- **Batched Database Writes**: Reduces database load
- **Automatic Cleanup**: Remove old captions from memory

**Caption Lifecycle**:
```python
class CaptionEntry:
    def __init__(self, caption_data: dict):
        self.caption_data = caption_data
        self.created_at = datetime.utcnow()
        self.last_upsert_to_db_at = None
        self.only_save_final_captions = True
    
    def should_upsert_to_db(self, should_flush=False) -> bool:
        # Only save final captions unless forcing flush
        if self.only_save_final_captions:
            return self.caption_data.get("isFinal") or should_flush
        
        # Save after 1 second delay for interim captions
        return (datetime.utcnow() - self.created_at) > timedelta(seconds=1)
```

**Processing Flow**:
```python
def process_captions(self, should_flush=False):
    for key, entry in list(self.captions.items()):
        if entry.should_upsert_to_db(should_flush=should_flush):
            participant = self.get_participant_callback(entry.caption_data["deviceId"])
            
            if participant:
                self.save_utterance_callback({
                    **participant,
                    "timestamp_ms": int(entry.created_at.timestamp() * 1000),
                    "duration_ms": int((entry.modified_at - entry.created_at).total_seconds() * 1000),
                    "text": entry.caption_data.get("text", ""),
                    "source_uuid_suffix": f"{entry.caption_data['deviceId']}-{entry.caption_data['captionId']}"
                })
```

## Audio Output Processing

### Audio Output Manager

**Purpose**: Handle bot speech output (TTS and pre-recorded audio).

**File**: `audio_output_manager.py`

**Features**:
- **Multiple Audio Sources**: TTS generation and audio file playback
- **Chunked Playback**: Streams audio in small chunks to prevent blocking
- **Thread Management**: Non-blocking audio output
- **Timing Control**: Platform-specific playback timing

**Playback Process**:
```python
def start_playing_audio_media_request(self, audio_media_request):
    # Stop any existing playback
    self._stop_audio_thread()
    
    if audio_media_request.media_blob:
        # Handle pre-recorded audio
        self.audio_data = mp3_to_pcm(audio_media_request.media_blob.blob, 
                                   sample_rate=self.SAMPLE_RATE)
        self.duration_ms = audio_media_request.media_blob.duration_ms
    else:
        # Generate TTS audio
        audio_blob, duration_ms = generate_audio_from_text(
            text=audio_media_request.text_to_speak,
            settings=audio_media_request.text_to_speech_settings,
            sample_rate=self.SAMPLE_RATE,
            bot=audio_media_request.bot
        )
        self.audio_data = audio_blob
        self.duration_ms = duration_ms
    
    # Start playback thread
    self.audio_thread = threading.Thread(target=self._play_audio_chunks)
    self.audio_thread.start()

def _play_audio_chunks(self, audio_data, chunk_size):
    """Stream audio data in chunks with timing control"""
    for i in range(0, len(audio_data), chunk_size):
        if self.stop_audio_thread:
            break
        chunk = audio_data[i:i + chunk_size]
        self.play_raw_audio_callback(bytes=chunk, sample_rate=self.SAMPLE_RATE)
        time.sleep(self.sleep_time_between_chunks_seconds)
```

### Realtime Audio Output Manager

**Purpose**: Handle real-time audio injection from external WebSocket sources.

**File**: `realtime_audio_output_manager.py`

**Features**:
- **Sample Rate Conversion**: Upsample incoming audio to output rate
- **Buffer Management**: Queue chunks for smooth playback
- **Automatic Threading**: Start/stop playback threads as needed
- **Timeout Handling**: Stop playback when no new audio arrives

**Real-time Processing**:
```python
def add_chunk(self, chunk, sample_rate):
    # Clear old buffer if there's been a gap
    if time.time() - self.last_chunk_time > 0.15:
        self.inner_chunk_buffer = b""
    
    self.inner_chunk_buffer += chunk
    chunk_size_bytes = int(self.bytes_per_sample * self.chunk_length_seconds * sample_rate)
    
    # Process complete chunks
    while len(self.inner_chunk_buffer) >= chunk_size_bytes:
        self.add_chunk_inner(self.inner_chunk_buffer[:chunk_size_bytes], sample_rate)
        self.inner_chunk_buffer = self.inner_chunk_buffer[chunk_size_bytes:]

def _process_audio_queue(self):
    """Process audio chunks with automatic thread management"""
    while not self.stop_audio_thread:
        try:
            chunk, sample_rate = self.audio_queue.get(timeout=1.0)
            
            # Upsample to output sample rate
            chunk_upsampled = self.upsample_chunk_to_output_sample_rate(chunk, sample_rate)
            
            # Play the chunk
            self.play_raw_audio_callback(bytes=chunk_upsampled, 
                                       sample_rate=self.output_sample_rate)
            
            time.sleep(self.sleep_time_between_chunks_seconds * self.chunk_length_seconds)
            
        except queue.Empty:
            # Timeout if no new chunks
            if time.time() - self.last_chunk_time > 10:
                break
```

**Upsampling Algorithm**:
```python
def upsample_chunk_to_output_sample_rate(self, chunk, sample_rate):
    if sample_rate == self.output_sample_rate:
        return chunk
    
    ratio = self.output_sample_rate // sample_rate
    
    # Use simple repetition for integer ratios (better performance)
    if self.output_sample_rate % sample_rate == 0 and ratio > 1:
        samples = np.frombuffer(chunk, dtype=np.int16)
        upsampled_samples = np.repeat(samples, ratio)
        return upsampled_samples.tobytes()
    else:
        # Use audioop for non-integer ratios
        return _upsample(chunk, sample_rate, self.output_sample_rate)
```

## Video Processing

### Video Output Manager

**Purpose**: Manage bot video display in meetings.

**File**: `video_output_manager.py`

**Features**:
- **Video Playback Control**: Start/stop video display
- **Playback Monitoring**: Check if videos are still playing
- **Single Video Policy**: Only one video plays at a time
- **Platform Integration**: Adapter-specific video handling

**Video Management**:
```python
def start_playing_video_media_request(self, video_media_request):
    """Start playing a video in the meeting"""
    self.currently_playing_video_media_request = video_media_request
    self.play_video_callback(video_media_request.media_url)

def monitor_currently_playing_video_media_request(self):
    """Check if current video is still playing (rate-limited)"""
    if not self.currently_playing_video_media_request:
        return
    
    # Only check every 2 seconds (may be expensive)
    if time.time() - self.last_check_time < 2:
        return
    
    if not self.check_if_still_playing_callback():
        # Video finished
        self.currently_playing_video_media_request_finished_callback(
            self.currently_playing_video_media_request
        )
        self.currently_playing_video_media_request = None
```

### GStreamer Pipeline

**Purpose**: Handle video encoding, muxing, and output for recording/streaming.

**File**: `gstreamer_pipeline.py`

**Pipeline Architecture**:
```
Video Input: appsrc → videoconvert → videorate → x264enc
Audio Input: appsrc → audioconvert → audiorate → voaacenc
Muxing: video + audio → mp4mux/flvmux/matroskamux
Output: muxer → filesink/appsink
```

**Pipeline Configuration**:
```python
def setup(self):
    # Configure muxer based on output format
    if self.output_format == self.OUTPUT_FORMAT_MP4:
        muxer_string = "mp4mux name=muxer"
    elif self.output_format == self.OUTPUT_FORMAT_FLV:
        muxer_string = "h264parse ! flvmux name=muxer streamable=true"
    elif self.output_format == self.OUTPUT_FORMAT_WEBM:
        muxer_string = "h264parse ! matroskamux name=muxer"
    
    # Configure sink
    if self.sink_type == self.SINK_TYPE_APPSINK:
        sink_string = "appsink name=sink emit-signals=true"
    else:
        sink_string = f"filesink location={self.file_location}"
    
    # Build complete pipeline
    pipeline_str = f"""
        appsrc name=video_source ! videoconvert ! videorate ! 
        x264enc tune=zerolatency speed-preset=ultrafast ! 
        {muxer_string} ! {sink_string}
        appsrc name=audio_source ! audioconvert ! audiorate ! 
        voaacenc bitrate=128000 ! muxer.
    """
    
    self.pipeline = Gst.parse_launch(pipeline_str)
```

**Frame Processing**:
```python
def on_new_video_frame(self, frame, current_time_ns):
    # Initialize timing on first frame
    if self.start_time_ns is None:
        self.start_time_ns = current_time_ns
    
    # Create buffer with proper timestamp
    buffer = Gst.Buffer.new_wrapped(frame)
    buffer.pts = current_time_ns - self.start_time_ns
    buffer.duration = 33 * 1000 * 1000  # 33ms (30fps)
    
    # Push to pipeline
    ret = self.appsrc.emit("push-buffer", buffer)
    if ret != Gst.FlowReturn.OK:
        logger.warning(f"Failed to push video buffer: {ret}")
```

**Performance Monitoring**:
```python
def monitor_pipeline_stats(self):
    """Track queue drops and performance"""
    for queue_name in self.queue_drops:
        drops = self.queue_drops[queue_name] - self.last_reported_drops[queue_name]
        if drops > 0:
            logger.info(f"{queue_name}: {drops} buffers dropped")
        self.last_reported_drops[queue_name] = self.queue_drops[queue_name]

def on_queue_overrun(self, queue, queue_name):
    """Callback for queue buffer drops"""
    self.queue_drops[queue_name] += 1
```

## RTMP Streaming

### RTMP Client

**Purpose**: Stream processed video/audio to external RTMP endpoints.

**File**: `rtmp_client.py`

**Features**:
- **FFmpeg Integration**: Uses FFmpeg for RTMP streaming
- **Direct Copy**: No re-encoding for FLV input
- **Error Handling**: Broken pipe and connection detection
- **Process Management**: Graceful start/stop

**Streaming Process**:
```python
def start(self):
    """Start RTMP streaming to endpoint"""
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",           # Overwrite output
        "-f", "flv",    # Input format (from GStreamer)
        "-i", "pipe:0", # Read from stdin
        "-c", "copy",   # Copy without re-encoding
        "-f", "flv",    # Output format
        self.rtmp_url   # RTMP destination
    ]
    
    self.ffmpeg_process = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=10**8  # Large buffer for smooth streaming
    )

def write_data(self, flv_data):
    """Write FLV data to RTMP stream"""
    try:
        self.ffmpeg_process.stdin.write(flv_data)
        self.ffmpeg_process.stdin.flush()
        return True
    except BrokenPipeError:
        logger.info("RTMP stream connection lost")
        self.is_running = False
        return False
```

## Audio Quality and Timing

### Sample Rate Handling

Different platforms use different audio sample rates:

| Platform | Sample Rate | Format |
|----------|-------------|--------|
| **Zoom Native SDK** | 32kHz | 16-bit PCM |
| **Zoom Web** | 48kHz | 32-bit Float |
| **Google Meet** | 48kHz | 32-bit Float |
| **Teams** | 48kHz | 32-bit Float |

### Platform-Specific Timing

```python
def get_sleep_time_between_audio_output_chunks_seconds(self):
    """Platform-specific audio chunk timing"""
    meeting_type = self.get_meeting_type()
    if meeting_type == MeetingTypes.ZOOM:
        return 0.9  # Zoom needs longer gaps
    return 0.1      # Other platforms can handle faster chunks

def get_per_participant_audio_utterance_delay_ms(self):
    """Compensate for platform-specific delays"""
    meeting_type = self.get_meeting_type()
    if meeting_type == MeetingTypes.TEAMS:
        return 2000  # Teams has significant delay
    return 0
```

### Voice Activity Detection

The system uses dual VAD approach:
1. **RMS-based detection**: Catches very quiet speech
2. **WebRTC VAD**: Advanced speech detection

```python
def silence_detected(self, chunk_bytes):
    # Energy-based detection (configurable threshold)
    if calculate_normalized_rms(chunk_bytes) < threshold:
        return True
    
    # WebRTC VAD for sophisticated speech detection
    return not self.vad.is_speech(chunk_bytes, self.sample_rate)
```

## Performance Considerations

### Memory Management
- **Buffer Limits**: Utterance size limits prevent memory buildup
- **Stream Cleanup**: Automatic cleanup of idle transcription streams
- **Caption Pruning**: Remove old captions from memory

### CPU Optimization
- **Efficient Upsampling**: Use sample repetition when possible
- **Queue Management**: Rate-limited processing to prevent overload
- **Batched Operations**: Group database operations

### Network Optimization
- **Chunked Streaming**: Small chunks for real-time responsiveness
- **Backpressure Handling**: Handle network congestion gracefully
- **Error Recovery**: Automatic reconnection for stream failures

This comprehensive audio/video processing system provides robust, scalable meeting bot capabilities across multiple platforms while maintaining high quality and performance.
