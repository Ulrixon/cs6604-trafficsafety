"""
VCC real-time WebSocket streaming service.

Handles WebSocket connections to VCC API for streaming BSM and PSM messages
in real-time with 1-minute interval buffering.
"""

import asyncio
import json
import websockets
from typing import List, Dict, Callable, Optional
from datetime import datetime
from .vcc_client import vcc_client


class VCCRealtimeStreamer:
    """
    WebSocket client for streaming VCC API messages in real-time.

    Buffers messages in 1-minute intervals and triggers callback when
    interval completes for processing.
    """

    def __init__(self):
        """Initialize real-time streamer"""
        self.bsm_buffer: List[Dict] = []
        self.psm_buffer: List[Dict] = []
        self.current_interval_start: Optional[datetime] = None
        self.bsm_websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.psm_websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.callback: Optional[Callable] = None

    def _get_interval_start(self, timestamp: datetime) -> datetime:
        """
        Get the start of the 1-minute interval for a timestamp.

        Args:
            timestamp: Message timestamp

        Returns:
            Start of 1-minute interval
        """
        return timestamp.replace(second=0, microsecond=0)

    def _check_interval_boundary(self, timestamp: datetime) -> bool:
        """
        Check if timestamp crosses into a new 1-minute interval.

        Args:
            timestamp: Message timestamp

        Returns:
            True if interval boundary crossed
        """
        interval_start = self._get_interval_start(timestamp)

        if self.current_interval_start is None:
            self.current_interval_start = interval_start
            return False

        if interval_start > self.current_interval_start:
            return True  # New interval started

        return False

    async def _stream_bsm(self, uri: str):
        """
        Stream BSM messages from WebSocket.

        Args:
            uri: WebSocket URI for BSM messages
        """
        try:
            async with websockets.connect(uri) as websocket:
                self.bsm_websocket = websocket
                print(f"✓ Connected to BSM WebSocket: {uri[:50]}...")

                while self.running:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)

                        # Handle both single messages and arrays
                        messages = data if isinstance(data, list) else [data]

                        for msg in messages:
                            # Extract timestamp (VCC uses milliseconds)
                            timestamp_ms = msg.get('timestamp', 0)
                            if timestamp_ms == 0:
                                timestamp_ms = msg.get('publishTimestamp', 0)

                            if timestamp_ms == 0:
                                continue  # Skip messages without timestamp

                            # Convert to datetime (VCC uses milliseconds)
                            msg_time = datetime.fromtimestamp(
                                timestamp_ms / 1000)

                            # Check if interval boundary crossed
                            if self._check_interval_boundary(msg_time):
                                # Trigger callback with buffered messages
                                if self.callback:
                                    await self.callback(
                                        self.bsm_buffer.copy(),
                                        self.psm_buffer.copy(),
                                        self.current_interval_start
                                    )

                                # Clear buffers and start new interval
                                self.bsm_buffer = []
                                self.psm_buffer = []
                                self.current_interval_start = self._get_interval_start(
                                    msg_time)

                            # Add message to buffer
                            self.bsm_buffer.append(msg)

                    except asyncio.TimeoutError:
                        # Timeout is OK - continue listening
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        print("⚠ BSM WebSocket connection closed")
                        break
                    except Exception as e:
                        print(f"⚠ Error receiving BSM message: {e}")
                        continue

        except Exception as e:
            print(f"✗ BSM WebSocket error: {e}")
            self.bsm_websocket = None

    async def _stream_psm(self, uri: str):
        """
        Stream PSM messages from WebSocket.

        Args:
            uri: WebSocket URI for PSM messages
        """
        try:
            async with websockets.connect(uri) as websocket:
                self.psm_websocket = websocket
                print(f"✓ Connected to PSM WebSocket: {uri[:50]}...")

                while self.running:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)

                        # Handle both single messages and arrays
                        messages = data if isinstance(data, list) else [data]

                        for msg in messages:
                            # Extract timestamp (VCC uses milliseconds)
                            timestamp_ms = msg.get('timestamp', 0)
                            if timestamp_ms == 0:
                                timestamp_ms = msg.get('publishTimestamp', 0)

                            if timestamp_ms == 0:
                                continue

                            # Convert to datetime (VCC uses milliseconds)
                            msg_time = datetime.fromtimestamp(
                                timestamp_ms / 1000)

                            # Check if interval boundary crossed
                            if self._check_interval_boundary(msg_time):
                                # Trigger callback with buffered messages
                                if self.callback:
                                    await self.callback(
                                        self.bsm_buffer.copy(),
                                        self.psm_buffer.copy(),
                                        self.current_interval_start
                                    )

                                # Clear buffers and start new interval
                                self.bsm_buffer = []
                                self.psm_buffer = []
                                self.current_interval_start = self._get_interval_start(
                                    msg_time)

                            # Add message to buffer
                            self.psm_buffer.append(msg)

                    except asyncio.TimeoutError:
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        print("⚠ PSM WebSocket connection closed")
                        break
                    except Exception as e:
                        print(f"⚠ Error receiving PSM message: {e}")
                        continue

        except Exception as e:
            print(f"✗ PSM WebSocket error: {e}")
            self.psm_websocket = None

    async def start_streaming(
        self,
        callback: Callable[[List[Dict], List[Dict], datetime], None],
        intersection_id: str = 'all'
    ):
        """
        Start streaming BSM and PSM messages in real-time.

        Args:
            callback: Async function called when 1-minute interval completes
                      Signature: callback(bsm_messages, psm_messages, interval_start)
            intersection_id: Intersection ID or 'all' for all intersections
        """
        self.callback = callback
        self.running = True

        # Get WebSocket URLs
        bsm_uri = vcc_client.get_websocket_url('bsm', intersection_id)
        psm_uri = vcc_client.get_websocket_url('psm', intersection_id)

        if not bsm_uri:
            print("✗ Failed to get BSM WebSocket URL")
            return

        if not psm_uri:
            print("✗ Failed to get PSM WebSocket URL")
            return

        # Start streaming both BSM and PSM concurrently
        try:
            await asyncio.gather(
                self._stream_bsm(bsm_uri),
                self._stream_psm(psm_uri),
                return_exceptions=True
            )
        except Exception as e:
            print(f"✗ Streaming error: {e}")
        finally:
            self.running = False

    async def stop_streaming(self):
        """Stop streaming and close connections"""
        self.running = False

        if self.bsm_websocket:
            await self.bsm_websocket.close()
            self.bsm_websocket = None

        if self.psm_websocket:
            await self.psm_websocket.close()
            self.psm_websocket = None

        print("✓ Streaming stopped")


# Global streamer instance
vcc_streamer = VCCRealtimeStreamer()
