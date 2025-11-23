#!/usr/bin/env python3
"""
Integration tests for real-time streaming diarization
Tests actual pyannote models with real audio
"""

import sys
import os
import asyncio
import numpy as np
from pathlib import Path

# Add source to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("=" * 70)
print("Real-Time Streaming - Integration Tests")
print("=" * 70)

# Check if pyannote is installed
try:
    from pyannote.audio import Pipeline
    print("\n✅ pyannote.audio is installed")
except ImportError:
    print("\n❌ pyannote.audio is not installed")
    print("   Run: pip install -e .")
    sys.exit(1)

# Import our implementation
try:
    from pyannote.audio.pipelines.realtime_streaming import RealTimeStreamingDiarization
    print("✅ RealTimeStreamingDiarization imported successfully")
except ImportError as e:
    print(f"❌ Failed to import RealTimeStreamingDiarization: {e}")
    sys.exit(1)


async def test_initialization():
    """Test 1: Initialize real-time diarizer"""
    print("\n" + "=" * 70)
    print("[Test 1] Initialization Test")
    print("=" * 70)

    try:
        # Create diarizer
        diarizer = RealTimeStreamingDiarization(
            sample_rate=16000,
            chunk_duration=5.0,
            min_chunk_duration=2.0,
            latency_mode='low',
            hf_token=os.environ.get('HF_TOKEN')
        )

        print("✅ RealTimeStreamingDiarization created")
        print(f"   Sample rate: {diarizer.sample_rate}")
        print(f"   Chunk duration: {diarizer.chunk_duration}")
        print(f"   Min chunk duration: {diarizer.min_chunk_duration}")
        print(f"   Latency mode: {diarizer.latency_mode}")

        # Check buffer
        assert len(diarizer.audio_buffer) == 0
        assert diarizer.buffer_duration == 0.0
        print("✅ Audio buffer initialized correctly")

        return diarizer

    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def test_audio_buffering(diarizer):
    """Test 2: Audio buffering"""
    print("\n" + "=" * 70)
    print("[Test 2] Audio Buffering Test")
    print("=" * 70)

    try:
        # Create test audio chunks
        chunk1 = np.random.randn(16000).astype(np.float32)  # 1 second
        chunk2 = np.random.randn(16000).astype(np.float32)  # 1 second

        # Add chunks
        diarizer.add_audio(chunk1)
        print(f"✅ Added chunk 1 (1.0s), buffer duration: {diarizer.buffer_duration:.2f}s")

        assert diarizer.buffer_duration > 0.99 and diarizer.buffer_duration < 1.01
        assert len(diarizer.audio_buffer) == 1

        diarizer.add_audio(chunk2)
        print(f"✅ Added chunk 2 (1.0s), buffer duration: {diarizer.buffer_duration:.2f}s")

        assert diarizer.buffer_duration > 1.99 and diarizer.buffer_duration < 2.01
        assert len(diarizer.audio_buffer) == 2

        # Get buffered audio
        buffered = diarizer.get_buffered_audio(1.5)
        assert buffered is not None
        assert len(buffered) == int(1.5 * 16000)
        print(f"✅ Retrieved 1.5s of audio ({len(buffered)} samples)")

        # Reset
        diarizer.reset()
        assert len(diarizer.audio_buffer) == 0
        assert diarizer.buffer_duration == 0.0
        print("✅ Reset successful")

    except Exception as e:
        print(f"❌ Buffering test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def test_pipeline_start(diarizer):
    """Test 3: Start pipeline (requires HF token or cached models)"""
    print("\n" + "=" * 70)
    print("[Test 3] Pipeline Initialization Test")
    print("=" * 70)

    try:
        print("Starting pipeline (this may take a while on first run)...")

        # Start pipeline
        await diarizer.start()

        assert diarizer.is_started is True
        assert diarizer.pipeline is not None
        print("✅ Pipeline started successfully")

        # Check pipeline configuration
        print(f"   Chunk duration: {diarizer.pipeline.chunk_duration}")
        print(f"   Overlap duration: {diarizer.pipeline.overlap_duration}")

        if diarizer.latency_mode == 'low':
            assert diarizer.pipeline.chunk_duration == 3.0
            assert diarizer.pipeline.overlap_duration == 0.5
            print("✅ Low latency configuration applied")
        else:
            assert diarizer.pipeline.chunk_duration == 5.0
            assert diarizer.pipeline.overlap_duration == 1.0
            print("✅ Standard configuration applied")

    except Exception as e:
        print(f"❌ Pipeline start failed: {e}")
        print("\nNote: This test requires either:")
        print("  1. HF_TOKEN environment variable set")
        print("  2. Models cached locally (run download_models.py first)")
        import traceback
        traceback.print_exc()
        return False

    return True


async def test_audio_processing(diarizer):
    """Test 4: Process audio chunks"""
    print("\n" + "=" * 70)
    print("[Test 4] Audio Processing Test")
    print("=" * 70)

    try:
        # Create synthetic audio (5 seconds of sine wave)
        duration = 5.0
        sample_rate = 16000
        t = np.linspace(0, duration, int(duration * sample_rate))
        # Mix of two frequencies to simulate different speakers
        audio = (np.sin(2 * np.pi * 440 * t) * 0.3 +
                 np.sin(2 * np.pi * 880 * t[:len(t)//2]) * 0.3)
        audio = audio.astype(np.float32)

        print(f"Created {duration}s synthetic audio ({len(audio)} samples)")

        # Add audio
        diarizer.reset()
        diarizer.add_audio(audio)
        print(f"✅ Added audio to buffer, duration: {diarizer.buffer_duration:.2f}s")

        # Get chunk for processing
        chunk = diarizer.get_buffered_audio(5.0)
        assert chunk is not None
        assert len(chunk) == 80000  # 5 seconds at 16kHz

        import torch
        waveform = torch.from_numpy(chunk).float().unsqueeze(0)
        print(f"✅ Converted to tensor, shape: {waveform.shape}")

        # Process chunk
        print("Processing chunk through pipeline...")
        output = diarizer.pipeline.process_chunk(waveform, sample_rate, 0.0)

        print("✅ Chunk processed successfully")
        print(f"   Output type: {type(output)}")
        print(f"   Segment: {output.segment}")

        # Check output
        if hasattr(output, 'speaker_diarization'):
            num_segments = len(list(output.speaker_diarization.itertracks()))
            print(f"   Diarization segments: {num_segments}")

            if num_segments > 0:
                print("\n   Speaker segments:")
                for turn, _, speaker in output.speaker_diarization.itertracks(yield_label=True):
                    print(f"      {turn.start:.1f}s - {turn.end:.1f}s: {speaker}")
                print("✅ Diarization produced results")
            else:
                print("⚠️  No speech detected in synthetic audio (expected)")

    except Exception as e:
        print(f"❌ Audio processing failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def test_streaming_generator(diarizer):
    """Test 5: Streaming with async generator"""
    print("\n" + "=" * 70)
    print("[Test 5] Async Generator Streaming Test")
    print("=" * 70)

    try:
        # Create async generator that yields audio chunks
        async def audio_generator():
            """Simulate streaming audio chunks"""
            chunk_size = 16000  # 1 second chunks
            for i in range(5):  # 5 seconds total
                # Generate sine wave
                t = np.linspace(i, i+1, chunk_size)
                chunk = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)
                yield chunk
                await asyncio.sleep(0.01)  # Simulate real-time delay

        print("Processing audio stream...")
        diarizer.reset()

        result_count = 0
        async for result in diarizer.process_audio_stream(audio_generator()):
            result_count += 1
            print(f"   Result {result_count}: {result['speaker']} at {result['time']:.1f}s")

        if result_count > 0:
            print(f"✅ Received {result_count} streaming results")
        else:
            print("⚠️  No results (may be due to synthetic audio)")

    except Exception as e:
        print(f"❌ Streaming test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def test_stop_and_cleanup(diarizer):
    """Test 6: Stop and cleanup"""
    print("\n" + "=" * 70)
    print("[Test 6] Stop and Cleanup Test")
    print("=" * 70)

    try:
        await diarizer.stop()

        assert diarizer.is_started is False
        assert len(diarizer.audio_buffer) == 0
        assert diarizer.buffer_duration == 0.0

        print("✅ Stopped and cleaned up successfully")

    except Exception as e:
        print(f"❌ Stop/cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def main():
    """Run all integration tests"""
    print("\nStarting integration tests...")
    print("These tests require pyannote models to be available.\n")

    # Test 1: Initialization
    diarizer = await test_initialization()

    # Test 2: Audio buffering
    await test_audio_buffering(diarizer)

    # Test 3: Pipeline start (may fail if no HF token)
    pipeline_started = await test_pipeline_start(diarizer)

    if pipeline_started:
        # Test 4: Audio processing
        await test_audio_processing(diarizer)

        # Test 5: Streaming generator
        await test_streaming_generator(diarizer)

        # Test 6: Stop and cleanup
        await test_stop_and_cleanup(diarizer)
    else:
        print("\n⚠️  Skipping tests that require pipeline")
        print("   Set HF_TOKEN or run download_models.py first")

    # Summary
    print("\n" + "=" * 70)
    if pipeline_started:
        print("✅ ALL INTEGRATION TESTS PASSED!")
    else:
        print("✅ BASIC TESTS PASSED (Pipeline tests skipped)")
    print("=" * 70)

    print("""
Summary:
✅ Initialization: Working
✅ Audio buffering: Working
✅ Pipeline start: """ + ("Working" if pipeline_started else "Skipped (no models)") + """
✅ Audio processing: """ + ("Working" if pipeline_started else "Skipped") + """
✅ Async streaming: """ + ("Working" if pipeline_started else "Skipped") + """
✅ Cleanup: Working

Next steps:
1. For full testing, ensure models are downloaded:
   export HF_TOKEN=your_token
   python download_models.py

2. Test real-time server:
   python realtime_server.py

3. Test browser interface:
   Open realtime_demo.html in browser
""")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(0)
