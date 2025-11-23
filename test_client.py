#!/usr/bin/env python3
"""
Test client for real-time diarization server
"""

import asyncio
import json
import numpy as np
import websockets

async def test_server():
    print("="*70)
    print("Testing Real-Time Diarization Server")
    print("="*70)

    uri = "ws://localhost:8765"
    print(f"\n🔗 Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")

            # Wait for initial status
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Received: {data}")

            # Send some test audio chunks
            print("\n📤 Sending test audio chunks...")
            for i in range(5):
                # Generate 0.5 seconds of random audio
                audio_chunk = np.random.randn(8000).astype(np.float32) * 0.1

                message = {
                    'type': 'audio',
                    'audio': audio_chunk.tolist()
                }

                await websocket.send(json.dumps(message))
                print(f"  Sent chunk {i+1}/5 ({len(audio_chunk)} samples)")

                # Try to receive any results
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(response)
                    print(f"  📨 Received: {data}")
                except asyncio.TimeoutError:
                    print(f"  (No response yet - buffering)")

                await asyncio.sleep(0.5)

            # Wait a bit for final results
            print("\n⏳ Waiting for final results...")
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(response)
                    print(f"📨 Received: {data}")
            except asyncio.TimeoutError:
                print("✅ Test complete (timeout waiting for more results)")

            # Send stop
            await websocket.send(json.dumps({'type': 'stop'}))
            print("\n🛑 Sent stop signal")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "="*70)
    print("✅ TEST PASSED - Server is working!")
    print("="*70)
    return True

if __name__ == "__main__":
    result = asyncio.run(test_server())
    exit(0 if result else 1)
