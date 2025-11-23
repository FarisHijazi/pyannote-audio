#!/usr/bin/env python3
"""
Simple web demo for PyAnnote Streaming Speaker Diarization
Shows the concept even without full installation
"""

import gradio as gr
import time
import random

def mock_stream_diarize(audio_file, chunk_duration, overlap_duration, speaker_threshold):
    """
    Mock streaming diarization demo (for when pyannote isn't fully installed)
    """

    if not audio_file:
        yield ("⚠️  Please upload an audio file", "", 0)
        return

    # Simulate loading
    yield ("📥 Loading pipeline...", "", 0.1)
    time.sleep(1)

    yield (
        f"✅ Pipeline loaded! (DEMO MODE)\n"
        f"Chunk duration: {chunk_duration}s\n"
        f"Overlap: {overlap_duration}s\n"
        f"Speaker threshold: {speaker_threshold}\n\n"
        f"🎵 Processing audio...\n\n"
        f"⚠️  NOTE: This is a mock demo showing the interface.\n"
        f"Install pyannote-audio for real processing!",
        "",
        0.2
    )
    time.sleep(0.5)

    # Simulate processing chunks
    num_chunks = 8
    speakers = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]
    results_text = ""

    for chunk_num in range(1, num_chunks + 1):
        # Simulate chunk processing
        start_time = (chunk_num - 1) * (chunk_duration - overlap_duration)
        end_time = start_time + chunk_duration

        chunk_result = f"\n{'='*60}\n"
        chunk_result += f"Chunk {chunk_num}: {start_time:.1f}s - {end_time:.1f}s\n"
        chunk_result += f"{'='*60}\n"

        # Random speakers for demo
        num_speakers_in_chunk = random.randint(1, 3)
        chunk_speakers = random.sample(speakers, num_speakers_in_chunk)

        chunk_result += f"Speakers in chunk: {len(chunk_speakers)}\n"
        chunk_result += f"Total speakers: {len(speakers)}\n\n"

        # Generate mock segments
        time_in_chunk = start_time
        for i in range(random.randint(2, 5)):
            duration = random.uniform(0.5, 2.0)
            speaker = random.choice(chunk_speakers)
            chunk_result += f"  {time_in_chunk:6.1f}s - {time_in_chunk + duration:6.1f}s : {speaker}\n"
            time_in_chunk += duration + random.uniform(0.1, 0.5)

        results_text += chunk_result

        # Update status
        status = (
            f"🔄 Processing... (DEMO MODE)\n"
            f"Chunk: {chunk_num}/{num_chunks}\n"
            f"Time: {end_time:.1f}s\n"
            f"Speakers found: {len(speakers)}"
        )

        progress = 0.2 + (chunk_num / num_chunks) * 0.7

        yield (status, results_text, progress)
        time.sleep(0.5)

    # Final summary
    summary = f"\n{'='*60}\n"
    summary += f"✅ COMPLETE! (DEMO MODE)\n"
    summary += f"{'='*60}\n"
    summary += f"Total chunks: {num_chunks}\n"
    summary += f"Total speakers: {len(speakers)}\n"
    summary += f"Speakers: {sorted(speakers)}\n"
    summary += f"{'='*60}\n\n"

    summary += "⚠️  This was a mock demo.\n"
    summary += "Install pyannote-audio for real streaming diarization:\n"
    summary += "  pip install -e .\n\n"
    summary += "Then run: python demo_streaming_diarization.py\n"

    results_text += summary

    yield (
        f"✅ Processing complete! (DEMO)\n"
        f"Chunks: {num_chunks}\n"
        f"Speakers: {len(speakers)}",
        results_text,
        1.0
    )


# Create Gradio interface
def create_demo():
    """Create Gradio web interface"""

    with gr.Blocks(title="PyAnnote Streaming Diarization Demo") as demo:
        gr.Markdown("""
        # 🎙️ PyAnnote Streaming Speaker Diarization Demo

        This demo showcases the new **streaming speaker diarization** feature for pyannote-audio.

        ⚠️  **DEMO MODE**: This is a simplified demo showing the interface concept.
        For real audio processing, install pyannote-audio and use the full version.

        ### About the Streaming Feature:
        - ✅ Processes audio in real-time chunks
        - ✅ Memory-efficient (one chunk at a time)
        - ✅ Tracks speakers across chunks
        - ✅ Supports live audio streams
        """)

        with gr.Row():
            with gr.Column():
                audio_input = gr.Audio(
                    label="Upload Audio File (Demo - any file works)",
                    type="filepath",
                    sources=["upload"]
                )

                with gr.Accordion("Settings", open=True):
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

                process_btn = gr.Button("🎵 Process Audio (Demo)", variant="primary")

                gr.Markdown("""
                ### How Streaming Works:
                1. **Chunking**: Audio split into overlapping chunks
                2. **Processing**: Each chunk analyzed for speakers
                3. **Tracking**: Speakers matched across chunks using embeddings
                4. **Output**: Real-time results as each chunk completes

                ### Key Benefits:
                - 📉 Lower memory usage
                - ⚡ Real-time processing
                - 🎤 Live audio support
                - 📊 Incremental results
                """)

            with gr.Column():
                status_output = gr.Textbox(
                    label="Status",
                    lines=10,
                    interactive=False
                )

                results_output = gr.Textbox(
                    label="Diarization Results",
                    lines=20,
                    interactive=False
                )

        # Connect processing
        process_btn.click(
            fn=mock_stream_diarize,
            inputs=[
                audio_input,
                chunk_duration,
                overlap_duration,
                speaker_threshold
            ],
            outputs=[status_output, results_output]
        )

        gr.Markdown("""
        ---

        ### Installation & Real Usage

        To use the real streaming diarization:

        ```bash
        # Install pyannote-audio
        pip install -e .

        # Set your HuggingFace token
        export HF_TOKEN=your_token_here

        # Run the full demo
        python demo_streaming_diarization.py
        ```

        **Get HuggingFace Token**: [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)

        **Accept Model Terms**:
        - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
        - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)

        ### GitHub Repository

        **Feature Branch**: [claude/add-diarization-streaming](https://github.com/FarisHijazi/pyannote-audio/tree/claude/add-diarization-streaming-01GiQsparjtXgF3JWYRz9ZVe)

        ### Files Added:
        - `src/pyannote/audio/pipelines/streaming_speaker_diarization.py` - Main implementation
        - `test_streaming_diarization.py` - Test script
        - `demo_streaming_diarization.py` - Full demo (requires installation)
        - `demo_simple.py` - This simplified demo
        """)

    return demo


if __name__ == "__main__":
    print("="*70)
    print("PyAnnote Streaming Diarization - Simple Demo")
    print("="*70)
    print("\n⚠️  Running in DEMO MODE")
    print("This shows the interface concept with mock data.")
    print("\nFor real processing, install pyannote-audio and run:")
    print("  python demo_streaming_diarization.py\n")

    demo = create_demo()

    print("="*70)
    print("Launching web interface...")
    print("="*70)

    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
