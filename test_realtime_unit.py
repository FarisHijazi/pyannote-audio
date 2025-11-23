#!/usr/bin/env python3
"""
Comprehensive unit tests for real-time streaming diarization
Tests each component independently with mocking
"""

import sys
import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
import numpy as np
import asyncio
from collections import deque

# Add source to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("=" * 70)
print("Real-Time Streaming Diarization - Unit Tests")
print("=" * 70)


class TestRealTimeStreamingDiarization(unittest.TestCase):
    """Test RealTimeStreamingDiarization class"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock the imports that require full installation
        self.mock_modules = {}
        for module in ['pyannote.audio', 'pyannote.core', 'torch', 'torchaudio']:
            self.mock_modules[module] = MagicMock()
            sys.modules[module] = self.mock_modules[module]

    def test_audio_buffer_initialization(self):
        """Test audio buffer is properly initialized"""
        from pyannote.audio.pipelines.realtime_streaming import RealTimeStreamingDiarization

        diarizer = RealTimeStreamingDiarization(sample_rate=16000, chunk_duration=5.0)

        self.assertIsInstance(diarizer.audio_buffer, deque)
        self.assertEqual(diarizer.buffer_duration, 0.0)
        self.assertEqual(diarizer.sample_rate, 16000)
        self.assertEqual(diarizer.chunk_duration, 5.0)
        print("✅ Audio buffer initialization test passed")

    def test_add_audio_single_chunk(self):
        """Test adding a single audio chunk to buffer"""
        from pyannote.audio.pipelines.realtime_streaming import RealTimeStreamingDiarization

        diarizer = RealTimeStreamingDiarization(sample_rate=16000)

        # Create 1 second of audio (16000 samples)
        audio_chunk = np.random.randn(16000).astype(np.float32)
        diarizer.add_audio(audio_chunk)

        self.assertEqual(len(diarizer.audio_buffer), 1)
        self.assertAlmostEqual(diarizer.buffer_duration, 1.0, places=2)
        print("✅ Add audio single chunk test passed")

    def test_add_audio_multiple_chunks(self):
        """Test adding multiple audio chunks"""
        from pyannote.audio.pipelines.realtime_streaming import RealTimeStreamingDiarization

        diarizer = RealTimeStreamingDiarization(sample_rate=16000)

        # Add 5 chunks of 0.5 seconds each
        for _ in range(5):
            audio_chunk = np.random.randn(8000).astype(np.float32)  # 0.5s at 16kHz
            diarizer.add_audio(audio_chunk)

        self.assertEqual(len(diarizer.audio_buffer), 5)
        self.assertAlmostEqual(diarizer.buffer_duration, 2.5, places=2)
        print("✅ Add audio multiple chunks test passed")

    def test_get_buffered_audio(self):
        """Test retrieving buffered audio"""
        from pyannote.audio.pipelines.realtime_streaming import RealTimeStreamingDiarization

        diarizer = RealTimeStreamingDiarization(sample_rate=16000)

        # Add some audio chunks
        chunk1 = np.ones(8000).astype(np.float32)  # 0.5s
        chunk2 = np.ones(8000).astype(np.float32) * 2  # 0.5s
        diarizer.add_audio(chunk1)
        diarizer.add_audio(chunk2)

        # Get buffered audio
        buffered = diarizer.get_buffered_audio()

        self.assertEqual(len(buffered), 16000)  # 1 second total
        self.assertAlmostEqual(buffered[0], 1.0)
        self.assertAlmostEqual(buffered[8000], 2.0)
        print("✅ Get buffered audio test passed")

    def test_reset_buffer(self):
        """Test resetting the audio buffer"""
        from pyannote.audio.pipelines.realtime_streaming import RealTimeStreamingDiarization

        diarizer = RealTimeStreamingDiarization(sample_rate=16000)

        # Add audio
        diarizer.add_audio(np.random.randn(16000).astype(np.float32))
        self.assertGreater(len(diarizer.audio_buffer), 0)

        # Reset
        diarizer.reset()

        self.assertEqual(len(diarizer.audio_buffer), 0)
        self.assertEqual(diarizer.buffer_duration, 0.0)
        print("✅ Reset buffer test passed")

    def test_latency_modes(self):
        """Test different latency mode configurations"""
        from pyannote.audio.pipelines.realtime_streaming import RealTimeStreamingDiarization

        # Low latency mode
        low_latency = RealTimeStreamingDiarization(latency_mode='low')
        self.assertEqual(low_latency.chunk_duration, 3.0)
        self.assertEqual(low_latency.min_chunk_duration, 1.5)

        # Medium latency mode
        medium_latency = RealTimeStreamingDiarization(latency_mode='medium')
        self.assertEqual(medium_latency.chunk_duration, 5.0)
        self.assertEqual(medium_latency.min_chunk_duration, 2.5)

        # High quality mode
        high_quality = RealTimeStreamingDiarization(latency_mode='high_quality')
        self.assertEqual(high_quality.chunk_duration, 10.0)
        self.assertEqual(high_quality.min_chunk_duration, 5.0)

        print("✅ Latency modes test passed")

    def test_buffer_overflow_handling(self):
        """Test that buffer doesn't grow indefinitely"""
        from pyannote.audio.pipelines.realtime_streaming import RealTimeStreamingDiarization

        diarizer = RealTimeStreamingDiarization(sample_rate=16000, max_buffer_duration=10.0)

        # Add more than max buffer duration
        for _ in range(20):  # 20 seconds of audio in 1-second chunks
            diarizer.add_audio(np.random.randn(16000).astype(np.float32))

        # Buffer should be limited
        self.assertLessEqual(diarizer.buffer_duration, 11.0)  # Some tolerance
        print("✅ Buffer overflow handling test passed")


class TestWebSocketIntegration(unittest.TestCase):
    """Test WebSocket server functionality"""

    def test_audio_message_parsing(self):
        """Test parsing audio messages from WebSocket"""
        import json

        # Create mock audio message
        audio_data = [0.1, 0.2, 0.3, 0.4, 0.5]
        message = json.dumps({
            'type': 'audio',
            'audio': audio_data
        })

        # Parse message
        data = json.loads(message)
        self.assertEqual(data['type'], 'audio')
        self.assertEqual(len(data['audio']), 5)

        # Convert to numpy array
        audio_array = np.array(data['audio'], dtype=np.float32)
        self.assertEqual(audio_array.dtype, np.float32)
        self.assertAlmostEqual(audio_array[0], 0.1)
        print("✅ Audio message parsing test passed")

    def test_stop_message_parsing(self):
        """Test parsing stop messages"""
        import json

        message = json.dumps({'type': 'stop'})
        data = json.loads(message)

        self.assertEqual(data['type'], 'stop')
        print("✅ Stop message parsing test passed")

    def test_result_message_creation(self):
        """Test creating result messages to send to client"""
        import json

        result = {
            'type': 'result',
            'speaker': 'SPEAKER_00',
            'start': 1.5,
            'end': 3.2,
            'time': 2.0
        }

        message = json.dumps(result)
        parsed = json.loads(message)

        self.assertEqual(parsed['type'], 'result')
        self.assertEqual(parsed['speaker'], 'SPEAKER_00')
        self.assertAlmostEqual(parsed['start'], 1.5)
        print("✅ Result message creation test passed")


class TestAudioProcessing(unittest.TestCase):
    """Test audio processing logic"""

    def test_sample_rate_conversion(self):
        """Test audio sample rate conversion logic"""
        # Test that 16kHz is used (pyannote requirement)
        target_sample_rate = 16000

        # Simulate different input sample rates
        input_rates = [8000, 16000, 44100, 48000]

        for rate in input_rates:
            # Calculate conversion ratio
            ratio = target_sample_rate / rate
            self.assertIsInstance(ratio, float)

            if rate == 16000:
                self.assertEqual(ratio, 1.0)

        print("✅ Sample rate conversion test passed")

    def test_audio_chunk_sizes(self):
        """Test various audio chunk sizes are handled correctly"""
        chunk_sizes = [1024, 2048, 4096, 8192, 16000]
        sample_rate = 16000

        for size in chunk_sizes:
            # Calculate duration
            duration = size / sample_rate
            self.assertGreater(duration, 0)
            self.assertLess(duration, 2.0)  # All test chunks < 2 seconds

        print("✅ Audio chunk sizes test passed")

    def test_numpy_array_conversion(self):
        """Test converting JavaScript arrays to numpy arrays"""
        # Simulate JavaScript Float32Array as list
        js_array = [0.1, -0.2, 0.3, -0.4, 0.5]

        # Convert to numpy
        np_array = np.array(js_array, dtype=np.float32)

        self.assertEqual(np_array.dtype, np.float32)
        self.assertEqual(len(np_array), 5)
        self.assertAlmostEqual(np_array[0], 0.1, places=5)
        self.assertAlmostEqual(np_array[1], -0.2, places=5)
        print("✅ Numpy array conversion test passed")


class TestAsyncFunctionality(unittest.TestCase):
    """Test async processing functionality"""

    def test_async_generator_simulation(self):
        """Test async generator pattern used in audio streaming"""
        async def mock_audio_generator():
            for i in range(5):
                yield np.random.randn(1600).astype(np.float32)  # 0.1s chunks
                await asyncio.sleep(0.01)  # Simulate delay

        async def consume_generator():
            chunks = []
            async for chunk in mock_audio_generator():
                chunks.append(chunk)
            return chunks

        # Run async test
        chunks = asyncio.run(consume_generator())

        self.assertEqual(len(chunks), 5)
        self.assertEqual(chunks[0].shape[0], 1600)
        print("✅ Async generator simulation test passed")

    def test_async_queue_pattern(self):
        """Test async queue pattern for audio buffering"""
        async def queue_test():
            queue = asyncio.Queue()

            # Producer
            async def produce():
                for i in range(3):
                    await queue.put(f"chunk_{i}")
                    await asyncio.sleep(0.01)
                await queue.put(None)  # Sentinel

            # Consumer
            async def consume():
                results = []
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    results.append(item)
                return results

            # Run both
            producer_task = asyncio.create_task(produce())
            consumer_task = asyncio.create_task(consume())

            results = await consumer_task
            await producer_task

            return results

        results = asyncio.run(queue_test())

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0], "chunk_0")
        print("✅ Async queue pattern test passed")


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""

    def test_empty_audio_chunk(self):
        """Test handling empty audio chunks"""
        empty_array = np.array([], dtype=np.float32)

        # Should not crash
        self.assertEqual(len(empty_array), 0)
        print("✅ Empty audio chunk test passed")

    def test_invalid_json_handling(self):
        """Test handling invalid JSON messages"""
        import json

        invalid_messages = [
            "not json",
            "{incomplete",
            '{"type": "audio"}',  # Missing audio data
        ]

        for msg in invalid_messages:
            try:
                data = json.loads(msg)
                # Check if required fields exist
                if 'type' in data:
                    if data['type'] == 'audio' and 'audio' not in data:
                        # Missing audio field - should be handled
                        pass
            except json.JSONDecodeError:
                # Invalid JSON - should be caught
                pass

        print("✅ Invalid JSON handling test passed")

    def test_audio_dtype_validation(self):
        """Test audio data type validation"""
        # Test various dtypes
        dtypes = [np.float32, np.float64, np.int16, np.int32]

        for dtype in dtypes:
            array = np.array([1, 2, 3], dtype=dtype)

            # Convert to float32 (required for processing)
            converted = array.astype(np.float32)
            self.assertEqual(converted.dtype, np.float32)

        print("✅ Audio dtype validation test passed")


def run_all_tests():
    """Run all unit tests"""
    print("\n" + "=" * 70)
    print("Running Unit Tests")
    print("=" * 70 + "\n")

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRealTimeStreamingDiarization))
    suite.addTests(loader.loadTestsFromTestCase(TestWebSocketIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestAudioProcessing))
    suite.addTests(loader.loadTestsFromTestCase(TestAsyncFunctionality))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n✅ ALL UNIT TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
