#!/usr/bin/env python3
"""
Web demo for PyAnnote Streaming Speaker Diarization
Hosts a Gradio interface to test the streaming feature
"""

import os
import sys
from pathlib import Path
import tempfile
import warnings

# Add source to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import gradio as gr
import torch

# Check if pyannote is installed
try:
    from pyannote.audio.pipelines.streaming_speaker_diarization import StreamingSpeakerDiarization
    PYANNOTE_AVAILABLE = True
except ImportError as e:
    PYANNOTE_AVAILABLE = False
    IMPORT_ERROR = str(e)


def get_hf_token():
    """Get HuggingFace token from environment"""
    return os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")


def stream_diarize(audio_file, hf_token, chunk_duration, overlap_duration, speaker_threshold):
    """
    Process audio file with streaming diarization

    Parameters
    ----------
    audio_file : str
        Path to uploaded audio file
    hf_token : str
        HuggingFace API token
    chunk_duration : float
        Duration of each chunk in seconds
    overlap_duration : float
        Overlap between chunks in seconds
    speaker_threshold : float
        Similarity threshold for matching speakers

    Yields
    ------
    tuple
        (status_text, results_text, progress)
    """

    if not PYANNOTE_AVAILABLE:
        yield (
            f"❌ Error: pyannote.audio not installed\n\n{IMPORT_ERROR}\n\nPlease run: pip install -e .",
            "",
            0
        )
        return

    if not audio_file:
        yield ("⚠️  Please upload an audio file", "", 0)
        return

    if not hf_token:
        hf_token = get_hf_token()
        # Token can be None if models are cached

    try:
        # Initialize pipeline
        yield ("📥 Loading pipeline...", "", 0)

        pipeline = StreamingSpeakerDiarization.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )

        # Configure parameters
        pipeline.chunk_duration = chunk_duration
        pipeline.overlap_duration = overlap_duration
        pipeline.speaker_threshold = speaker_threshold

        # Check for GPU
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            pipeline.to(torch.device("cuda"))

        yield (
            f"✅ Pipeline loaded!\n"
            f"Device: {device}\n"
            f"Chunk duration: {chunk_duration}s\n"
            f"Overlap: {overlap_duration}s\n"
            f"Speaker threshold: {speaker_threshold}\n\n"
            f"🎵 Processing audio...",
            "",
            0.1
        )

        # Process audio in streaming mode
        chunk_count = 0
        all_speakers = set()
        results_text = ""

        for output in pipeline.stream(audio_file):
            chunk_count += 1
            chunk_speakers = output.speaker_diarization.labels()
            all_speakers.update(chunk_speakers)

            # Build results text
            chunk_result = f"\n{'='*60}\n"
            chunk_result += f"Chunk {chunk_count}: {output.segment.start:.1f}s - {output.segment.end:.1f}s\n"
            chunk_result += f"{'='*60}\n"

            if len(output.speaker_diarization) > 0:
                chunk_result += f"Speakers in chunk: {len(chunk_speakers)}\n"
                chunk_result += f"Total speakers: {len(all_speakers)}\n\n"

                for turn, _, speaker in output.speaker_diarization.itertracks(yield_label=True):
                    chunk_result += f"  {turn.start:6.1f}s - {turn.end:6.1f}s : {speaker}\n"
            else:
                chunk_result += "  (No speech detected)\n"

            results_text += chunk_result

            # Update status
            status = (
                f"🔄 Processing...\n"
                f"Chunk: {chunk_count}\n"
                f"Time: {output.segment.end:.1f}s\n"
                f"Speakers found: {len(all_speakers)}"
            )

            # Calculate progress (estimate)
            progress = min(0.9, 0.1 + (chunk_count * 0.05))

            yield (status, results_text, progress)

            if output.is_final:
                # Final summary
                summary = f"\n{'='*60}\n"
                summary += f"✅ COMPLETE!\n"
                summary += f"{'='*60}\n"
                summary += f"Total chunks: {chunk_count}\n"
                summary += f"Total speakers: {len(all_speakers)}\n"
                summary += f"Speakers: {sorted(all_speakers)}\n"
                summary += f"{'='*60}\n\n"

                summary += "Full Timeline:\n"
                summary += "-" * 60 + "\n"
                for turn, _, speaker in output.cumulative_diarization.itertracks(yield_label=True):
                    summary += f"{turn.start:6.1f}s - {turn.end:6.1f}s : {speaker}\n"

                results_text += summary

                yield (
                    f"✅ Processing complete!\n"
                    f"Chunks: {chunk_count}\n"
                    f"Speakers: {len(all_speakers)}",
                    results_text,
                    1.0
                )

    except Exception as e:
        yield (
            f"❌ Error during processing:\n\n{str(e)}\n\nCheck console for full traceback.",
            results_text if 'results_text' in locals() else "",
            0
        )
        import traceback
        traceback.print_exc()


# Create Gradio interface
def create_demo():
    """Create Gradio web interface"""

    with gr.Blocks(title="PyAnnote Streaming Diarization") as demo:
        gr.Markdown("""
        # 🎙️ PyAnnote Streaming Speaker Diarization Demo

        This demo showcases the new **streaming speaker diarization** feature for pyannote-audio.

        Upload an audio file to see real-time speaker diarization with chunk-by-chunk processing!

        ### Setup Requirements (First Time Only):
        1. **HuggingFace Token**: Get from [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
        2. **Accept Terms**:
           - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
           - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)

        **Note**: After first download, models are cached locally. No token needed for subsequent runs!
        """)

        with gr.Row():
            with gr.Column():
                audio_input = gr.Audio(
                    label="Upload Audio File",
                    type="filepath",
                    sources=["upload", "microphone"]
                )

                hf_token_input = gr.Textbox(
                    label="HuggingFace Token (optional if set in environment)",
                    type="password",
                    placeholder="hf_..."
                )

                with gr.Accordion("Advanced Settings", open=False):
                    chunk_duration = gr.Slider(
                        minimum=1.0,
                        maximum=30.0,
                        value=5.0,
                        step=0.5,
                        label="Chunk Duration (seconds)"
                    )

                    overlap_duration = gr.Slider(
                        minimum=0.0,
                        maximum=5.0,
                        value=1.0,
                        step=0.25,
                        label="Overlap Duration (seconds)"
                    )

                    speaker_threshold = gr.Slider(
                        minimum=0.5,
                        maximum=0.95,
                        value=0.75,
                        step=0.05,
                        label="Speaker Matching Threshold"
                    )

                process_btn = gr.Button("🎵 Process Audio", variant="primary")

                gr.Markdown("""
                ### How it works:
                - Audio is processed in **chunks** (default 5s with 1s overlap)
                - Speakers are tracked across chunks using **embeddings**
                - Results are yielded in **real-time** as each chunk completes
                - Memory-efficient: only one chunk in memory at a time
                """)

            with gr.Column():
                status_output = gr.Textbox(
                    label="Status",
                    lines=8,
                    interactive=False
                )

                progress_output = gr.Progress()

                results_output = gr.Textbox(
                    label="Diarization Results",
                    lines=20,
                    interactive=False
                )

        # Connect processing
        process_btn.click(
            fn=stream_diarize,
            inputs=[
                audio_input,
                hf_token_input,
                chunk_duration,
                overlap_duration,
                speaker_threshold
            ],
            outputs=[status_output, results_output, progress_output]
        )

        gr.Markdown("""
        ---

        ### About this Feature

        This is a **new streaming capability** for pyannote-audio that enables:
        - ✅ Real-time processing of audio streams
        - ✅ Incremental diarization of large files
        - ✅ Memory-efficient chunk-based processing
        - ✅ Live audio input support (microphone, network streams)

        **GitHub**: [pyannote-audio streaming feature](https://github.com/FarisHijazi/pyannote-audio/tree/claude/add-diarization-streaming-01GiQsparjtXgF3JWYRz9ZVe)
        """)

    return demo


if __name__ == "__main__":
    print("="*70)
    print("PyAnnote Streaming Speaker Diarization - Web Demo")
    print("="*70)

    if not PYANNOTE_AVAILABLE:
        print(f"\n⚠️  Warning: pyannote.audio not fully installed")
        print(f"Error: {IMPORT_ERROR}")
        print("\nThe web interface will still launch, but processing will fail.")
        print("To fix: pip install -e .")

    # Check for HF token
    token = get_hf_token()
    if token:
        print(f"\n✅ HuggingFace token found in environment")
    else:
        print(f"\n⚠️  No HuggingFace token in environment")
        print("You'll need to enter it in the web interface")

    # Create and launch demo
    demo = create_demo()

    print("\n" + "="*70)
    print("Launching web interface...")
    print("="*70)

    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,  # We'll use localtunnel/ngrok separately
        show_error=True
    )
