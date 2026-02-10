"""
AR System Web API
FastAPI endpoints for AR system management
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import json

try:
    from .ar_system_manager import ar_system_manager
    from .task_executor import TaskExecutor
    from .rabbitmq_client import RabbitMQClient
    from .rtsp_manager import RTSPManager
except ImportError:
    from ar_system_manager import ar_system_manager
    from task_executor import TaskExecutor
    from rabbitmq_client import RabbitMQClient
    from rtsp_manager import RTSPManager

logger = logging.getLogger(__name__)

# Pydantic models
class ARCommand(BaseModel):
    audio_data: str  # base64 encoded audio
    user_id: str = "ar_user"

class RTSPStreamRequest(BaseModel):
    rtsp_url: str
    user_id: str = "ar_user"
    connection_method: str = "auto"
    auth_credentials: Optional[Dict[str, str]] = None
    network_options: Optional[Dict[str, Any]] = None

class TaskRequest(BaseModel):
    task_type: str
    task_params: Dict[str, Any] = {}
    ai_response: str = ""

class SystemStatus(BaseModel):
    status: str
    timestamp: str
    components: Dict[str, Any]
    active_streams: int
    active_commands: int

def create_ar_api_routes(app: FastAPI):
    """Create AR system API routes"""
    
    @app.post("/ar/command")
    async def process_ar_command(command: ARCommand):
        """Process AR command from audio data"""
        try:
            # Decode base64 audio data
            audio_data = base64.b64decode(command.audio_data)
            
            # Process through AR system
            result = await ar_system_manager.process_ar_command(
                audio_data=audio_data,
                user_id=command.user_id
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing AR command: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/ar/audio-upload")
    async def upload_audio_file(file: UploadFile = File(...), user_id: str = "ar_user"):
        """Upload audio file for processing"""
        try:
            # Read audio file
            audio_data = await file.read()
            
            # Process through AR system
            result = await ar_system_manager.process_ar_command(
                audio_data=audio_data,
                user_id=user_id
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing uploaded audio: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/ar/status")
    async def get_ar_system_status():
        """Get AR system status"""
        try:
            # Get system status from various components
            status = {
                "status": "active",
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "agent1_asr": "active",
                    "agent2_ai": "active",
                    "rtsp_manager": "active",
                    "rabbitmq_client": "active",
                    "task_executor": "active"
                },
                "active_streams": len(getattr(ar_system_manager.network_rtsp_manager, 'streams', {})),
                "active_commands": len(ar_system_manager.active_commands)
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting AR system status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/ar/rtsp/start")
    async def start_rtsp_stream(request: RTSPStreamRequest):
        """Start processing an RTSP stream with network optimization"""
        try:
            result = await ar_system_manager.start_network_rtsp_stream(
                rtsp_url=request.rtsp_url,
                user_id=request.user_id,
                connection_method=request.connection_method,
                auth_credentials=request.auth_credentials,
                network_options=request.network_options
            )
            
            if result.get("success"):
                return {
                    "status": "success",
                    "message": f"Started RTSP stream processing for {request.user_id}",
                    "rtsp_url": request.rtsp_url,
                    "connection_method": result.get("connection_method"),
                    "stream_info": result.get("stream_info", {})
                }
            else:
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "error": result.get("error", "Unknown error"),
                        "suggestions": result.get("suggestions", [])
                    }
                )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error starting RTSP stream: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/ar/glasses/connect")
    async def connect_ar_glasses(user_id: str = "ar_user"):
        """Connect to AR glasses input stream to receive video and audio"""
        try:
            logger.info(f"🥽 API request to connect AR glasses for user: {user_id}")
            
            result = await ar_system_manager.connect_to_ar_glasses(user_id)
            
            if result.get("status") == "connected":
                return {
                    "status": "success",
                    "message": result.get("message"),
                    "ar_glasses_url": result.get("ar_glasses_url"),
                    "user_id": user_id,
                    "connection_info": {
                        "stream_url": "",
                        "description": "AR glasses camera and microphone feed",
                        "auth": "nchc:nchc",
                        "capabilities": ["video", "audio", "real-time processing"]
                    }
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": result.get("message", "Failed to connect to AR glasses"),
                        "ar_glasses_url": result.get("ar_glasses_url")
                    }
                )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error connecting to AR glasses: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/ar/command/{command_id}")
    async def get_command_status(command_id: str):
        """Get status of a specific AR command"""
        try:
            if command_id in ar_system_manager.active_commands:
                command = ar_system_manager.active_commands[command_id]
                return {
                    "command_id": command_id,
                    "status": command.status,
                    "user_id": command.user_id,
                    "transcription": getattr(command, 'transcription', None),
                    "ai_response": getattr(command, 'ai_response', None),
                    "task_type": getattr(command, 'task_type', None),
                    "timestamp": command.timestamp.isoformat()
                }
            else:
                raise HTTPException(status_code=404, detail="Command not found")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting command status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/ar/rtsp/streams")
    async def list_rtsp_streams():
        """List active RTSP streams"""
        try:
            streams = await ar_system_manager.get_network_rtsp_status()
            return streams
        except Exception as e:
            logger.error(f"Error listing RTSP streams: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/ar/rtsp/streams/{user_id}")
    async def stop_rtsp_stream(user_id: str):
        """Stop an active RTSP stream"""
        try:
            result = await ar_system_manager.stop_network_rtsp_stream(user_id)
            if result.get("success"):
                return {"status": "success", "message": f"Stopped stream for {user_id}"}
            else:
                raise HTTPException(status_code=404, detail=result.get("error", "Stream not found"))
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error stopping RTSP stream: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/ar/rtsp/network/status/{user_id}")
    async def get_network_rtsp_status(user_id: str):
        """Get network RTSP stream status for a user"""
        try:
            status = await ar_system_manager.get_network_rtsp_status(user_id)
            return status
        except Exception as e:
            logger.error(f"Error getting network RTSP status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/ar/rtsp/network/status")
    async def get_all_network_rtsp_status():
        """Get all network RTSP streams status"""
        try:
            status = await ar_system_manager.get_network_rtsp_status()
            return status
        except Exception as e:
            logger.error(f"Error getting network RTSP status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/ar/network/diagnostics")
    async def run_network_diagnostics(rtsp_url: Optional[str] = None):
        """Run network diagnostics"""
        try:
            diagnostics = await ar_system_manager.get_network_diagnostics(rtsp_url)
            return diagnostics
        except Exception as e:
            logger.error(f"Error running network diagnostics: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/ar/queue/status")
    async def get_queue_status():
        """Get RabbitMQ queue status"""
        try:
            status = await ar_system_manager.rabbitmq_client.get_queue_info()
            return status
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/ar/task/execute")
    async def execute_task_directly(task: TaskRequest):
        """Execute a task directly (bypassing queue)"""
        try:
            task_data = {
                "task_type": task.task_type,
                "task_params": task.task_params,
                "ai_response": task.ai_response
            }
            
            result = await ar_system_manager.task_executor.execute_task(task_data)
            return result
            
        except Exception as e:
            logger.error(f"Error executing task: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # WebSocket endpoint for real-time AR communication
    @app.websocket("/ar/ws/{user_id}")
    async def ar_websocket_endpoint(websocket: WebSocket, user_id: str):
        """WebSocket endpoint for real-time AR communication"""
        await websocket.accept()
        logger.info(f"AR WebSocket connected for user: {user_id}")
        
        try:
            while True:
                # Receive audio data
                data = await websocket.receive_bytes()
                
                # Process through AR system
                result = await ar_system_manager.process_ar_command(
                    audio_data=data,
                    user_id=user_id
                )
                
                # Send response back
                await websocket.send_text(json.dumps(result))
                
        except WebSocketDisconnect:
            logger.info(f"AR WebSocket disconnected for user: {user_id}")
        except Exception as e:
            logger.error(f"AR WebSocket error for user {user_id}: {e}")
            await websocket.close()

# Connection manager for WebSocket
class ARConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"AR WebSocket connected: {user_id}")
    
    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"AR WebSocket disconnected: {user_id}")
    
    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)
    
    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

# Global connection manager
ar_connection_manager = ARConnectionManager()

# Create FastAPI app
app = FastAPI(
    title="AR AI System API",
    description="API for AR glasses AI processing system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create AR API routes
create_ar_api_routes(app)

if __name__ == "__main__":
    import uvicorn
    import asyncio
    
    async def startup():
        """Initialize AR system on startup"""
        try:
            logger.info("🚀 Starting AR AI System...")
            await ar_system_manager.initialize()
            logger.info("✅ AR System initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize AR system: {e}")
            raise
    
    # Add startup event
    @app.on_event("startup")
    async def startup_event():
        await startup()
    
    logger.info("🌈 Starting AR Web API Server...")
    logger.info("🎯 Server will be available at http://0.0.0.0:8000")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
