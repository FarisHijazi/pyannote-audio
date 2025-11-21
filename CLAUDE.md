# PyAnnote Audio - Claude Development Notes

## Project Overview

This is the pyannote-audio repository, a speaker diarization toolkit for Python. This document tracks changes and improvements made during Claude development sessions.

## Recent Changes

###  2025-11-21: Added Streaming Speaker Diarization Feature

#### Summary
Implemented a major new feature: **Streaming Speaker Diarization**. This allows pyannote-audio to process audio in chunks/streams rather than requiring a complete audio file upfront.

#### What Was Changed

1. **New StreamingSpeakerDiarization Pipeline** (`src/pyannote/audio/pipelines/streaming_speaker_diarization.py`)
   - Extends the base `SpeakerDiarization` class
   - Processes audio in configurable chunks (default: 5 second chunks with 1 second overlap)
   - Maintains speaker registry across chunks for consistent speaker identification
   - Supports two streaming modes:
     - File-based streaming: Process large audio files incrementally
     - Generator-based streaming: Process truly streaming audio (e.g., from microphone or network)

2. **Key Features**:
   - **Incremental Processing**: Audio is processed in chunks, reducing memory footprint
   - **Speaker Tracking**: Maintains speaker embeddings across chunks using cosine similarity matching
   - **Real-time Updates**: Yields diarization results as each chunk is processed
   - **Configurable Parameters**:
     - `chunk_duration`: Duration of each chunk (default 5.0s)
     - `overlap_duration`: Overlap between chunks (default 1.0s)
     - `speaker_threshold`: Similarity threshold for matching speakers (default 0.75)
     - `min_speakers`/`max_speakers`: Control number of speakers

3. **API Methods**:
   - `stream(audio_file)`: Process an audio file in streaming mode
   - `stream_from_generator(audio_generator)`: Process audio from a generator (for live streams)
   - `process_chunk(waveform, sample_rate, chunk_start)`: Process a single audio chunk
   - `reset()`: Reset streaming state between audio files

4. **Output Format** (`StreamingDiarizeOutput`):
   - `segment`: Time range for the current chunk
   - `speaker_diarization`: Diarization for this chunk only
   - `cumulative_diarization`: Complete diarization from start to current chunk
   - `speaker_embeddings`: Embeddings for speakers in this chunk
   - `is_final`: Flag indicating if this is the last chunk

#### Files Created/Modified

**New Files**:
- `src/pyannote/audio/pipelines/streaming_speaker_diarization.py` - Main streaming pipeline implementation
- `test_streaming_diarization.py` - Comprehensive test script with HF token management
- `.env.example` - Template for environment variables (HuggingFace token)

**Modified Files**:
- `src/pyannote/audio/pipelines/__init__.py` - Added `StreamingSpeakerDiarization` to exports

#### Usage Example

```python
from pyannote.audio.pipelines.streaming_speaker_diarization import StreamingSpeakerDiarization

# Initialize pipeline
pipeline = StreamingSpeakerDiarization.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token="YOUR_HF_TOKEN"
)

# Configure streaming parameters
pipeline.chunk_duration = 5.0  # 5 second chunks
pipeline.overlap_duration = 1.0  # 1 second overlap
pipeline.speaker_threshold = 0.75  # Speaker matching threshold

# Process audio file in streaming mode
for output in pipeline.stream("audio.wav"):
    print(f"[{output.segment.start:.1f}s - {output.segment.end:.1f}s]")
    for turn, _, speaker in output.speaker_diarization.itertracks(yield_label=True):
        print(f"  {turn.start:.1f}s - {turn.end:.1f}s: {speaker}")

    if output.is_final:
        print(f"Complete! Total speakers: {len(output.cumulative_diarization.labels())}")
```

#### HuggingFace Token Setup

The streaming diarization requires a HuggingFace token with access to pyannote models:

1. Get token from: https://huggingface.co/settings/tokens
2. Accept terms for:
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
3. Set token via:
   - Environment variable: `export HF_TOKEN=your_token`
   - `.env` file: `HF_TOKEN=your_token`
   - Or use the interactive prompt in `test_streaming_diarization.py`

#### Testing

Run the test script:
```bash
python test_streaming_diarization.py
```

The script will:
- Prompt for HuggingFace token if not configured
- Test file-based streaming on sample audio
- Optionally test generator-based streaming
- Display detailed progress and results

#### Technical Details

**Speaker Matching Algorithm**:
- Extracts embeddings for each speech segment in a chunk
- Compares embeddings to known speakers using cosine similarity
- Matches to existing speaker if similarity ≥ threshold
- Creates new speaker if no match found (unless max_speakers reached)
- Updates speaker embeddings using exponential moving average

**Memory Management**:
- Only processes one chunk at a time in memory
- Cumulative diarization is lightweight (just Annotation objects)
- Speaker registry maintains one embedding per speaker

**Limitations**:
- Clustering is simpler than batch mode (no VBx clustering)
- Speaker count accuracy may be lower than batch processing
- First few chunks may have less accurate speaker assignments
- Not suitable for applications requiring perfect speaker count

#### Future Improvements

Potential enhancements for future development:
- Add buffer/look-ahead for better chunk boundary handling
- Implement online clustering algorithms for better speaker tracking
- Add speaker re-identification for handling long gaps
- Support for speaker enrollment (known speaker embeddings)
- Performance optimizations for real-time processing
- Better handling of overlapping speech
- Confidence scores for speaker assignments

#### Dependencies

No new dependencies were added. The streaming feature uses the existing pyannote-audio stack:
- torch, torchaudio, torchcodec
- pyannote-core, pyannote-pipeline
- scipy (for cosine distance calculations)

## Development Environment

- Python 3.11
- PyTorch 2.8.0 with CUDA 12.8
- pyannote.audio 0.1.dev281

## Testing Status

- ✅ Code implementation complete
- ⏳ Installation in progress (pip install -e .)
- ⏳ Integration testing pending
- ⏳ End-to-end streaming test pending

## Notes for Future Development

- The streaming pipeline inherits from `SpeakerDiarization`, so it has access to all the same models and parameters
- The `reset()` method should be called between processing different audio files
- Consider GPU memory constraints when setting chunk_duration for real-time applications
- The overlap_duration helps with continuity at chunk boundaries but increases computation

---

Last updated: 2025-11-21
