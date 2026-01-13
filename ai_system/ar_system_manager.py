"""
AR System Manager
Manages the flow from AR glasses RTSP stream through Agent1 (ASR) and Agent2 (AI) to task execution
"""

import asyncio
import json
import logging
import cv2
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid
import aiohttp
import pika
from dataclasses import dataclass

try:
    from .orchestrator import ai_orchestrator
    from .voice_whisper import voice_handler
    from .task_executor import TaskExecutor
    from .rtsp_manager import RTSPManager
    from .network_rtsp_manager import NetworkRTSPManager
    from .rabbitmq_client import RabbitMQClient
except ImportError:
    from orchestrator import ai_orchestrator
    from voice_whisper import voice_handler
    from task_executor import TaskExecutor
    from rtsp_manager import RTSPManager
    from network_rtsp_manager import NetworkRTSPManager
    from rabbitmq_client import RabbitMQClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ARCommand:
    """Represents a command from AR glasses"""
    command_id: str
    user_id: str
    audio_data: bytes
    timestamp: datetime
    session_id: str = None
    transcription: str = None
    ai_response: str = None
    task_type: str = None
    task_params: Dict[str, Any] = None
    status: str = "pending"  # pending, processing, completed, failed

class Agent1ASR:
    """Agent 1: Automatic Speech Recognition"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict] = {}
        
    async def initialize(self):
        """Initialize ASR components"""
        logger.info("Initializing Agent1 (ASR)...")
        await voice_handler.initialize()
        logger.info("Agent1 (ASR) initialized successfully")
        
    async def process_audio_stream(self, command: ARCommand) -> str:
        """Process audio from AR glasses and return transcription"""
        try:
            logger.info(f"Agent1 processing audio for command: {command.command_id}")
            
            # Process audio through whisper.cpp
            transcription = await voice_handler.process_audio_stream(
                command.user_id, 
                command.audio_data
            )
            
            if transcription and transcription.strip() and transcription != "[BLANK_AUDIO]":
                command.transcription = transcription.strip()
                command.status = "transcribed"
                logger.info(f"Agent1 transcription: {transcription}")
                return transcription
            else:
                logger.warning("Agent1: No valid transcription received")
                command.status = "no_speech"
                return None
                
        except Exception as e:
            logger.error(f"Agent1 ASR error: {e}")
            command.status = "asr_error"
            return None

class Agent2AI:
    """Agent 2: AI Processing with MCP, Ollama, and RAG"""
    
    def __init__(self):
        self.active_sessions: Dict[str, str] = {}
        
    async def initialize(self):
        """Initialize AI components"""
        logger.info("Initializing Agent2 (AI)...")
        await ai_orchestrator.initialize()
        logger.info("Agent2 (AI) initialized successfully")
        
    async def process_command(self, command: ARCommand) -> Dict[str, Any]:
        """Process transcribed command through AI system"""
        try:
            logger.info(f"Agent2 processing command: {command. transcription}")
            
            # Get or create session for user
            if command.user_id not in self.active_sessions:
                session_id = await ai_orchestrator.create_session(
                    title=f"AR Session {command.user_id}"
                )
                self.active_sessions[command.user_id] = session_id
                command.session_id = session_id
            else:
                command.session_id = self.active_sessions[command.user_id]
            
            # Process through AI orchestrator
            result = await ai_orchestrator.process_query(
                query=command.transcription,
                session_id=command.session_id,
                use_tools=True,
                use_memory=True
            )
            
            command.ai_response = result["response"]
            command.status = "ai_processed"
            
            # Extract task information if available
            tools_executed = result.get("tools_executed", [])
            if tools_executed:
                # Determine task type from tools used
                command.task_type = self._determine_task_type(tools_executed, command.transcription)
                command.task_params = self._extract_task_params(tools_executed, command.transcription)
            
            logger.info(f"Agent2 response: {result['response']}")
            return result
            
        except Exception as e:
            logger.error(f"Agent2 AI processing error: {e}")
            command.status = "ai_error"
            return {"response": f"AI processing error: {str(e)}", "tools_executed": []}
    
    def _determine_task_type(self, tools_executed: List[Dict], transcription: str) -> str:
        """Determine task type based on tools used and transcription"""
        transcription_lower = transcription.lower()
        
        # Stock-related requests
        if any("stock" in tool.get("name", "").lower() for tool in tools_executed) or \
           any(word in transcription_lower for word in ["stock", "price", "shares", "market"]):
            return "display_stock"
        
        # Web search requests
        if any("search" in tool.get("name", "").lower() for tool in tools_executed) or \
           any(word in transcription_lower for word in ["search", "find", "look up", "google"]):
            return "web_search"
        
        # File system requests
        if any("file" in tool.get("name", "").lower() for tool in tools_executed):
            return "file_operation"
        
        # Browser requests
        if any(word in transcription_lower for word in ["open", "navigate", "browse", "website", "url"]):
            return "browser_control"
        
        return "general_display"
    
    def _extract_task_params(self, tools_executed: List[Dict], transcription: str) -> Dict[str, Any]:
        """Extract parameters for task execution"""
        params = {}
        
        # Extract tool results and parameters
        for tool in tools_executed:
            if "result" in tool:
                params["tool_result"] = tool["result"]
            if "args" in tool:
                params["tool_args"] = tool["args"]
        
        # Extract key information from transcription
        transcription_lower = transcription.lower()
        
        # Extract stock symbols
        import re
        stock_pattern = r'\b([A-Z]{1,5})\b'
        stocks = re.findall(stock_pattern, transcription.upper())
        if stocks:
            params["symbols"] = stocks
        
        # Extract URLs
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        urls = re.findall(url_pattern, transcription)
        if urls:
            params["urls"] = urls
        
        # Extract search terms
        search_keywords = ["search for", "find", "look up", "google"]
        for keyword in search_keywords:
            if keyword in transcription_lower:
                search_term = transcription_lower.split(keyword, 1)[1].strip()
                params["search_term"] = search_term
                break
        
        return params

class ARSystemManager:
    """Main AR System Manager orchestrating the entire flow"""
    
    def __init__(self):
        self.agent1 = Agent1ASR()
        self.agent2 = Agent2AI()
        self.rtsp_manager = RTSPManager()
        self.network_rtsp_manager = NetworkRTSPManager()
        self.rabbitmq_client = RabbitMQClient()
        self.task_executor = TaskExecutor()
        self.active_commands: Dict[str, ARCommand] = {}
        self.network_config = self._load_network_config()
        
        # AR glasses input stream URL
        self.ar_glasses_input_url = "rtsp://nchc:nchc@203.145.214.72:1935/mod/eye1.sdp"
        
    async def initialize(self):
        """Initialize all system components"""
        logger.info("Initializing AR System Manager...")
        logger.info(f"🥽 AR Glasses Input Stream: {self.ar_glasses_input_url}")
        
        try:
            await self.agent1.initialize()
            await self.agent2.initialize()
            await self.rtsp_manager.initialize()
            await self.rabbitmq_client.initialize()
            await self.task_executor.initialize()
            
            logger.info("AR System Manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AR System: {e}")
            raise
    
    async def connect_to_ar_glasses(self, user_id: str = "ar_user") -> Dict:
        """Connect to AR glasses RTSP stream to receive video and audio"""
        try:
            logger.info("🥽 Connecting to AR glasses input stream...")
            
            # Start processing the AR glasses input stream
            await self.start_ar_glasses_input_stream(self.ar_glasses_input_url, user_id)
            
            return {
                "status": "connected",
                "ar_glasses_url": self.ar_glasses_input_url,
                "user_id": user_id,
                "message": "Successfully connected to AR glasses stream"
            }
            
        except Exception as e:
            logger.error(f"Failed to connect to AR glasses: {e}")
            return {
                "status": "error",
                "message": f"Failed to connect to AR glasses: {str(e)}",
                "ar_glasses_url": self.ar_glasses_input_url
            }
    
    async def start_ar_glasses_input_stream(self, rtsp_url: str, user_id: str):
        """Start processing the AR glasses input stream for both video and audio"""
        logger.info(f"📡 Starting AR glasses input stream processing for {user_id}")
        logger.info(f"🎥 Stream URL: {rtsp_url}")
        
        # Process the RTSP stream from AR glasses
        await self._process_ar_glasses_stream(rtsp_url, user_id)
    
    async def _process_ar_glasses_stream(self, rtsp_url: str, user_id: str):
        """Process AR glasses RTSP stream for real-time audio processing"""
        try:
            # Use network RTSP manager to handle the AR glasses stream
            auth_credentials = {
                "username": "nchc",
                "password": "nchc"
            }
            
            # Define audio processing callback
            async def audio_callback(audio_data: bytes):
                """Process audio from AR glasses stream"""
                if audio_data and len(audio_data) > 0:
                    logger.debug(f"🎤 Received audio data: {len(audio_data)} bytes")
                    # Process the audio through our AR command pipeline
                    await self.process_ar_command(audio_data, user_id)
            
            # Define video callback for monitoring (optional)
            async def video_callback(frame):
                """Process video from AR glasses (for monitoring/context)"""
                if frame is not None:
                    logger.debug("📹 Received video frame from AR glasses")
                    # Could be used for visual context or recording
                    pass
            
            # Start the AR glasses stream processing
            result = await self.network_rtsp_manager.start_rtsp_stream(
                rtsp_url=rtsp_url,
                user_id=user_id,
                connection_method="direct",  # Direct connection to AR glasses
                auth_credentials=auth_credentials,
                audio_callback=audio_callback,
                video_callback=video_callback
            )
            
            logger.info(f"✅ AR glasses stream started: {result}")
            
        except Exception as e:
            logger.error(f"❌ Error processing AR glasses stream: {e}")
            raise
    
    async def process_ar_command(self, audio_data: bytes, user_id: str = "ar_user") -> Dict[str, Any]:
        """Main processing pipeline for AR commands"""
        command_id = str(uuid.uuid4())
        command = ARCommand(
            command_id=command_id,
            user_id=user_id,
            audio_data=audio_data,
            timestamp=datetime.now()
        )
        
        self.active_commands[command_id] = command
        
        try:
            # Step 1: Agent1 - Speech Recognition
            logger.info(f"Step 1: Processing audio through Agent1 (ASR)")
            transcription = await self.agent1.process_audio_stream(command)
            
            if not transcription:
                return {
                    "status": "error",
                    "message": "No speech detected or transcription failed",
                    "command_id": command_id
                }
            
            # Step 2: Agent2 - AI Processing
            logger.info(f"Step 2: Processing '{transcription}' through Agent2 (AI)")
            ai_result = await self.agent2.process_command(command)
            
            # Step 3: Task Execution (if needed)
            if command.task_type:
                logger.info(f"Step 3: Executing task '{command.task_type}'")
                
                # Send task to RabbitMQ for remote execution
                task_message = {
                    "command_id": command.command_id,
                    "task_type": command.task_type,
                    "task_params": command.task_params,
                    "ai_response": command.ai_response,
                    "timestamp": command.timestamp.isoformat()
                }
                
                await self.rabbitmq_client.send_task(task_message)
                command.status = "task_queued"
            else:
                command.status = "completed"
            
            return {
                "status": "success",
                "command_id": command.command_id,
                "transcription": command.transcription,
                "ai_response": command.ai_response,
                "task_type": command.task_type,
                "task_params": command.task_params,
                "timestamp": command.timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing AR command: {e}")
            command.status = "error"
            return {
                "status": "error",
                "message": str(e),
                "command_id": command_id
            }
    
    async def start_rtsp_stream_processing(self, rtsp_url: str, user_id: str = "ar_user"):
        """Start processing RTSP stream from AR glasses"""
        logger.info(f"Starting RTSP stream processing for user: {user_id}")
        
        async def audio_callback(audio_data: bytes):
            """Callback for processing audio from RTSP stream"""
            await self.process_ar_command(audio_data, user_id)
        
        await self.rtsp_manager.start_stream(rtsp_url, audio_callback)
    
    async def get_command_status(self, command_id: str) -> Dict[str, Any]:
        """Get status of a specific command"""
        if command_id not in self.active_commands:
            return {"error": "Command not found"}
        
        command = self.active_commands[command_id]
        return {
            "command_id": command.command_id,
            "status": command.status,
            "transcription": command.transcription,
            "ai_response": command.ai_response,
            "task_type": command.task_type,
            "timestamp": command.timestamp.isoformat()
        }
    
    def _load_network_config(self) -> Dict:
        """Load network configuration from file"""
        try:
            with open("network_config.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("network_config.json not found, using default config")
            return {"network": {"connection_method": "direct"}}
        except Exception as e:
            logger.error(f"Error loading network config: {e}")
            return {"network": {"connection_method": "direct"}}
    
    async def start_network_rtsp_stream(
        self, 
        rtsp_url: str, 
        user_id: str,
        connection_method: str = "auto",
        auth_credentials: Dict = None,
        network_options: Dict = None
    ) -> Dict:
        """Start RTSP stream with network optimization"""
        try:
            logger.info(f"Starting network RTSP stream for {user_id}")
            
            # Use network RTSP manager for cross-network streaming
            result = await self.network_rtsp_manager.start_rtsp_stream(
                rtsp_url=rtsp_url,
                user_id=user_id,
                connection_method=connection_method,
                auth_credentials=auth_credentials,
                network_options=network_options or self.network_config.get("network", {})
            )
            
            if result.get("success"):
                logger.info(f"Network RTSP stream started successfully for {user_id}")
                
                # Start audio processing loop
                asyncio.create_task(self._process_rtsp_audio_loop(user_id))
                
            return result
            
        except Exception as e:
            logger.error(f"Error starting network RTSP stream: {e}")
            return {
                "success": False,
                "error": str(e),
                "suggestions": ["Check network configuration", "Verify RTSP URL"]
            }
    
    async def _process_rtsp_audio_loop(self, user_id: str):
        """Process audio from RTSP stream continuously"""
        logger.info(f"Starting RTSP audio processing loop for {user_id}")
        
        audio_buffer = b""
        buffer_size = 16000 * 2 * 3  # 3 seconds of 16kHz 16-bit audio
        
        try:
            while True:
                # Get audio chunk from network RTSP manager
                audio_chunk = self.network_rtsp_manager.get_audio_chunk(user_id, timeout=1.0)
                
                if audio_chunk is None:
                    await asyncio.sleep(0.1)
                    continue
                
                audio_buffer += audio_chunk
                
                # Process when buffer is full
                if len(audio_buffer) >= buffer_size:
                    # Process the audio buffer through AR pipeline
                    try:
                        result = await self.process_ar_command(audio_buffer, user_id)
                        logger.debug(f"RTSP audio processing result: {result}")
                    except Exception as e:
                        logger.error(f"Error processing RTSP audio: {e}")
                    
                    # Reset buffer
                    audio_buffer = b""
                
        except Exception as e:
            logger.error(f"RTSP audio processing loop error for {user_id}: {e}")
    
    async def stop_network_rtsp_stream(self, user_id: str) -> Dict:
        """Stop network RTSP stream"""
        return await self.network_rtsp_manager.stop_rtsp_stream(user_id)
    
    async def get_network_rtsp_status(self, user_id: str = None) -> Dict:
        """Get network RTSP stream status"""
        return self.network_rtsp_manager.get_stream_status(user_id)
    
    async def get_network_diagnostics(self, rtsp_url: str = None) -> Dict:
        """Get network diagnostics"""
        return await self.network_rtsp_manager.get_network_diagnostics(rtsp_url)
    
    async def shutdown(self):
        """Shutdown all system components"""
        logger.info("Shutting down AR System Manager...")
        
        try:
            await self.rtsp_manager.shutdown()
            await self.network_rtsp_manager.stop_rtsp_stream("all")
            await self.rabbitmq_client.shutdown()
            await self.task_executor.shutdown()
            await ai_orchestrator.shutdown()
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

# Global instance
ar_system_manager = ARSystemManager()
