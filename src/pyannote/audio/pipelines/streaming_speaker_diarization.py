# The MIT License (MIT)
#
# Copyright (c) 2021-2025 CNRS
# Copyright (c) 2025- pyannoteAI
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Streaming speaker diarization pipeline"""

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Union, Any
import warnings

import numpy as np
import torch
from pyannote.audio import Audio, Inference, Pipeline
from pyannote.audio.core.io import AudioFile
from pyannote.audio.pipelines.speaker_diarization import SpeakerDiarization
from pyannote.audio.pipelines.speaker_verification import PretrainedSpeakerEmbedding
from pyannote.audio.pipelines.utils import get_model
from pyannote.audio.utils.signal import binarize
from pyannote.core import Annotation, Segment, SlidingWindow, SlidingWindowFeature
from scipy.spatial.distance import cdist


@dataclass
class StreamingDiarizeOutput:
    """Output from streaming diarization for a single chunk"""

    # Time range for this chunk
    segment: Segment

    # Speaker diarization for this chunk
    speaker_diarization: Annotation

    # Cumulative diarization from start to end of this chunk
    cumulative_diarization: Annotation

    # Speaker embeddings for speakers in this chunk
    speaker_embeddings: dict[str, np.ndarray] = None

    # Whether this is the final chunk
    is_final: bool = False


class StreamingSpeakerDiarization(SpeakerDiarization):
    """Streaming speaker diarization pipeline

    This pipeline processes audio in chunks and yields diarization results incrementally.
    Unlike the batch SpeakerDiarization pipeline, this can process streaming audio sources
    such as live microphone input, network streams, or large files that should be processed
    incrementally.

    Parameters
    ----------
    chunk_duration : float, optional
        Duration of each audio chunk to process in seconds. Defaults to 5.0.
    overlap_duration : float, optional
        Duration of overlap between consecutive chunks in seconds. Defaults to 1.0.
        This helps maintain continuity across chunk boundaries.
    speaker_threshold : float, optional
        Cosine similarity threshold for matching speakers across chunks.
        Defaults to 0.7. Lower values create more distinct speakers.
    min_speakers : int, optional
        Minimum number of speakers. Defaults to 1.
    max_speakers : int, optional
        Maximum number of speakers. Defaults to None (unlimited).
    **kwargs
        Additional parameters passed to the base SpeakerDiarization pipeline.

    Example
    -------
    >>> from pyannote.audio.pipelines.streaming_speaker_diarization import StreamingSpeakerDiarization
    >>>
    >>> # HF token only needed on first download, then models are cached
    >>> pipeline = StreamingSpeakerDiarization.from_pretrained(
    ...     "pyannote/speaker-diarization-3.1",
    ...     use_auth_token="YOUR_HF_TOKEN"  # Optional if models already cached
    ... )
    >>>
    >>> # Process audio file in streaming mode
    >>> for output in pipeline.stream("audio.wav"):
    ...     print(f"Chunk {output.segment}: {len(output.speaker_diarization.labels())} speakers")
    ...     for turn, _, speaker in output.speaker_diarization.itertracks(yield_label=True):
    ...         print(f"  {turn.start:.1f}s - {turn.end:.1f}s: {speaker}")

    Note
    ----
    After the first run with a valid HuggingFace token, models are cached locally.
    Subsequent runs don't require the token - just pass use_auth_token=None or omit it.
    """

    def __init__(
        self,
        segmentation: Union[str, dict] = None,
        embedding: Union[str, dict] = None,
        chunk_duration: float = 5.0,
        overlap_duration: float = 1.0,
        speaker_threshold: float = 0.7,
        min_speakers: int = 1,
        max_speakers: Optional[int] = None,
        **kwargs
    ):
        super().__init__(
            segmentation=segmentation,
            embedding=embedding,
            **kwargs
        )

        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        self.speaker_threshold = speaker_threshold
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers

        # Speaker registry: maintains known speakers and their embeddings
        self._speaker_registry: dict[str, np.ndarray] = {}
        self._speaker_count = 0
        self._cumulative_diarization = None

    def reset(self):
        """Reset the streaming state"""
        self._speaker_registry = {}
        self._speaker_count = 0
        self._cumulative_diarization = None

    def _get_next_speaker_label(self) -> str:
        """Generate next speaker label"""
        label = f"SPEAKER_{self._speaker_count:02d}"
        self._speaker_count += 1
        return label

    def _match_speaker(self, embedding: np.ndarray) -> Optional[str]:
        """Match an embedding to a known speaker

        Parameters
        ----------
        embedding : np.ndarray
            Speaker embedding to match

        Returns
        -------
        speaker_label : str or None
            Label of matched speaker, or None if no match found
        """
        if not self._speaker_registry:
            return None

        # Compute cosine similarity with all known speakers
        known_embeddings = np.array(list(self._speaker_registry.values()))
        known_labels = list(self._speaker_registry.keys())

        # Reshape embedding for cdist
        embedding = embedding.reshape(1, -1)

        # Compute cosine distance and convert to similarity
        distances = cdist(embedding, known_embeddings, metric='cosine')
        similarities = 1 - distances[0]

        # Find best match
        best_idx = np.argmax(similarities)
        best_similarity = similarities[best_idx]

        if best_similarity >= self.speaker_threshold:
            return known_labels[best_idx]

        return None

    def _update_speaker_registry(self, label: str, embedding: np.ndarray, alpha: float = 0.3):
        """Update speaker registry with new embedding

        Uses exponential moving average to update speaker embeddings.

        Parameters
        ----------
        label : str
            Speaker label
        embedding : np.ndarray
            New speaker embedding
        alpha : float, optional
            Update weight (0 = keep old, 1 = use only new). Defaults to 0.3.
        """
        if label in self._speaker_registry:
            # Update with moving average
            old_embedding = self._speaker_registry[label]
            self._speaker_registry[label] = (1 - alpha) * old_embedding + alpha * embedding
            # Normalize
            self._speaker_registry[label] /= np.linalg.norm(self._speaker_registry[label])
        else:
            # Add new speaker
            self._speaker_registry[label] = embedding / np.linalg.norm(embedding)

    def process_chunk(
        self,
        waveform: torch.Tensor,
        sample_rate: int,
        chunk_start: float,
    ) -> StreamingDiarizeOutput:
        """Process a single audio chunk

        Parameters
        ----------
        waveform : torch.Tensor
            Audio waveform as (channels, samples) tensor
        sample_rate : int
            Sample rate of the audio
        chunk_start : float
            Start time of this chunk in seconds (relative to beginning of stream)

        Returns
        -------
        output : StreamingDiarizeOutput
            Diarization output for this chunk
        """
        # Prepare file dict for processing
        file = {
            "waveform": waveform,
            "sample_rate": sample_rate,
            "uri": f"stream_chunk_{chunk_start:.2f}"
        }

        # Get segmentation
        segmentation: SlidingWindowFeature = self._segmentation(file)

        # Binarize segmentation to get speech regions
        # Use simple threshold-based binarization
        binarized = binarize(
            segmentation,
            onset=0.5,
            offset=0.5
        )

        # Create annotation for speech regions
        chunk_annotation = Annotation(uri=file["uri"])

        # Get embeddings for speech regions
        chunk_embeddings = {}
        local_speaker_map = {}  # Maps local speaker index to global speaker label

        # Convert binarized to speech segments
        # binarized is a SlidingWindowFeature with shape (num_frames, num_classes) or (num_frames,)
        # Find contiguous regions where any class is active
        speech_regions = []

        frames = binarized.data
        sliding_window = binarized.sliding_window

        # Handle both 1D and 2D frames
        if frames.ndim == 1:
            is_speech = frames > 0.5
        else:
            is_speech = np.max(frames, axis=1) > 0.5  # Any class active

        # Ensure 1D boolean array
        is_speech = is_speech.ravel()

        # Find start/end of speech segments
        # Pad with False on both sides to detect boundaries
        padded = np.concatenate(([False], is_speech, [False]))
        changes = np.diff(padded.astype(int))
        starts = np.where(changes == 1)[0]
        ends = np.where(changes == -1)[0]

        for start_idx, end_idx in zip(starts, ends):
            start_time = sliding_window[start_idx].middle
            end_time = sliding_window[end_idx - 1].middle
            speech_regions.append(Segment(start_time, end_time))

        # Extract embeddings for each speech region
        for speech_turn in speech_regions:
            # Skip very short segments
            if speech_turn.duration < 0.5:
                continue

            # Extract embedding for this segment
            try:
                # Extract the actual audio segment
                start_sample = int(speech_turn.start * sample_rate)
                end_sample = int(speech_turn.end * sample_rate)

                # Extract segment from waveform
                if waveform.ndim == 1:
                    segment_audio = waveform[start_sample:end_sample].unsqueeze(0)
                else:
                    segment_audio = waveform[:, start_sample:end_sample]

                # Create input dict for embedding model
                embedding_input = {
                    "waveform": segment_audio,
                    "sample_rate": sample_rate,
                }

                # Get embedding
                embedding = self._embedding(embedding_input)

                # Match to known speaker or create new one
                speaker_label = self._match_speaker(embedding)

                if speaker_label is None:
                    # New speaker
                    if self.max_speakers is None or self._speaker_count < self.max_speakers:
                        speaker_label = self._get_next_speaker_label()
                        self._update_speaker_registry(speaker_label, embedding)
                    else:
                        # Max speakers reached, assign to closest match
                        speaker_label = self._match_speaker(embedding)
                        if speaker_label is None and self._speaker_registry:
                            # Force assignment to most similar speaker
                            known_embeddings = np.array(list(self._speaker_registry.values()))
                            known_labels = list(self._speaker_registry.keys())
                            distances = cdist(embedding.reshape(1, -1), known_embeddings, metric='cosine')
                            speaker_label = known_labels[np.argmin(distances[0])]
                        elif speaker_label is None:
                            # Shouldn't happen, but create first speaker if needed
                            speaker_label = self._get_next_speaker_label()
                            self._update_speaker_registry(speaker_label, embedding)
                else:
                    # Update existing speaker embedding
                    self._update_speaker_registry(speaker_label, embedding)

                # Add to chunk annotation (adjust time to be relative to chunk start)
                global_turn = Segment(
                    chunk_start + speech_turn.start,
                    chunk_start + speech_turn.end
                )
                chunk_annotation[global_turn] = speaker_label
                chunk_embeddings[speaker_label] = embedding

            except Exception as e:
                warnings.warn(f"Failed to process segment {speech_turn}: {e}")
                continue

        # Update cumulative diarization
        if self._cumulative_diarization is None:
            self._cumulative_diarization = Annotation(uri="stream")

        # Add chunk results to cumulative diarization
        for turn, _, label in chunk_annotation.itertracks(yield_label=True):
            self._cumulative_diarization[turn] = label

        # Create output
        chunk_segment = Segment(chunk_start, chunk_start + self.chunk_duration)

        return StreamingDiarizeOutput(
            segment=chunk_segment,
            speaker_diarization=chunk_annotation,
            cumulative_diarization=self._cumulative_diarization.copy(),
            speaker_embeddings=chunk_embeddings,
            is_final=False
        )

    def stream(
        self,
        audio: AudioFile,
        chunk_duration: Optional[float] = None,
        overlap_duration: Optional[float] = None,
    ) -> Iterator[StreamingDiarizeOutput]:
        """Stream diarization results for an audio file

        Parameters
        ----------
        audio : AudioFile
            Audio file path, waveform, or file-like object
        chunk_duration : float, optional
            Override default chunk duration
        overlap_duration : float, optional
            Override default overlap duration

        Yields
        ------
        output : StreamingDiarizeOutput
            Diarization output for each chunk
        """
        # Reset state
        self.reset()

        # Use instance defaults if not specified
        chunk_duration = chunk_duration or self.chunk_duration
        overlap_duration = overlap_duration or self.overlap_duration

        # Load audio
        audio_loader = Audio(sample_rate=self.segmentation.model.audio.sample_rate, mono=True)

        # Convert audio to file dict if it's a path
        if isinstance(audio, (str, Path)):
            file = {"audio": audio}
        else:
            file = audio

        # Get full waveform
        waveform, sample_rate = audio_loader(file)

        # Calculate chunk parameters
        chunk_samples = int(chunk_duration * sample_rate)
        overlap_samples = int(overlap_duration * sample_rate)
        step_samples = chunk_samples - overlap_samples

        # Get total duration
        total_samples = waveform.shape[-1]
        total_duration = total_samples / sample_rate

        # Process chunks
        chunk_start = 0.0
        sample_start = 0

        while sample_start < total_samples:
            # Get chunk waveform
            sample_end = min(sample_start + chunk_samples, total_samples)
            chunk_waveform = waveform[..., sample_start:sample_end]

            # Pad if necessary (last chunk might be shorter)
            if chunk_waveform.shape[-1] < chunk_samples:
                padding = chunk_samples - chunk_waveform.shape[-1]
                chunk_waveform = torch.nn.functional.pad(chunk_waveform, (0, padding))

            # Process chunk
            output = self.process_chunk(chunk_waveform, sample_rate, chunk_start)

            # Check if this is the last chunk
            sample_start += step_samples
            chunk_start += (step_samples / sample_rate)

            if sample_start >= total_samples:
                output.is_final = True

            yield output

    def stream_from_generator(
        self,
        audio_generator: Iterator[tuple[torch.Tensor, int]],
        chunk_duration: Optional[float] = None,
    ) -> Iterator[StreamingDiarizeOutput]:
        """Stream diarization results from an audio generator

        This method allows processing truly streaming audio sources where the
        audio arrives in chunks over time (e.g., from a microphone or network stream).

        Parameters
        ----------
        audio_generator : Iterator[tuple[torch.Tensor, int]]
            Iterator yielding (waveform_chunk, sample_rate) tuples.
            Each waveform_chunk should be a torch.Tensor of shape (channels, samples).
        chunk_duration : float, optional
            Override default chunk duration

        Yields
        ------
        output : StreamingDiarizeOutput
            Diarization output for each chunk

        Example
        -------
        >>> def audio_chunks():
        ...     # Simulate streaming audio
        ...     for i in range(10):
        ...         waveform = torch.randn(1, 16000 * 5)  # 5 seconds at 16kHz
        ...         yield waveform, 16000
        >>>
        >>> for output in pipeline.stream_from_generator(audio_chunks()):
        ...     print(f"Chunk {output.segment}: {len(output.speaker_diarization.labels())} speakers")
        """
        # Reset state
        self.reset()

        # Use instance default if not specified
        chunk_duration = chunk_duration or self.chunk_duration

        chunk_start = 0.0

        for chunk_waveform, sample_rate in audio_generator:
            # Process chunk
            output = self.process_chunk(chunk_waveform, sample_rate, chunk_start)

            # Update chunk start for next iteration
            chunk_duration_actual = chunk_waveform.shape[-1] / sample_rate
            chunk_start += chunk_duration_actual

            yield output


# For backward compatibility and easier imports
__all__ = ['StreamingSpeakerDiarization', 'StreamingDiarizeOutput']
