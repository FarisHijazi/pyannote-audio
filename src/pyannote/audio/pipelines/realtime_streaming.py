#!/usr/bin/env python3
"""
Real-time streaming speaker diarization
Processes live audio input and outputs results in real-time
"""

import asyncio
import numpy as np
import torch
from typing import Optional, AsyncIterator
from collections import deque
import time

from pyannote.audio.pipelines.streaming_speaker_diarization import (
    StreamingSpeakerDiarization,
    StreamingDiarizeOutput
)
from pyannote.core import Segment


class RealTimeStreamingDiarization:
    """
    Real-time streaming speaker diarization

    Processes audio as it arrives from a live source (microphone, stream)
    and yields diarization results with minimal latency.

    Parameters
    ----------
    sample_rate : int
        Audio sample rate (default: 16000)
    chunk_duration : float
        Duration of processing window in seconds (default: 5.0)
    min_chunk_duration : float
        Minimum audio needed before processing (default: 2.0)
    latency_mode : str
        'low' (faster, less accurate) or 'high' (slower, more accurate)
        Default: 'low'

    Example
    -------
    >>> diarizer = RealTimeStreamingDiarization()
    >>> await diarizer.start()
    >>>
    >>> # Feed audio chunks as they arrive
    >>> async for result in diarizer.process_audio_stream(audio_chunks):
    >>>     print(f"{result.time:.1f}s: {result.speaker} speaking")
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_duration: float = 5.0,
        min_chunk_duration: float = 2.0,
        latency_mode: str = 'low',
        hf_token: Optional[str] = None
    ):
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.min_chunk_duration = min_chunk_duration
        self.latency_mode = latency_mode
        self.hf_token = hf_token

        # Audio buffer
        self.audio_buffer = deque()
        self.buffer_duration = 0.0

        # Processing state
        self.pipeline: Optional[StreamingSpeakerDiarization] = None
        self.is_started = False
        self.total_processed = 0.0
        self.last_process_time = 0.0

    async def start(self):
        """Initialize the pipeline"""
        if self.is_started:
            return

        # Load streaming pipeline
        # Pass model names directly
        from pyannote.audio.pipelines.utils import get_model

        self.pipeline = StreamingSpeakerDiarization(
            segmentation="pyannote/segmentation-3.0",
            embedding="pyannote/wespeaker-voxceleb-resnet34-LM",
            chunk_duration=self.chunk_duration,
            overlap_duration=1.0,
        )
        # Instantiate with no params - models should be cached
        self.pipeline.instantiate({})

        # Configure for low latency
        if self.latency_mode == 'low':
            self.pipeline.chunk_duration = 3.0
            self.pipeline.overlap_duration = 0.5
        else:
            self.pipeline.chunk_duration = 5.0
            self.pipeline.overlap_duration = 1.0

        # Move to GPU if available
        if torch.cuda.is_available():
            self.pipeline.to(torch.device("cuda"))

        self.is_started = True

    async def stop(self):
        """Stop and reset"""
        self.reset()
        self.is_started = False

    def reset(self):
        """Reset the audio buffer and processing state"""
        self.audio_buffer.clear()
        self.buffer_duration = 0.0
        self.total_processed = 0.0
        self.last_process_time = 0.0

    def add_audio(self, audio_chunk: np.ndarray):
        """
        Add audio chunk to buffer

        Parameters
        ----------
        audio_chunk : np.ndarray
            Audio samples (1D array)
        """
        self.audio_buffer.append(audio_chunk)
        self.buffer_duration += len(audio_chunk) / self.sample_rate

    def get_buffered_audio(self, duration: float) -> Optional[np.ndarray]:
        """
        Get buffered audio of specified duration

        Returns None if not enough audio buffered
        """
        if self.buffer_duration < duration:
            return None

        # Calculate how many samples we need
        target_samples = int(duration * self.sample_rate)

        # Collect chunks
        chunks = []
        samples_collected = 0

        while samples_collected < target_samples and self.audio_buffer:
            chunk = self.audio_buffer.popleft()
            chunks.append(chunk)
            samples_collected += len(chunk)
            self.buffer_duration -= len(chunk) / self.sample_rate

        # Concatenate and trim to exact duration
        audio = np.concatenate(chunks)[:target_samples]

        return audio

    async def process_audio_stream(
        self,
        audio_generator: AsyncIterator[np.ndarray]
    ) -> AsyncIterator[dict]:
        """
        Process real-time audio stream

        Parameters
        ----------
        audio_generator : AsyncIterator[np.ndarray]
            Async generator yielding audio chunks

        Yields
        ------
        dict with keys:
            - time: timestamp in seconds
            - speaker: speaker label
            - start: segment start time
            - end: segment end time
            - confidence: speaker confidence (if available)
        """
        if not self.is_started:
            await self.start()

        async for audio_chunk in audio_generator:
            # Add to buffer
            self.add_audio(audio_chunk)

            # Process if we have enough audio
            if self.buffer_duration >= self.min_chunk_duration:
                # Get audio for processing
                audio = self.get_buffered_audio(self.chunk_duration)

                if audio is not None:
                    # Convert to tensor
                    waveform = torch.from_numpy(audio).float().unsqueeze(0)

                    # Process chunk
                    output = self.pipeline.process_chunk(
                        waveform,
                        self.sample_rate,
                        self.total_processed
                    )

                    # Yield results
                    for turn, _, speaker in output.speaker_diarization.itertracks(yield_label=True):
                        yield {
                            'time': turn.start,
                            'speaker': speaker,
                            'start': turn.start,
                            'end': turn.end,
                            'confidence': 1.0  # TODO: add actual confidence
                        }

                    self.total_processed += self.chunk_duration
                    self.last_process_time = time.time()

    async def process_microphone(self) -> AsyncIterator[dict]:
        """
        Process audio directly from microphone

        Yields speaker diarization results in real-time
        """
        try:
            import sounddevice as sd
        except ImportError:
            raise ImportError("sounddevice required for microphone input: pip install sounddevice")

        if not self.is_started:
            await self.start()

        # Audio queue for microphone callback
        audio_queue = asyncio.Queue()

        def audio_callback(indata, frames, time_info, status):
            """Callback for audio input"""
            if status:
                print(f"Audio status: {status}")
            # Convert to mono if stereo
            audio = indata[:, 0] if len(indata.shape) > 1 else indata
            audio_queue.put_nowait(audio.copy())

        # Start audio stream
        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            callback=audio_callback,
            blocksize=int(self.sample_rate * 0.1)  # 100ms chunks
        )

        with stream:
            print("🎤 Microphone recording started...")
            print("Speak now! Results will appear with a small delay.")

            try:
                while True:
                    # Get audio from queue
                    audio_chunk = await audio_queue.get()

                    # Add to buffer
                    self.add_audio(audio_chunk)

                    # Process if we have enough audio
                    if self.buffer_duration >= self.min_chunk_duration:
                        audio = self.get_buffered_audio(self.chunk_duration)

                        if audio is not None:
                            # Convert to tensor
                            waveform = torch.from_numpy(audio).float().unsqueeze(0)

                            # Process chunk
                            output = self.pipeline.process_chunk(
                                waveform,
                                self.sample_rate,
                                self.total_processed
                            )

                            # Yield results
                            for turn, _, speaker in output.speaker_diarization.itertracks(yield_label=True):
                                yield {
                                    'time': turn.start,
                                    'speaker': speaker,
                                    'start': turn.start,
                                    'end': turn.end,
                                    'confidence': 1.0
                                }

                            self.total_processed += self.chunk_duration

            except KeyboardInterrupt:
                print("\n🛑 Stopped recording")


# Simpler synchronous version for testing
class SimpleRealTimeStreaming:
    """Simple synchronous real-time streaming for testing"""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.buffer = []
        self.buffer_size = sample_rate * 5  # 5 seconds

    def add_audio(self, audio: np.ndarray):
        """Add audio chunk"""
        self.buffer.extend(audio.tolist())

    def should_process(self) -> bool:
        """Check if we have enough audio to process"""
        return len(self.buffer) >= self.buffer_size

    def get_audio_chunk(self) -> np.ndarray:
        """Get audio chunk for processing"""
        chunk = np.array(self.buffer[:self.buffer_size])
        self.buffer = self.buffer[self.buffer_size // 2:]  # 50% overlap
        return chunk


if __name__ == "__main__":
    import os

    print("="*70)
    print("Real-Time Streaming Diarization Test")
    print("="*70)

    # Example: Process from microphone
    async def test_microphone():
        hf_token = os.environ.get("HF_TOKEN")

        diarizer = RealTimeStreamingDiarization(
            latency_mode='low',
            hf_token=hf_token
        )

        print("\nStarting real-time diarization from microphone...")
        print("Press Ctrl+C to stop.\n")

        async for result in diarizer.process_microphone():
            print(f"[{result['time']:6.1f}s] {result['speaker']}: "
                  f"{result['start']:.1f}s - {result['end']:.1f}s")

    # Run test
    try:
        asyncio.run(test_microphone())
    except KeyboardInterrupt:
        print("\nStopped.")
