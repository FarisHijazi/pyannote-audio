#!/usr/bin/env python3
"""Test script for streaming speaker diarization"""

import os
import sys
from pathlib import Path
import warnings

# Add the source directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import torch
from pyannote.audio.pipelines.streaming_speaker_diarization import StreamingSpeakerDiarization


def get_hf_token():
    """Get HuggingFace token from environment or .env file"""

    # Check environment variables
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

    if token:
        return token

    # Check .env file
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("HF_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                    if token and token != "your_huggingface_token_here":
                        return token

    # Try without token first (models might be cached)
    print("\n" + "="*70)
    print("HuggingFace Token Check")
    print("="*70)
    print("\nNo HF token found in environment or .env file.")
    print("Checking if models are already cached locally...")

    # Try loading without token
    try:
        from pyannote.audio import Pipeline
        Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=None
        )
        print("✅ Models found in cache! No token needed.")
        return None
    except Exception:
        pass

    # Prompt user for token
    print("\n❌ Models not cached. HuggingFace token required for first download.")
    print("\nSteps to get your token:")
    print("  1. Go to https://huggingface.co/settings/tokens")
    print("  2. Create a new token (or use existing one)")
    print("  3. Accept pyannote/speaker-diarization terms at:")
    print("     https://huggingface.co/pyannote/speaker-diarization-3.1")
    print("  4. Accept pyannote/segmentation terms at:")
    print("     https://huggingface.co/pyannote/segmentation-3.0")
    print("\nYou can either:")
    print("  - Set HF_TOKEN environment variable")
    print("  - Create .env file with: HF_TOKEN=your_token")
    print("  - Enter token now (will be saved to .env)")
    print("  - Or press Enter to try without token (will fail if not cached)\n")

    token = input("Enter your HuggingFace token (or press Enter to skip): ").strip()

    if not token:
        print("\n⚠️  No token provided. Attempting to continue without token...")
        print("This will only work if models are already cached locally.")
        return None

    # Save token to .env file
    save = input("\nSave token to .env file for future use? (y/n): ").strip().lower()
    if save == 'y':
        with open(env_file, 'w') as f:
            f.write(f"# HuggingFace API Token\n")
            f.write(f"# Get your token from: https://huggingface.co/settings/tokens\n")
            f.write(f"HF_TOKEN={token}\n")
        print(f"Token saved to {env_file}")

        # Add .env to .gitignore if not already there
        gitignore = Path(__file__).parent / ".gitignore"
        if gitignore.exists():
            with open(gitignore, 'r') as f:
                content = f.read()
            if '.env' not in content:
                with open(gitignore, 'a') as f:
                    f.write("\n# Environment variables\n.env\n")
                print("Added .env to .gitignore")

    return token


def test_streaming_diarization(audio_file: str, hf_token: str):
    """Test streaming diarization on an audio file"""

    print("\n" + "="*70)
    print("Testing Streaming Speaker Diarization")
    print("="*70)
    print(f"\nAudio file: {audio_file}")
    print(f"Loading pipeline...")

    try:
        # Initialize streaming pipeline
        pipeline = StreamingSpeakerDiarization.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )

        # Set parameters for streaming
        pipeline.chunk_duration = 5.0  # 5 second chunks
        pipeline.overlap_duration = 1.0  # 1 second overlap
        pipeline.speaker_threshold = 0.75  # Speaker matching threshold

        print("Pipeline loaded successfully!")
        print(f"\nConfiguration:")
        print(f"  - Chunk duration: {pipeline.chunk_duration}s")
        print(f"  - Overlap duration: {pipeline.overlap_duration}s")
        print(f"  - Speaker threshold: {pipeline.speaker_threshold}")

        # Check if GPU is available
        if torch.cuda.is_available():
            print(f"  - Device: CUDA ({torch.cuda.get_device_name(0)})")
            pipeline.to(torch.device("cuda"))
        else:
            print(f"  - Device: CPU")

        print("\n" + "-"*70)
        print("Processing audio in streaming mode...")
        print("-"*70)

        # Process audio file in streaming mode
        chunk_count = 0
        all_speakers = set()

        for output in pipeline.stream(audio_file):
            chunk_count += 1
            chunk_speakers = output.speaker_diarization.labels()
            all_speakers.update(chunk_speakers)

            print(f"\n[Chunk {chunk_count}] Time: {output.segment.start:.1f}s - {output.segment.end:.1f}s")
            print(f"  Speakers in chunk: {len(chunk_speakers)}")
            print(f"  Total speakers so far: {len(all_speakers)}")

            # Show speaker turns in this chunk
            if len(output.speaker_diarization) > 0:
                print(f"  Speaker turns:")
                for turn, _, speaker in output.speaker_diarization.itertracks(yield_label=True):
                    print(f"    {turn.start:6.1f}s - {turn.end:6.1f}s : {speaker}")
            else:
                print(f"  (No speech detected)")

            if output.is_final:
                print(f"\n{'='*70}")
                print("Final Results")
                print("="*70)
                print(f"  Total chunks processed: {chunk_count}")
                print(f"  Total speakers detected: {len(all_speakers)}")
                print(f"  Speakers: {sorted(all_speakers)}")

                print(f"\nFull diarization timeline:")
                for turn, _, speaker in output.cumulative_diarization.itertracks(yield_label=True):
                    print(f"  {turn.start:6.1f}s - {turn.end:6.1f}s : {speaker}")

        print("\n" + "="*70)
        print("Streaming diarization completed successfully!")
        print("="*70)

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_generator_streaming(hf_token: str):
    """Test streaming from a generator (simulated live audio)"""

    print("\n" + "="*70)
    print("Testing Generator-Based Streaming (Simulated Live Audio)")
    print("="*70)

    try:
        # Initialize streaming pipeline
        pipeline = StreamingSpeakerDiarization.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )

        print("Pipeline loaded successfully!")

        # Create a generator that yields audio chunks
        def audio_generator():
            """Simulate streaming audio by generating random chunks"""
            sample_rate = 16000
            chunk_duration = 5.0  # 5 seconds per chunk
            num_chunks = 3

            print(f"\nGenerating {num_chunks} audio chunks ({chunk_duration}s each)...")

            for i in range(num_chunks):
                # Generate random audio (in practice, this would come from mic/stream)
                samples = int(sample_rate * chunk_duration)
                waveform = torch.randn(1, samples) * 0.1  # Random noise
                print(f"  Generated chunk {i+1}/{num_chunks}")
                yield waveform, sample_rate

        print("\nProcessing generated audio stream...")
        print("-"*70)

        chunk_count = 0
        for output in pipeline.stream_from_generator(audio_generator()):
            chunk_count += 1
            print(f"\n[Chunk {chunk_count}] Time: {output.segment.start:.1f}s - {output.segment.end:.1f}s")
            print(f"  Speakers detected: {len(output.speaker_diarization.labels())}")

            if len(output.speaker_diarization) > 0:
                for turn, _, speaker in output.speaker_diarization.itertracks(yield_label=True):
                    print(f"    {turn.start:6.1f}s - {turn.end:6.1f}s : {speaker}")

        print("\n✓ Generator streaming test completed!")
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function"""

    print("="*70)
    print("PyAnnote Streaming Speaker Diarization - Test Suite")
    print("="*70)

    # Get HuggingFace token
    hf_token = get_hf_token()

    if not hf_token:
        print("❌ No HuggingFace token available")
        sys.exit(1)

    # Find test audio file
    test_files = [
        Path(__file__).parent / "tutorials/assets/sample.wav",
        Path(__file__).parent / "tests/data/dev00.wav",
        Path(__file__).parent / "src/pyannote/audio/sample/sample.wav",
    ]

    audio_file = None
    for f in test_files:
        if f.exists():
            audio_file = str(f)
            break

    if not audio_file:
        print("❌ No test audio file found")
        print("\nSearched in:")
        for f in test_files:
            print(f"  - {f}")
        sys.exit(1)

    # Test 1: File-based streaming
    success1 = test_streaming_diarization(audio_file, hf_token)

    # Test 2: Generator-based streaming (optional)
    test_generator = input("\nTest generator-based streaming? (y/n): ").strip().lower()
    success2 = True
    if test_generator == 'y':
        success2 = test_generator_streaming(hf_token)

    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    print(f"  File streaming: {'✓ PASSED' if success1 else '❌ FAILED'}")
    if test_generator == 'y':
        print(f"  Generator streaming: {'✓ PASSED' if success2 else '❌ FAILED'}")
    print("="*70)

    return 0 if (success1 and success2) else 1


if __name__ == "__main__":
    sys.exit(main())
