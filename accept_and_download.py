#!/usr/bin/env python3
"""
Accept model terms and download models
"""

import os
import sys
from pathlib import Path

# Add source to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

print("="*70)
print("PyAnnote Model Downloader - Accept & Download")
print("="*70)

# Try to use HF API to accept terms
try:
    from huggingface_hub import HfApi

    api = HfApi(token=HF_TOKEN)

    # Try to access the repo - this might work if terms are already accepted
    print("\n1️⃣ Checking repository access...")

    try:
        repo_info = api.repo_info("pyannote/speaker-diarization-3.1", token=HF_TOKEN)
        print("✅ Repository accessible!")
    except Exception as e:
        print(f"❌ Cannot access repository: {e}")
        print("\n" + "="*70)
        print("MANUAL ACTION REQUIRED:")
        print("="*70)
        print("\n1. Visit: https://huggingface.co/pyannote/speaker-diarization-3.1")
        print("2. Log in with your HuggingFace account")
        print("3. Click 'Agree and access repository'")
        print("\n4. Then go to: https://huggingface.co/settings/tokens")
        print("5. Find your token and click 'Edit'")
        print("6. Enable 'Read access to contents of all public gated repos you can access'")
        print("7. Save the token")
        print("\n8. Then run this script again")
        sys.exit(1)

except ImportError:
    print("❌ huggingface_hub not installed")
    sys.exit(1)

# Now try downloading
print("\n2️⃣ Downloading models...")

try:
    from pyannote.audio import Pipeline, Model

    # Download speaker diarization pipeline
    print("\nDownloading: pyannote/speaker-diarization-3.1")
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=HF_TOKEN
    )
    print("✅ Speaker diarization pipeline downloaded")

    # Download segmentation model
    print("\nDownloading: pyannote/segmentation-3.0")
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
    print("✅ ALL MODELS DOWNLOADED SUCCESSFULLY!")
    print("="*70)
    print("\nYou can now run:")
    print("  python realtime_server.py")

except Exception as e:
    print(f"\n❌ Error downloading models: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
