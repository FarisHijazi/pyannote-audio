#!/usr/bin/env python3
"""
Performance benchmarks for real-time streaming (no models required)
Tests audio buffering, tensor conversion, and WebSocket message handling
"""

import time
import numpy as np
import torch
import json
import asyncio
from collections import deque
import sys
from pathlib import Path

# Add source to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("=" * 80)
print("REAL-TIME STREAMING PERFORMANCE BENCHMARKS")
print("=" * 80)
print("\nGPU:", "RTX 3090" if torch.cuda.is_available() else "Not available")
print("CUDA:", torch.version.cuda if torch.cuda.is_available() else "N/A")
print()

# Import our implementation
from pyannote.audio.pipelines.realtime_streaming import RealTimeStreamingDiarization

def measure_time(func, *args, **kwargs):
    """Measure execution time"""
    start = time.perf_counter()
    result = func(*args, **kwargs)
    end = time.perf_counter()
    return result, (end - start) * 1000  # Return result and time in ms


# Test 1: Audio Buffer Performance
print("=" * 80)
print("[Test 1] Audio Buffer Performance")
print("=" * 80)

diarizer = RealTimeStreamingDiarization(sample_rate=16000)

# Test adding chunks
chunk_times = []
for i in range(100):
    chunk = np.random.randn(1600).astype(np.float32)  # 0.1s chunk
    _, time_ms = measure_time(diarizer.add_audio, chunk)
    chunk_times.append(time_ms)

print(f"✅ Add audio chunk (100 iterations):")
print(f"   Average: {np.mean(chunk_times):.4f} ms")
print(f"   Min: {np.min(chunk_times):.4f} ms")
print(f"   Max: {np.max(chunk_times):.4f} ms")
print(f"   Std dev: {np.std(chunk_times):.4f} ms")

# Test retrieving buffered audio
diarizer.reset()
for _ in range(50):  # Add 5 seconds of audio
    diarizer.add_audio(np.random.randn(1600).astype(np.float32))

_, retrieve_time = measure_time(diarizer.get_buffered_audio, 1.0)
print(f"\n✅ Retrieve 1s buffered audio: {retrieve_time:.4f} ms")


# Test 2: Numpy to Tensor Conversion (GPU vs CPU)
print("\n" + "=" * 80)
print("[Test 2] Numpy → Tensor Conversion Performance")
print("=" * 80)

audio_sizes = [16000, 48000, 80000, 160000]  # 1s, 3s, 5s, 10s at 16kHz

for size in audio_sizes:
    audio_np = np.random.randn(size).astype(np.float32)

    # CPU conversion
    _, cpu_time = measure_time(torch.from_numpy, audio_np)

    # GPU conversion (if available)
    if torch.cuda.is_available():
        def to_cuda():
            return torch.from_numpy(audio_np).float().cuda()
        _, gpu_time = measure_time(to_cuda)
        print(f"✅ {size:6d} samples ({size/16000:.1f}s): CPU {cpu_time:.4f} ms | GPU {gpu_time:.4f} ms")
    else:
        print(f"✅ {size:6d} samples ({size/16000:.1f}s): CPU {cpu_time:.4f} ms")


# Test 3: WebSocket Message Serialization
print("\n" + "=" * 80)
print("[Test 3] WebSocket Message Serialization Performance")
print("=" * 80)

# Test audio message serialization
audio_chunk = np.random.randn(4096).astype(np.float32)
audio_list = audio_chunk.tolist()

_, serialize_time = measure_time(
    json.dumps,
    {'type': 'audio', 'audio': audio_list}
)
print(f"✅ Serialize audio message (4096 samples): {serialize_time:.4f} ms")

# Test result message serialization
result_msg = {
    'type': 'result',
    'speaker': 'SPEAKER_00',
    'start': 1.5,
    'end': 3.2,
    'time': 2.0
}
_, result_time = measure_time(json.dumps, result_msg)
print(f"✅ Serialize result message: {result_time:.4f} ms")

# Test deserialization
msg_str = json.dumps({'type': 'audio', 'audio': audio_list})
_, deserialize_time = measure_time(json.loads, msg_str)
print(f"✅ Deserialize audio message: {deserialize_time:.4f} ms")


# Test 4: Memory Usage
print("\n" + "=" * 80)
print("[Test 4] Memory Usage")
print("=" * 80)

import sys

# Audio buffer memory
diarizer = RealTimeStreamingDiarization()
for _ in range(100):  # 10 seconds of audio
    diarizer.add_audio(np.random.randn(1600).astype(np.float32))

buffer_mem = sys.getsizeof(diarizer.audio_buffer)
total_audio_mem = sum(sys.getsizeof(chunk) for chunk in diarizer.audio_buffer)
print(f"✅ Audio buffer overhead: {buffer_mem / 1024:.2f} KB")
print(f"✅ Total audio data: {total_audio_mem / 1024:.2f} KB")
print(f"✅ Total memory: {(buffer_mem + total_audio_mem) / 1024:.2f} KB for 10s audio")


# Test 5: Tensor Operations on GPU
if torch.cuda.is_available():
    print("\n" + "=" * 80)
    print("[Test 5] GPU Tensor Operations")
    print("=" * 80)

    # Test tensor creation and transfer
    audio = np.random.randn(80000).astype(np.float32)  # 5s

    _, cpu_tensor_time = measure_time(
        lambda: torch.from_numpy(audio).float()
    )
    print(f"✅ Create CPU tensor (5s audio): {cpu_tensor_time:.4f} ms")

    def create_and_transfer():
        return torch.from_numpy(audio).float().cuda()

    _, gpu_transfer_time = measure_time(create_and_transfer)
    print(f"✅ Create + transfer to GPU (5s audio): {gpu_transfer_time:.4f} ms")

    # Test operations on GPU
    tensor_gpu = torch.from_numpy(audio).float().cuda()

    _, unsqueeze_time = measure_time(lambda: tensor_gpu.unsqueeze(0))
    print(f"✅ Unsqueeze operation (GPU): {unsqueeze_time:.4f} ms")

    _, reshape_time = measure_time(lambda: tensor_gpu.reshape(1, -1))
    print(f"✅ Reshape operation (GPU): {reshape_time:.4f} ms")


# Test 6: Async Performance
print("\n" + "=" * 80)
print("[Test 6] Async Queue Performance")
print("=" * 80)

async def test_async_queue():
    queue = asyncio.Queue()

    # Producer
    async def produce():
        start = time.perf_counter()
        for i in range(100):
            await queue.put(np.random.randn(1600).astype(np.float32))
        end = time.perf_counter()
        return (end - start) * 1000

    # Consumer
    async def consume():
        start = time.perf_counter()
        for i in range(100):
            await queue.get()
        end = time.perf_counter()
        return (end - start) * 1000

    # Run both
    produce_task = asyncio.create_task(produce())
    consume_task = asyncio.create_task(consume())

    produce_time, consume_time = await asyncio.gather(produce_task, consume_task)
    return produce_time, consume_time

produce_time, consume_time = asyncio.run(test_async_queue())
print(f"✅ Async queue produce (100 chunks): {produce_time:.4f} ms")
print(f"✅ Async queue consume (100 chunks): {consume_time:.4f} ms")
print(f"✅ Average per chunk: {(produce_time + consume_time) / 200:.4f} ms")


# Summary
print("\n" + "=" * 80)
print("PERFORMANCE SUMMARY")
print("=" * 80)

print(f"""
Audio Buffering:
  • Add chunk (0.1s): {np.mean(chunk_times):.4f} ms avg
  • Retrieve buffer: {retrieve_time:.4f} ms

Tensor Conversion (5s audio):
  • CPU creation: {cpu_time:.4f} ms
  • GPU transfer: {gpu_transfer_time if torch.cuda.is_available() else 'N/A'} ms

WebSocket Messages:
  • Serialize audio (4096 samples): {serialize_time:.4f} ms
  • Deserialize audio: {deserialize_time:.4f} ms
  • Serialize result: {result_time:.4f} ms

Memory Usage (10s audio):
  • Buffer overhead: {buffer_mem / 1024:.2f} KB
  • Total memory: {(buffer_mem + total_audio_mem) / 1024:.2f} KB

Async Queue:
  • Per chunk overhead: {(produce_time + consume_time) / 200:.4f} ms

TOTAL OVERHEAD (excluding ML inference):
  • Audio buffering: ~{np.mean(chunk_times):.3f} ms per 0.1s chunk
  • Message handling: ~{serialize_time + deserialize_time:.3f} ms per message
  • GPU transfer: ~{gpu_transfer_time if torch.cuda.is_available() else 0:.3f} ms per 5s chunk

Expected overhead for low latency mode (3s chunks):
  • Buffering: ~{np.mean(chunk_times) * 30:.3f} ms (30 chunks × 0.1s)
  • Tensor conversion + GPU: ~{gpu_transfer_time if torch.cuda.is_available() else cpu_time:.3f} ms
  • Message overhead: ~{(serialize_time + deserialize_time) * 2:.3f} ms (2 messages)
  • TOTAL NON-ML OVERHEAD: ~{np.mean(chunk_times) * 30 + (gpu_transfer_time if torch.cuda.is_available() else cpu_time) + (serialize_time + deserialize_time) * 2:.3f} ms

NOTE: Actual end-to-end latency will include:
  • Model inference time (requires GPU benchmark with actual models)
  • Network latency (WebSocket round trip)
  • Browser rendering time
""")

print("=" * 80)
print("✅ ALL BENCHMARKS COMPLETE")
print("=" * 80)
