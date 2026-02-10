"""
RTSP Manager for handling basic RTSP stream operations
"""

import asyncio
import logging
import cv2
import numpy as np
from typing import Callable, Optional, Dict, Any
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

class RTSPManager:
    """
    RTSP Manager for handling RTSP stream connections and audio extraction
    """
    
    def __init__(self):
        self.is_initialized = False
        self.active_streams = {}
        self.stream_threads = {}
        self.stop_events = {}
        
    async def initialize(self):
        """Initialize the RTSP manager"""
        try:
            logger.info("Initializing RTSP Manager")
            self.is_initialized = True
            logger.info("RTSP Manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RTSP Manager: {e}")
            raise
    
    async def start_stream(self, rtsp_url: str, audio_callback: Callable[[bytes], None]):
        """
        Start an RTSP stream and extract audio
        
        Args:
            rtsp_url: The RTSP stream URL
            audio_callback: Callback function to handle audio data
        """
        try:
            logger.info(f"Starting RTSP stream: {rtsp_url}")
            
            # Create stop event for this stream
            stream_id = rtsp_url
            stop_event = threading.Event()
            self.stop_events[stream_id] = stop_event
            
            # Start stream processing in background thread
            thread = threading.Thread(
                target=self._process_rtsp_stream,
                args=(rtsp_url, audio_callback, stop_event),
                daemon=True
            )
            thread.start()
            
            self.stream_threads[stream_id] = thread
            self.active_streams[stream_id] = {
                'url': rtsp_url,
                'callback': audio_callback,
                'started_at': time.time()
            }
            
            logger.info(f"RTSP stream started successfully: {rtsp_url}")
            
        except Exception as e:
            logger.error(f"Failed to start RTSP stream {rtsp_url}: {e}")
            raise
    
    def _process_rtsp_stream(self, rtsp_url: str, audio_callback: Callable[[bytes], None], stop_event: threading.Event):
        """
        Process RTSP stream in background thread
        """
        try:
            logger.info(f"Processing RTSP stream: {rtsp_url}")
            
            # Try to connect to RTSP stream
            cap = cv2.VideoCapture(rtsp_url)
            
            if not cap.isOpened():
                logger.error(f"Failed to open RTSP stream: {rtsp_url}")
                return
            
            frame_count = 0
            audio_buffer_size = 1024 * 4  # 4KB audio chunks
            
            while not stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to read frame from RTSP stream")
                    time.sleep(0.1)
                    continue
                
                frame_count += 1
                
                # For now, simulate audio extraction
                # In a real implementation, you would extract audio from the RTSP stream
                if frame_count % 30 == 0:  # Every 30 frames (~1 second at 30fps)
                    # Generate dummy audio data for testing
                    dummy_audio = np.random.bytes(audio_buffer_size)
                    try:
                        audio_callback(dummy_audio)
                    except Exception as e:
                        logger.error(f"Audio callback error: {e}")
                
                # Small delay to prevent overwhelming the system
                time.sleep(0.033)  # ~30fps
            
            cap.release()
            logger.info(f"RTSP stream processing stopped: {rtsp_url}")
            
        except Exception as e:
            logger.error(f"Error processing RTSP stream {rtsp_url}: {e}")
    
    async def stop_stream(self, rtsp_url: str):
        """Stop a specific RTSP stream"""
        try:
            stream_id = rtsp_url
            
            if stream_id in self.stop_events:
                self.stop_events[stream_id].set()
                
            if stream_id in self.stream_threads:
                thread = self.stream_threads[stream_id]
                thread.join(timeout=5.0)  # Wait up to 5 seconds
                del self.stream_threads[stream_id]
                
            if stream_id in self.active_streams:
                del self.active_streams[stream_id]
                
            if stream_id in self.stop_events:
                del self.stop_events[stream_id]
                
            logger.info(f"RTSP stream stopped: {rtsp_url}")
            
        except Exception as e:
            logger.error(f"Error stopping RTSP stream {rtsp_url}: {e}")
    
    async def shutdown(self):
        """Shutdown the RTSP manager and stop all streams"""
        try:
            logger.info("Shutting down RTSP Manager")
            
            # Stop all active streams
            active_urls = list(self.active_streams.keys())
            for rtsp_url in active_urls:
                await self.stop_stream(rtsp_url)
            
            # Clear all data structures
            self.active_streams.clear()
            self.stream_threads.clear()
            self.stop_events.clear()
            
            self.is_initialized = False
            logger.info("RTSP Manager shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during RTSP Manager shutdown: {e}")
    
    def get_stream_status(self) -> Dict[str, Any]:
        """Get status of all active streams"""
        return {
            'initialized': self.is_initialized,
            'active_streams': len(self.active_streams),
            'stream_details': {
                url: {
                    'started_at': info['started_at'],
                    'duration': time.time() - info['started_at']
                }
                for url, info in self.active_streams.items()
            }
        }

# Factory function to create RTSPManager
def create_rtsp_manager() -> RTSPManager:
    """Create and return RTSPManager instance"""
    return RTSPManager()
