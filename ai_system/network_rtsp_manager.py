#!/usrimport asyncio
import logging
import subprocess
import json
import socket
import struct
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Callable
"""
Enhanced RTSP Manager for Cross-Network AR Glasses
Handles RTSP streaming across different networks with various connection methods
"""

import asyncio
import logging
import subprocess
import json
import socket
import struct
import threading
import time
from datetime import datetime
from typing import Dict, Optional, Callable, List
import cv2
import numpy as np
from queue import Queue, Empty

logger = logging.getLogger(__name__)

class NetworkRTSPManager:
    """Enhanced RTSP Manager for cross-network streaming"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.streams = {}
        self.processes = {}
        self.audio_queues = {}
        self.video_queues = {}
        self.running = False
        
        # Network configuration
        self.network_config = self.config.get('network', {})
        self.rtsp_config = self.config.get('rtsp', {})
        
        # Connection methods
        self.connection_methods = {
            'direct': self._setup_direct_connection,
            'port_forward': self._setup_port_forward,
            'vpn': self._setup_vpn_connection,
            'relay': self._setup_relay_connection,
            'tailscale': self._setup_tailscale_connection
        }
        
    async def start_rtsp_stream(
        self, 
        rtsp_url: str, 
        user_id: str,
        connection_method: str = 'auto',
        auth_credentials: Dict = None,
        network_options: Dict = None,
        audio_callback: Callable = None,
        video_callback: Callable = None
    ) -> Dict:
        """Start RTSP stream with network detection and optimization"""
        
        try:
            logger.info(f"Starting RTSP stream for user {user_id}")
            logger.info(f"RTSP URL: {rtsp_url}")
            logger.info(f"Connection method: {connection_method}")
            
            # Detect network configuration if auto
            if connection_method == 'auto':
                connection_method = await self._detect_optimal_connection(rtsp_url)
                logger.info(f"Auto-detected connection method: {connection_method}")
            
            # Setup connection based on method
            if connection_method in self.connection_methods:
                rtsp_url = await self.connection_methods[connection_method](
                    rtsp_url, auth_credentials, network_options
                )
            
            # Test connectivity
            connectivity_result = await self._test_rtsp_connectivity(rtsp_url)
            if not connectivity_result['success']:
                return {
                    'success': False,
                    'error': f"Connectivity test failed: {connectivity_result['error']}",
                    'suggestions': connectivity_result.get('suggestions', [])
                }
            
            # Create queues for this stream
            self.audio_queues[user_id] = Queue(maxsize=100)
            self.video_queues[user_id] = Queue(maxsize=50)
            
            # Start FFmpeg process for audio extraction
            audio_process = await self._start_audio_extraction(rtsp_url, user_id)
            
            # Start video processing
            video_process = await self._start_video_processing(rtsp_url, user_id)
            
            # Store stream info
            self.streams[user_id] = {
                'rtsp_url': rtsp_url,
                'connection_method': connection_method,
                'audio_process': audio_process,
                'video_process': video_process,
                'audio_callback': audio_callback,
                'video_callback': video_callback,
                'started_at': datetime.now(),
                'status': 'active'
            }
            
            self.running = True
            
            logger.info(f"RTSP stream started successfully for user {user_id}")
            logger.info(f"Audio callback: {'✅' if audio_callback else '❌'}")
            logger.info(f"Video callback: {'✅' if video_callback else '❌'}")
            
            return {
                'success': True,
                'user_id': user_id,
                'connection_method': connection_method,
                'stream_info': {
                    'audio_queue_size': self.audio_queues[user_id].qsize(),
                    'video_queue_size': self.video_queues[user_id].qsize(),
                    'started_at': self.streams[user_id]['started_at'].isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error starting RTSP stream: {e}")
            return {
                'success': False,
                'error': str(e),
                'suggestions': [
                    "Check RTSP URL format",
                    "Verify network connectivity",
                    "Try different connection method",
                    "Check firewall settings"
                ]
            }
    
    async def _detect_optimal_connection(self, rtsp_url: str) -> str:
        """Detect optimal connection method based on network analysis"""
        
        try:
            # Parse RTSP URL to get host
            import urllib.parse
            parsed = urllib.parse.urlparse(rtsp_url)
            host = parsed.hostname
            port = parsed.port or 554
            
            # Test if host is on same network
            if await self._is_local_network(host):
                return 'direct'
            
            # Test if VPN is available
            if await self._check_vpn_connectivity():
                return 'vpn'
            
            # Test if Tailscale is available
            if await self._check_tailscale_connectivity():
                return 'tailscale'
            
            # Default to port forwarding
            return 'port_forward'
            
        except Exception as e:
            logger.warning(f"Network detection failed: {e}")
            return 'direct'
    
    async def _is_local_network(self, host: str) -> bool:
        """Check if host is on local network"""
        try:
            import ipaddress
            ip = ipaddress.ip_address(host)
            return ip.is_private
        except:
            return False
    
    async def _check_vpn_connectivity(self) -> bool:
        """Check if VPN connection is available"""
        try:
            # Check for common VPN interfaces
            import psutil
            interfaces = psutil.net_if_addrs()
            vpn_interfaces = ['tun0', 'tap0', 'wg0', 'vpn0']
            
            for interface in vpn_interfaces:
                if interface in interfaces:
                    return True
            return False
        except:
            return False
    
    async def _check_tailscale_connectivity(self) -> bool:
        """Check if Tailscale is available"""
        try:
            result = subprocess.run(['tailscale', 'status'], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    async def _setup_direct_connection(self, rtsp_url: str, auth: Dict, options: Dict) -> str:
        """Setup direct RTSP connection"""
        return rtsp_url
    
    async def _setup_port_forward(self, rtsp_url: str, auth: Dict, options: Dict) -> str:
        """Setup port forwarded connection"""
        if options and 'public_ip' in options:
            import urllib.parse
            parsed = urllib.parse.urlparse(rtsp_url)
            new_url = f"{parsed.scheme}://{options['public_ip']}:{parsed.port or 554}{parsed.path}"
            if parsed.query:
                new_url += f"?{parsed.query}"
            return new_url
        return rtsp_url
    
    async def _setup_vpn_connection(self, rtsp_url: str, auth: Dict, options: Dict) -> str:
        """Setup VPN connection"""
        if options and 'vpn_server_ip' in options:
            import urllib.parse
            parsed = urllib.parse.urlparse(rtsp_url)
            new_url = f"{parsed.scheme}://{options['vpn_server_ip']}:{parsed.port or 554}{parsed.path}"
            if parsed.query:
                new_url += f"?{parsed.query}"
            return new_url
        return rtsp_url
    
    async def _setup_relay_connection(self, rtsp_url: str, auth: Dict, options: Dict) -> str:
        """Setup relay server connection"""
        if options and 'relay_server' in options:
            return options['relay_server']
        return rtsp_url
    
    async def _setup_tailscale_connection(self, rtsp_url: str, auth: Dict, options: Dict) -> str:
        """Setup Tailscale connection"""
        try:
            # Get Tailscale IP of the server
            result = subprocess.run(['tailscale', 'ip', '-4'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                tailscale_ip = result.stdout.strip()
                import urllib.parse
                parsed = urllib.parse.urlparse(rtsp_url)
                new_url = f"{parsed.scheme}://{tailscale_ip}:{parsed.port or 554}{parsed.path}"
                if parsed.query:
                    new_url += f"?{parsed.query}"
                return new_url
        except Exception as e:
            logger.warning(f"Tailscale setup failed: {e}")
        
        return rtsp_url
    
    async def _test_rtsp_connectivity(self, rtsp_url: str) -> Dict:
        """Test RTSP connectivity"""
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(rtsp_url)
            host = parsed.hostname
            port = parsed.port or 554
            
            # Test TCP connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            
            try:
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    return {'success': True, 'message': 'Connectivity test passed'}
                else:
                    return {
                        'success': False,
                        'error': f'Cannot connect to {host}:{port}',
                        'suggestions': [
                            'Check if server is running',
                            'Verify firewall settings',
                            'Try different connection method'
                        ]
                    }
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Connection test failed: {e}',
                    'suggestions': [
                        'Check network connectivity',
                        'Verify RTSP URL format',
                        'Try using IP address instead of hostname'
                    ]
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Invalid RTSP URL: {e}',
                'suggestions': ['Check RTSP URL format']
            }
    
    async def _start_audio_extraction(self, rtsp_url: str, user_id: str) -> subprocess.Popen:
        """Start FFmpeg process for audio extraction with network optimization"""
        
        # FFmpeg command with network optimization
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',  # Overwrite output
            '-rtsp_transport', 'tcp',  # Use TCP for better reliability
            '-timeout', '30000000',  # 30 second timeout
            '-reconnect', '1',
            '-reconnect_streamed', '1',
            '-reconnect_delay_max', '2',
            '-i', rtsp_url,
            '-vn',  # No video
            '-acodec', 'pcm_s16le',  # 16-bit PCM
            '-ar', '16000',  # 16kHz sample rate
            '-ac', '1',  # Mono
            '-f', 'wav',  # WAV format
            'pipe:1'  # Output to stdout
        ]
        
        logger.info(f"Starting audio extraction: {' '.join(ffmpeg_cmd)}")
        
        try:
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Start audio reading thread
            audio_thread = threading.Thread(
                target=self._read_audio_stream,
                args=(process.stdout, user_id),
                daemon=True
            )
            audio_thread.start()
            
            return process
            
        except Exception as e:
            logger.error(f"Failed to start audio extraction: {e}")
            raise
    
    async def _start_video_processing(self, rtsp_url: str, user_id: str) -> threading.Thread:
        """Start video processing with OpenCV"""
        
        def video_worker():
            try:
                cap = cv2.VideoCapture(rtsp_url)
                
                # Set video capture properties for network streaming
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FPS, 15)  # Limit FPS for network streaming
                
                while self.running and user_id in self.streams:
                    ret, frame = cap.read()
                    if ret:
                        # Resize frame for network efficiency
                        frame = cv2.resize(frame, (640, 480))
                        
                        # Add to queue if not full
                        if not self.video_queues[user_id].full():
                            self.video_queues[user_id].put(frame)
                        else:
                            # Remove old frame and add new one
                            try:
                                self.video_queues[user_id].get_nowait()
                                self.video_queues[user_id].put(frame)
                            except Empty:
                                pass
                    else:
                        logger.warning(f"Failed to read video frame for user {user_id}")
                        time.sleep(0.1)
                
                cap.release()
                logger.info(f"Video processing stopped for user {user_id}")
                
            except Exception as e:
                logger.error(f"Video processing error for user {user_id}: {e}")
        
        video_thread = threading.Thread(target=video_worker, daemon=True)
        video_thread.start()
        
        return video_thread
    
    def _read_audio_stream(self, stream, user_id: str):
        """Read audio data from FFmpeg stream"""
        try:
            while self.running and user_id in self.streams:
                # Read audio chunk (1024 samples * 2 bytes = 2048 bytes)
                chunk = stream.read(2048)
                if not chunk:
                    logger.warning(f"Audio stream ended for user {user_id}")
                    break
                
                # Add to queue if not full
                if not self.audio_queues[user_id].full():
                    self.audio_queues[user_id].put(chunk)
                else:
                    # Remove old chunk and add new one
                    try:
                        self.audio_queues[user_id].get_nowait()
                        self.audio_queues[user_id].put(chunk)
                    except Empty:
                        pass
                
                # Call audio callback if available
                if user_id in self.streams:
                    audio_callback = self.streams[user_id].get('audio_callback')
                    if audio_callback:
                        try:
                            # Call the callback directly (sync) or schedule if async
                            if asyncio.iscoroutinefunction(audio_callback):
                                # For async callbacks, we need to run in the event loop
                                # But since we're in a thread, we'll schedule it
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                try:
                                    loop.run_until_complete(audio_callback(chunk))
                                finally:
                                    loop.close()
                            else:
                                # For sync callbacks, call directly
                                audio_callback(chunk)
                        except Exception as e:
                            logger.error(f"Error calling audio callback for user {user_id}: {e}")
                        
        except Exception as e:
            logger.error(f"Audio reading error for user {user_id}: {e}")
    
    async def _call_audio_callback_safe(self, callback: Callable, audio_data: bytes):
        """Safely call audio callback, handling both sync and async callbacks"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(audio_data)
            else:
                callback(audio_data)
        except Exception as e:
            logger.error(f"Error in audio callback: {e}")
    
    def get_audio_chunk(self, user_id: str, timeout: float = 1.0) -> Optional[bytes]:
        """Get audio chunk from queue"""
        if user_id not in self.audio_queues:
            return None
        
        try:
            return self.audio_queues[user_id].get(timeout=timeout)
        except Empty:
            return None
    
    def get_video_frame(self, user_id: str, timeout: float = 1.0) -> Optional[np.ndarray]:
        """Get video frame from queue"""
        if user_id not in self.video_queues:
            return None
        
        try:
            return self.video_queues[user_id].get(timeout=timeout)
        except Empty:
            return None
    
    async def stop_rtsp_stream(self, user_id: str) -> Dict:
        """Stop RTSP stream"""
        try:
            if user_id not in self.streams:
                return {'success': False, 'error': 'Stream not found'}
            
            stream_info = self.streams[user_id]
            
            # Stop audio process
            if 'audio_process' in stream_info and stream_info['audio_process']:
                stream_info['audio_process'].terminate()
                stream_info['audio_process'].wait(timeout=5)
            
            # Mark stream as inactive
            stream_info['status'] = 'stopped'
            
            # Clean up queues
            if user_id in self.audio_queues:
                del self.audio_queues[user_id]
            if user_id in self.video_queues:
                del self.video_queues[user_id]
            
            # Remove stream
            del self.streams[user_id]
            
            logger.info(f"RTSP stream stopped for user {user_id}")
            
            return {'success': True, 'message': 'Stream stopped successfully'}
            
        except Exception as e:
            logger.error(f"Error stopping RTSP stream: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_stream_status(self, user_id: str = None) -> Dict:
        """Get stream status"""
        if user_id:
            if user_id in self.streams:
                stream = self.streams[user_id]
                return {
                    'user_id': user_id,
                    'status': stream['status'],
                    'connection_method': stream.get('connection_method', 'unknown'),
                    'started_at': stream['started_at'].isoformat(),
                    'audio_queue_size': self.audio_queues.get(user_id, Queue()).qsize(),
                    'video_queue_size': self.video_queues.get(user_id, Queue()).qsize()
                }
            else:
                return {'user_id': user_id, 'status': 'not_found'}
        else:
            return {
                'active_streams': len(self.streams),
                'streams': {
                    uid: {
                        'status': stream['status'],
                        'connection_method': stream.get('connection_method', 'unknown'),
                        'started_at': stream['started_at'].isoformat()
                    }
                    for uid, stream in self.streams.items()
                }
            }
    
    async def get_network_diagnostics(self, rtsp_url: str = None) -> Dict:
        """Get network diagnostics"""
        diagnostics = {
            'timestamp': datetime.now().isoformat(),
            'network_interfaces': {},
            'connectivity_tests': {},
            'recommendations': []
        }
        
        try:
            import psutil
            
            # Network interfaces
            for interface, addrs in psutil.net_if_addrs().items():
                diagnostics['network_interfaces'][interface] = []
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        diagnostics['network_interfaces'][interface].append({
                            'ip': addr.address,
                            'netmask': addr.netmask
                        })
            
            # Test connectivity if URL provided
            if rtsp_url:
                connectivity_result = await self._test_rtsp_connectivity(rtsp_url)
                diagnostics['connectivity_tests'][rtsp_url] = connectivity_result
            
            # Add recommendations
            diagnostics['recommendations'] = [
                "Use TCP transport for better reliability",
                "Configure proper firewall rules",
                "Consider VPN for secure connections",
                "Use lower resolution for better streaming"
            ]
            
        except Exception as e:
            diagnostics['error'] = str(e)
        
        return diagnostics

# Factory function to create NetworkRTSPManager
def create_network_rtsp_manager(config: Dict = None) -> NetworkRTSPManager:
    """Create and return NetworkRTSPManager instance"""
    return NetworkRTSPManager(config)
