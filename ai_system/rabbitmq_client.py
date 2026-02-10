"""
RabbitMQ Client for Task Distribution
Handles sending tasks to remote execution hosts
"""

import asyncio
import json
import logging
import pika
import aio_pika
from typing import Dict, Any, Callable, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class RabbitMQClient:
    """RabbitMQ client for task distribution"""
    
    def __init__(self, host: str = None, port: int = None, 
                 username: str = None, password: str = None):
        # Load configuration from network_config.json if not provided
        self._load_config()
        
        # Override with provided parameters
        self.host = host or self.host
        self.port = port or self.port
        self.username = username or self.username
        self.password = password or self.password
        
        self.connection = None
        self.channel = None
        self.task_queue_name = "ar_tasks"
        self.response_queue_name = "ar_responses"
        self.callbacks = {}
        
    def _load_config(self):
        """Load RabbitMQ configuration from network_config.json"""
        try:
            import os
            import json
            
            config_path = os.path.join(os.path.dirname(__file__), 'network_config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            rabbitmq_config = config.get('rabbitmq', {})
            self.host = rabbitmq_config.get('host', 'localhost')
            self.port = rabbitmq_config.get('port', 5672)
            self.username = rabbitmq_config.get('username', 'guest')
            self.password = rabbitmq_config.get('password', 'guest')
            
            logger.info(f"Loaded RabbitMQ config: {self.host}:{self.port} as {self.username}")
            
        except Exception as e:
            logger.warning(f"Could not load network config, using defaults: {e}")
            # Default configuration
            self.host = "localhost"
            self.port = 5672
            self.username = "guest"
            self.password = "guest"
        
    async def initialize(self):
        """Initialize RabbitMQ connection"""
        logger.info("Initializing RabbitMQ Client...")
        
        try:
            # Create connection
            connection_url = f"amqp://{self.username}:{self.password}@{self.host}:{self.port}/"
            self.connection = await aio_pika.connect_robust(connection_url)
            self.channel = await self.connection.channel()
            
            # Declare queues
            await self.channel.declare_queue(self.task_queue_name, durable=True)
            await self.channel.declare_queue(self.response_queue_name, durable=True)
            
            # Start consuming responses
            await self._start_response_consumer()
            
            logger.info("RabbitMQ Client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RabbitMQ: {e}")
            # For development, continue without RabbitMQ
            logger.warning("Continuing without RabbitMQ - tasks will be logged only")
    
    async def send_task(self, task_data: Dict[str, Any], 
                       callback: Callable = None, timeout: int = 300) -> str:
        """Send a task to the queue"""
        task_id = str(uuid.uuid4())
        
        try:
            if not self.connection:
                # If no RabbitMQ connection, log the task
                logger.warning("No RabbitMQ connection - logging task instead")
                await self._log_task_locally(task_data, task_id)
                return task_id
            
            # Prepare message
            message_body = {
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
                "timeout": timeout,
                **task_data
            }
            
            # Register callback if provided
            if callback:
                self.callbacks[task_id] = {
                    "callback": callback,
                    "timestamp": datetime.now(),
                    "timeout": timeout
                }
            
            # Send message
            message = aio_pika.Message(
                json.dumps(message_body).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                correlation_id=task_id,
                reply_to=self.response_queue_name
            )
            
            await self.channel.default_exchange.publish(
                message,
                routing_key=self.task_queue_name
            )
            
            logger.info(f"Task sent to queue: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Error sending task to queue: {e}")
            # Fallback to local logging
            await self._log_task_locally(task_data, task_id)
            return task_id
    
    async def _log_task_locally(self, task_data: Dict[str, Any], task_id: str):
        """Log task locally when RabbitMQ is not available"""
        logger.info(f"TASK EXECUTION REQUEST (ID: {task_id}):")
        logger.info(f"  Type: {task_data.get('task_type', 'unknown')}")
        logger.info(f"  Params: {task_data.get('task_params', {})}")
        logger.info(f"  AI Response: {task_data.get('ai_response', 'N/A')}")
        
        # Simulate task completion for development
        await asyncio.sleep(1)
        
        # Create mock response
        mock_response = {
            "task_id": task_id,
            "status": "completed",
            "result": "Task logged locally - no remote execution",
            "timestamp": datetime.now().isoformat()
        }
        
        # Call callback if exists
        if task_id in self.callbacks:
            try:
                await self.callbacks[task_id]["callback"](mock_response)
                del self.callbacks[task_id]
            except Exception as e:
                logger.error(f"Error calling task callback: {e}")
    
    async def _start_response_consumer(self):
        """Start consuming response messages"""
        if not self.connection:
            return
            
        try:
            queue = await self.channel.declare_queue(self.response_queue_name, durable=True)
            
            async def process_response(message):
                try:
                    response_data = json.loads(message.body.decode())
                    task_id = response_data.get("task_id")
                    
                    if task_id and task_id in self.callbacks:
                        callback_info = self.callbacks[task_id]
                        
                        try:
                            await callback_info["callback"](response_data)
                        except Exception as e:
                            logger.error(f"Error in response callback: {e}")
                        finally:
                            del self.callbacks[task_id]
                    
                    await message.ack()
                    
                except Exception as e:
                    logger.error(f"Error processing response message: {e}")
                    await message.nack(requeue=False)
            
            await queue.consume(process_response)
            logger.info("Started consuming response messages")
            
        except Exception as e:
            logger.error(f"Error starting response consumer: {e}")
    
    async def get_queue_info(self) -> Dict[str, Any]:
        """Get information about queues"""
        if not self.connection:
            return {"status": "disconnected"}
        
        try:
            task_queue = await self.channel.declare_queue(self.task_queue_name, durable=True)
            response_queue = await self.channel.declare_queue(self.response_queue_name, durable=True)
            
            return {
                "status": "connected",
                "task_queue": {
                    "name": self.task_queue_name,
                    "message_count": task_queue.declaration_result.message_count,
                    "consumer_count": task_queue.declaration_result.consumer_count
                },
                "response_queue": {
                    "name": self.response_queue_name,
                    "message_count": response_queue.declaration_result.message_count,
                    "consumer_count": response_queue.declaration_result.consumer_count
                },
                "pending_callbacks": len(self.callbacks)
            }
            
        except Exception as e:
            logger.error(f"Error getting queue info: {e}")
            return {"status": "error", "message": str(e)}
    
    async def shutdown(self):
        """Shutdown RabbitMQ connection"""
        logger.info("Shutting down RabbitMQ Client...")
        
        try:
            if self.connection:
                await self.connection.close()
                
        except Exception as e:
            logger.error(f"Error during RabbitMQ shutdown: {e}")
        
        logger.info("RabbitMQ Client shutdown complete")

# Task message format:
"""
{
    "task_id": "uuid",
    "command_id": "original_ar_command_id",
    "task_type": "display_stock|web_search|browser_control|file_operation|general_display",
    "task_params": {
        "symbols": ["AAPL", "GOOGL"],
        "search_term": "weather today",
        "urls": ["https://example.com"],
        "tool_result": {...},
        "tool_args": {...}
    },
    "ai_response": "The stock price for Apple is...",
    "timestamp": "2025-01-01T12:00:00",
    "timeout": 300
}
"""

# Response message format:
"""
{
    "task_id": "uuid",
    "status": "completed|failed|timeout",
    "result": "Description of what was executed",
    "screenshot": "base64_encoded_screenshot",
    "error": "Error message if failed",
    "timestamp": "2025-01-01T12:00:00"
}
"""
