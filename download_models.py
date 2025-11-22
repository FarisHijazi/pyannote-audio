#!/usr/bin/env python3
"""
Download and cache pyannote models so they can be used without HF token later
"""

import os
import sys
from pathlib import Path

# Add source to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("="*70)
print("PyAnnote Model Downloader")
print("="*70)

# Get token from environment
HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

if not HF_TOKEN:
    print("\n❌ Error: HF_TOKEN environment variable not set")
    print("\nPlease set your HuggingFace token:")
    print("  export HF_TOKEN=your_token_here")
    print("\nGet your token from: https://huggingface.co/settings/tokens")
    sys.exit(1)

print(f"\n✅ Using HF token from environment")

print("\nDownloading models to local cache...")
print("This will allow running without HF token in the future.\n")

try:
    from pyannote.audio import Pipeline

    # Download speaker diarization pipeline (includes all models)
    print("Downloading: pyannote/speaker-diarization-3.1")
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=HF_TOKEN
    )
    print("✅ Speaker diarization pipeline downloaded")

    # Download segmentation model separately to ensure it's cached
    print("\nDownloading: pyannote/segmentation-3.0")
    from pyannote.audio import Model
    segmentation_model = Model.from_pretrained(
        "pyannote/segmentation-3.0",
        token=HF_TOKEN
    )
    print("✅ Segmentation model downloaded")

    # Download embedding model
    print("\nDownloading: pyannote/wespeaker-voxceleb-resnet34-LM")
    embedding_model = Model.from_pretrained(
        "pyannote/wespeaker-voxceleb-resnet34-LM",
        token=HF_TOKEN
    )
    print("✅ Embedding model downloaded")

    print("\n" + "="*70)
    print("✅ All models downloaded successfully!")
    print("="*70)
    print("\nModels are now cached locally.")
    print("You can use the streaming diarization without HF token:")
    print("\n  python test_streaming_diarization.py")
    print("  python demo_streaming_diarization.py")
    print("\nJust press Enter when prompted for token (or leave it empty).")

except Exception as e:
    print(f"\n❌ Error downloading models: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
