#!/usr/bin/env python3
"""
End-to-end test simulating browser behavior
Tests the full pipeline including ML processing
"""

import asyncio
import json
import numpy as np
import websockets
import sys

async def test_full_pipeline():
    print("="*70)
    print("END-TO-END TEST - Simulating Browser")
    print("="*70)

    uri = "ws://localhost:8765"
    print(f"\n🔗 Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")

            # Wait for initialization
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 {data['message']}")

            # Wait for ready
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 {data['message']}")

            print("\n📤 Sending audio that should trigger processing...")
            print("   (Sending enough audio to exceed min_chunk_duration)")

            # Send 4 seconds of audio in small chunks (like browser does)
            # Browser sends ~4096 samples at a time at 16kHz = 0.256s per chunk
            sample_rate = 16000
            chunk_size = 4096  # Same as browser
            total_duration = 4.0  # seconds
            total_samples = int(total_duration * sample_rate)
            num_chunks = total_samples // chunk_size

            print(f"   Total: {total_duration}s, Chunk size: {chunk_size} samples")
            print(f"   Sending {num_chunks} chunks...")

            results_received = []
            errors_received = []

            for i in range(num_chunks):
                # Generate audio chunk
                # Use varying amplitude to simulate speech
                amplitude = 0.1 + 0.05 * np.sin(2 * np.pi * i / 20)
                audio_chunk = np.random.randn(chunk_size).astype(np.float32) * amplitude

                message = {
                    'type': 'audio',
                    'audio': audio_chunk.tolist()
                }

                await websocket.send(json.dumps(message))

                # Check for responses (non-blocking)
                try:
                    while True:
                        response = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                        data = json.loads(response)

                        if data['type'] == 'result':
                            print(f"   ✅ RESULT: Speaker={data['speaker']}, Time={data['start']}-{data['end']}s")
                            results_received.append(data)
                        elif data['type'] == 'error':
                            print(f"   ❌ ERROR: {data['message']}")
                            errors_received.append(data)
                            return False
                        else:
                            print(f"   📨 {data}")
                except asyncio.TimeoutError:
                    pass  # No messages waiting

                # Progress indicator
                if (i + 1) % 10 == 0:
                    elapsed = (i + 1) * chunk_size / sample_rate
                    print(f"   Progress: {elapsed:.2f}s sent ({i+1}/{num_chunks} chunks)")

            # Wait for any remaining processing
            print("\n⏳ Waiting for final results...")
            try:
                for _ in range(50):  # Wait up to 5 seconds
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                    data = json.loads(response)

                    if data['type'] == 'result':
                        print(f"✅ RESULT: Speaker={data['speaker']}, Time={data['start']}-{data['end']}s")
                        results_received.append(data)
                    elif data['type'] == 'error':
                        print(f"❌ ERROR: {data['message']}")
                        errors_received.append(data)
                        return False
                    else:
                        print(f"📨 {data}")
            except asyncio.TimeoutError:
                pass

            # Send stop
            await websocket.send(json.dumps({'type': 'stop'}))
            print("\n🛑 Sent stop signal")

            print("\n" + "="*70)
            if errors_received:
                print(f"❌ TEST FAILED - {len(errors_received)} errors received")
                for err in errors_received:
                    print(f"   Error: {err['message']}")
                return False
            else:
                print(f"✅ TEST PASSED - No errors!")
                print(f"   Results received: {len(results_received)}")
                if results_received:
                    print("\n   Speaker timeline:")
                    for r in results_received:
                        print(f"     {r['speaker']}: {r['start']}s - {r['end']}s")
                else:
                    print("   (No speakers detected - normal for random noise)")
                return True

    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_full_pipeline())
    sys.exit(0 if result else 1)
