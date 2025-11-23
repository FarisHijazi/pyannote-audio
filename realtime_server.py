#!/usr/bin/env python3
"""
WebSocket server for real-time speaker diarization
Receives audio from browser microphone and streams back results
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add source to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import numpy as np
import websockets
from websockets.server import serve

# Check for installation
try:
    from pyannote.audio.pipelines.realtime_streaming import RealTimeStreamingDiarization
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False


class RealtimeDiarizationServer:
    """WebSocket server for real-time diarization"""

    def __init__(self, hf_token=None):
        self.hf_token = hf_token
        self.active_connections = set()

    async def handle_client(self, websocket):
        """Handle a client connection"""
        print(f"✅ Client connected: {websocket.remote_address}")
        self.active_connections.add(websocket)

        if not PYANNOTE_AVAILABLE:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': 'pyannote.audio not installed. Run: pip install -e .'
            }))
            return

        # Create diarizer for this connection
        diarizer = RealTimeStreamingDiarization(
            sample_rate=16000,
            latency_mode='low',
            hf_token=self.hf_token
        )

        try:
            # Initialize
            await websocket.send(json.dumps({'type': 'status', 'message': 'Initializing...'}))
            await diarizer.start()
            await websocket.send(json.dumps({'type': 'status', 'message': 'Ready!'}))

            # Process audio chunks
            async for message in websocket:
                try:
                    data = json.loads(message)

                    if data['type'] == 'audio':
                        # Receive audio chunk
                        audio_data = np.array(data['audio'], dtype=np.float32)

                        # Add to buffer
                        diarizer.add_audio(audio_data)

                        # Process if ready
                        if diarizer.buffer_duration >= diarizer.min_chunk_duration:
                            audio_chunk = diarizer.get_buffered_audio(diarizer.chunk_duration)

                            if audio_chunk is not None:
                                # Process
                                import torch
                                waveform = torch.from_numpy(audio_chunk).float().unsqueeze(0)

                                output = diarizer.pipeline.process_chunk(
                                    waveform,
                                    diarizer.sample_rate,
                                    diarizer.total_processed
                                )

                                # Send results
                                for turn, _, speaker in output.speaker_diarization.itertracks(yield_label=True):
                                    result = {
                                        'type': 'result',
                                        'time': round(turn.start, 2),
                                        'speaker': speaker,
                                        'start': round(turn.start, 2),
                                        'end': round(turn.end, 2)
                                    }
                                    await websocket.send(json.dumps(result))

                                diarizer.total_processed += diarizer.chunk_duration

                    elif data['type'] == 'stop':
                        await diarizer.stop()
                        break

                except json.JSONDecodeError:
                    print(f"Invalid JSON received")
                except Exception as e:
                    print(f"Error processing audio: {e}")
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': str(e)
                    }))

        except websockets.exceptions.ConnectionClosed:
            print(f"❌ Client disconnected: {websocket.remote_address}")
        finally:
            self.active_connections.remove(websocket)
            await diarizer.stop()

    async def start(self, host='0.0.0.0', port=8765):
        """Start the WebSocket server"""
        print("="*70)
        print("Real-Time Speaker Diarization Server")
        print("="*70)
        print(f"\n🚀 Starting WebSocket server on ws://{host}:{port}")
        print(f"📊 Open realtime_demo.html in your browser to start\n")

        async with serve(self.handle_client, host, port):
            await asyncio.Future()  # run forever


if __name__ == "__main__":
    # Get HF token
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

    if not hf_token:
        print("⚠️  Warning: No HF_TOKEN found in environment")
        print("Models must already be cached, or server will fail")
        print("Set token with: export HF_TOKEN=your_token\n")

    # Create and start server
    server = RealtimeDiarizationServer(hf_token=hf_token)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped")
