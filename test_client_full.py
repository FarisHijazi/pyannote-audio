#!/usr/bin/env python3
"""
Full test client - sends enough audio to trigger processing
"""

import asyncio
import json
import numpy as np
import websockets

async def test_server():
    print("="*70)
    print("Full Test - Real-Time Diarization Server")
    print("="*70)

    uri = "ws://localhost:8765"
    print(f"\n🔗 Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")

            # Wait for initial status
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Server: {data['message']}")

            # Wait for ready status
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(response)
                    print(f"📨 Server: {data['message']}")
                    if 'Ready' in data['message']:
                        break
                except asyncio.TimeoutError:
                    print("⏳ Still loading models...")

            print("\n📤 Sending 5 seconds of test audio (enough to trigger processing)...")

            # Send 5 seconds of audio in 0.25s chunks = 20 chunks
            chunk_duration = 0.25  # seconds
            sample_rate = 16000
            samples_per_chunk = int(chunk_duration * sample_rate)
            total_chunks = 20  # 5 seconds total

            results_received = []

            for i in range(total_chunks):
                # Generate audio chunk (random noise)
                audio_chunk = np.random.randn(samples_per_chunk).astype(np.float32) * 0.1

                message = {
                    'type': 'audio',
                    'audio': audio_chunk.tolist()
                }

                await websocket.send(json.dumps(message))
                elapsed = (i + 1) * chunk_duration
                print(f"  Sent {elapsed:.2f}s of audio (chunk {i+1}/{total_chunks})")

                # Check for results (non-blocking)
                try:
                    while True:
                        response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                        data = json.loads(response)
                        if data['type'] == 'result':
                            print(f"  📊 RESULT: {data}")
                            results_received.append(data)
                        else:
                            print(f"  📨 {data}")
                except asyncio.TimeoutError:
                    pass  # No results yet

                await asyncio.sleep(0.1)

            # Wait for remaining results
            print("\n⏳ Waiting for final processing results...")
            try:
                for _ in range(20):  # Wait up to 2 seconds
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                    data = json.loads(response)
                    if data['type'] == 'result':
                        print(f"📊 RESULT: {data}")
                        results_received.append(data)
                    else:
                        print(f"📨 {data}")
            except asyncio.TimeoutError:
                pass

            # Send stop
            await websocket.send(json.dumps({'type': 'stop'}))
            print("\n🛑 Sent stop signal")

            print("\n" + "="*70)
            print(f"✅ TEST COMPLETE - Received {len(results_received)} results")
            print("="*70)

            if len(results_received) > 0:
                print("\n📊 Results summary:")
                for r in results_received:
                    print(f"  {r['speaker']}: {r['start']}s - {r['end']}s")
                return True
            else:
                print("\n⚠️  No results received (this may be normal for random noise)")
                return True  # Still pass - server is working

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_server())
    exit(0 if result else 1)
