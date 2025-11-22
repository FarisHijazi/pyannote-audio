#!/usr/bin/env python3
"""
Test with actual audio file to trigger full processing
"""

import asyncio
import json
import numpy as np
import websockets
import sys

async def test_with_audio():
    print("="*70)
    print("Testing with generated speech-like audio")
    print("="*70)

    uri = "ws://localhost:8765"
    print(f"\n🔗 Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")

            # Wait for ready
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 {data['message']}")

            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 {data['message']}")

            print("\n📤 Sending speech-like audio...")

            # Generate more realistic audio with speech-like patterns
            sample_rate = 16000
            chunk_size = 4096

            # Send 5 seconds of audio that might trigger speech detection
            total_duration = 5.0
            num_chunks = int((total_duration * sample_rate) / chunk_size)

            print(f"   Sending {num_chunks} chunks ({total_duration}s)")

            for i in range(num_chunks):
                # Generate audio with speech-like envelope
                # Alternate between "speech" and "silence"
                if i % 8 < 5:  # 5 chunks speech, 3 chunks silence pattern
                    # Speech-like: amplitude modulation
                    t = np.arange(chunk_size) / sample_rate
                    freq = 100 + 50 * np.sin(2 * np.pi * i / 10)
                    audio = 0.3 * np.sin(2 * np.pi * freq * t)
                    # Add formants
                    audio += 0.1 * np.sin(2 * np.pi * 800 * t)
                    audio += 0.05 * np.sin(2 * np.pi * 2500 * t)
                    audio = audio.astype(np.float32)
                else:
                    # Silence
                    audio = np.random.randn(chunk_size).astype(np.float32) * 0.01

                message = {
                    'type': 'audio',
                    'audio': audio.tolist()
                }

                await websocket.send(json.dumps(message))

                # Check for responses
                try:
                    while True:
                        response = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                        data = json.loads(response)

                        if data['type'] == 'result':
                            print(f"   ✅ RESULT: {data['speaker']} at {data['start']}-{data['end']}s")
                        elif data['type'] == 'error':
                            print(f"   ❌ ERROR: {data['message']}")
                            return False
                except asyncio.TimeoutError:
                    pass

                if (i + 1) % 10 == 0:
                    elapsed = (i + 1) * chunk_size / sample_rate
                    print(f"   Progress: {elapsed:.1f}s")

            # Wait for results
            print("\n⏳ Waiting for processing...")
            try:
                for _ in range(100):
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                    data = json.loads(response)

                    if data['type'] == 'result':
                        print(f"✅ RESULT: {data['speaker']} at {data['start']}-{data['end']}s")
                    elif data['type'] == 'error':
                        print(f"❌ ERROR: {data['message']}")
                        return False
            except asyncio.TimeoutError:
                pass

            await websocket.send(json.dumps({'type': 'stop'}))
            print("\n✅ Test complete")
            return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_with_audio())
    sys.exit(0 if result else 1)
