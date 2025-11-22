#!/usr/bin/env python3
"""
Demo WebSocket server for testing frontend without models
Simulates speaker diarization results
"""

import asyncio
import json
import numpy as np
import websockets
from websockets.server import serve
import random
import time


class DemoServer:
    """Demo server that simulates diarization without models"""

    def __init__(self):
        self.active_connections = set()
        self.speakers = ['SPEAKER_00', 'SPEAKER_01', 'SPEAKER_02']

    async def handle_client(self, websocket):
        """Handle a client connection"""
        print(f"✅ Client connected: {websocket.remote_address}")
        self.active_connections.add(websocket)

        try:
            # Send ready status
            await websocket.send(json.dumps({
                'type': 'status',
                'message': 'Demo mode - simulating results (no actual ML models)'
            }))

            audio_time = 0.0
            last_speaker = None

            # Process audio chunks
            async for message in websocket:
                try:
                    data = json.loads(message)

                    if data['type'] == 'audio':
                        # Get audio chunk length
                        audio_data = data['audio']
                        chunk_duration = len(audio_data) / 16000.0  # Assuming 16kHz
                        audio_time += chunk_duration

                        # Simulate processing every ~3 seconds
                        if audio_time >= 2.0:
                            # Generate simulated results
                            num_segments = random.randint(1, 3)

                            for i in range(num_segments):
                                # Pick a speaker (bias toward continuing same speaker)
                                if last_speaker and random.random() < 0.6:
                                    speaker = last_speaker
                                else:
                                    speaker = random.choice(self.speakers)
                                    last_speaker = speaker

                                # Generate segment times
                                start_time = audio_time - 2.0 + (i * 0.7)
                                end_time = start_time + random.uniform(0.5, 1.5)

                                result = {
                                    'type': 'result',
                                    'time': round(audio_time, 2),
                                    'speaker': speaker,
                                    'start': round(max(0, start_time), 2),
                                    'end': round(end_time, 2)
                                }

                                await websocket.send(json.dumps(result))
                                print(f"📊 Sent: {speaker} at {result['start']}-{result['end']}s")

                            # Reset counter
                            audio_time = 0.0

                    elif data['type'] == 'stop':
                        print("🛑 Client stopped recording")
                        await websocket.send(json.dumps({
                            'type': 'status',
                            'message': 'Stopped'
                        }))

                except json.JSONDecodeError:
                    print("❌ Invalid JSON received")
                except Exception as e:
                    print(f"❌ Error processing message: {e}")
                    import traceback
                    traceback.print_exc()

        except websockets.exceptions.ConnectionClosed:
            print(f"❌ Client disconnected: {websocket.remote_address}")
        finally:
            self.active_connections.remove(websocket)

    async def start(self, host='0.0.0.0', port=8765):
        """Start the WebSocket server"""
        print("="*70)
        print("DEMO Server - Real-Time Speaker Diarization")
        print("="*70)
        print("\n⚠️  DEMO MODE - Simulating results (no actual ML models)")
        print(f"🚀 Starting WebSocket server on ws://{host}:{port}")
        print(f"📊 Open realtime_demo.html in your browser to start\n")
        print(f"   URL: file://{__file__.replace('demo_server_no_models.py', 'realtime_demo.html')}\n")

        async with serve(self.handle_client, host, port):
            await asyncio.Future()  # run forever


if __name__ == "__main__":
    server = DemoServer()

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped")
