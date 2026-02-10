"""
Local LLM Manager
Handles communication with local language models via Ollama and other backends
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, AsyncGenerator, Any
import aiohttp
from dataclasses import asdict

try:
    from .config import LLMConfig, config
except ImportError:
    from config import LLMConfig, config

logger = logging.getLogger(__name__)

class LLMManager:
    """Manages local LLM interactions"""
    
    def __init__(self):
        self.active_models: Dict[str, bool] = {}
        self.model_stats: Dict[str, Dict] = {}
        
    async def initialize(self):
        """Initialize the LLM manager"""
        logger.info("Initializing LLM Manager...")
        await self._check_ollama_status()
        await self._load_available_models()
        
    async def _check_ollama_status(self) -> bool:
        """Check if Ollama is running"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434/api/tags") as response:
                    if response.status == 200:
                        logger.info("Ollama is running")
                        return True
        except Exception as e:
            logger.warning(f"Ollama not accessible: {e}")
            logger.info("Starting Ollama...")
            # Try to start Ollama
            process = await asyncio.create_subprocess_exec(
                "ollama", "serve",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.sleep(3)  # Give it time to start
            return await self._check_ollama_status()
        
        return False
    
    async def _load_available_models(self):
        """Load list of available models from Ollama"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get("models", [])
                        for model in models:
                            model_name = model["name"].split(":")[0]
                            self.active_models[model_name] = True
                            self.model_stats[model_name] = {
                                "size": model.get("size", 0),
                                "modified_at": model.get("modified_at", ""),
                                "digest": model.get("digest", "")
                            }
                        logger.info(f"Found {len(models)} available models: {list(self.active_models.keys())}")
        except Exception as e:
            logger.error(f"Error loading models: {e}")
    
    async def ensure_model_available(self, model_name: str) -> bool:
        """Ensure a model is available, pull if necessary"""
        if model_name in self.active_models:
            return True
            
        logger.info(f"Pulling model {model_name}...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:11434/api/pull",
                    json={"name": model_name}
                ) as response:
                    if response.status == 200:
                        async for line in response.content:
                            if line:
                                try:
                                    status = json.loads(line.decode())
                                    if status.get("status") == "success":
                                        self.active_models[model_name] = True
                                        logger.info(f"Successfully pulled {model_name}")
                                        return True
                                except json.JSONDecodeError:
                                    continue
        except Exception as e:
            logger.error(f"Error pulling model {model_name}: {e}")
            return False
        
        return False
    
    async def generate_response(
        self, 
        prompt: str, 
        model_name: str = None,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
        stream: bool = False
    ) -> str:
        """Generate response from LLM"""
        
        llm_config = config.get_llm_config(model_name)
        
        # Ensure model is available
        if not await self.ensure_model_available(llm_config.model_name):
            raise Exception(f"Model {llm_config.model_name} not available")
        
        # Prepare request
        request_data = {
            "model": llm_config.model_name,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature or llm_config.temperature,
                "num_predict": max_tokens or llm_config.max_tokens
            }
        }
        
        if system_prompt:
            request_data["system"] = system_prompt
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{llm_config.endpoint}/api/generate",
                    json=request_data
                ) as response:
                    if response.status == 200:
                        if stream:
                            return self._handle_stream_response(response)
                        else:
                            data = await response.json()
                            return data.get("response", "")
                    else:
                        error_text = await response.text()
                        raise Exception(f"LLM API error: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise
    
    async def _handle_stream_response(self, response) -> AsyncGenerator[str, None]:
        """Handle streaming response from LLM"""
        async for line in response.content:
            if line:
                try:
                    data = json.loads(line.decode())
                    if "response" in data:
                        yield data["response"]
                    if data.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model_name: str = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """Chat completion with conversation history"""
        
        llm_config = config.get_llm_config(model_name)
        
        if not await self.ensure_model_available(llm_config.model_name):
            raise Exception(f"Model {llm_config.model_name} not available")
        
        request_data = {
            "model": llm_config.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature or llm_config.temperature,
                "num_predict": max_tokens or llm_config.max_tokens
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{llm_config.endpoint}/api/chat",
                    json=request_data
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("message", {}).get("content", "")
                    else:
                        error_text = await response.text()
                        raise Exception(f"Chat API error: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            raise
    
    async def get_model_info(self, model_name: str = None) -> Dict[str, Any]:
        """Get information about a model"""
        llm_config = config.get_llm_config(model_name)
        
        model_info = {
            "name": llm_config.model_name,
            "type": llm_config.model_type,
            "endpoint": llm_config.endpoint,
            "context_length": llm_config.context_length,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens,
            "available": llm_config.model_name in self.active_models,
            "stats": self.model_stats.get(llm_config.model_name, {})
        }
        
        return model_info
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """List all available models with their info"""
        models = []
        for model_name in config.list_available_llms():
            model_info = await self.get_model_info(model_name)
            models.append(model_info)
        return models
    
    def _enhance_prompt_with_context(
        self,
        prompt: str,
        context: Dict[str, Any] = None,
        system_prompt: str = None
    ) -> str:
        """Enhance prompt with contextual information for better understanding"""
        
        enhanced_parts = []
        
        # Add system context
        if system_prompt:
            enhanced_parts.append(f"System Context: {system_prompt}")
        
        # Add conversational context
        if context:
            if context.get("conversation_history"):
                enhanced_parts.append("Recent Conversation:")
                for entry in context["conversation_history"][-3:]:
                    enhanced_parts.append(f"- {entry}")
            
            if context.get("user_preferences"):
                enhanced_parts.append("User Preferences:")
                for key, value in context["user_preferences"].items():
                    enhanced_parts.append(f"- {key}: {value}")
            
            if context.get("current_task"):
                enhanced_parts.append(f"Current Task Context: {context['current_task']}")
            
            if context.get("available_tools"):
                enhanced_parts.append(f"Available Tools: {', '.join(context['available_tools'])}")
        
        # Add the main prompt
        enhanced_parts.append("User Request:")
        enhanced_parts.append(prompt)
        
        # Add intelligent context instruction
        enhanced_parts.append("\nInstructions: You are an intelligent AI agent. Consider all provided context to give the most helpful and accurate response. If the user's intent isn't completely clear, use the context to make reasonable inferences about what they want to accomplish.")
        
        return "\n\n".join(enhanced_parts)
    
    async def generate_contextual_response(
        self,
        user_input: str,
        conversation_history: List[str] = None,
        user_preferences: Dict[str, Any] = None,
        available_tools: List[str] = None,
        model_name: str = None
    ) -> str:
        """Generate a contextually aware response"""
        
        context = {
            "conversation_history": conversation_history or [],
            "user_preferences": user_preferences or {},
            "available_tools": available_tools or []
        }
        
        system_prompt = """You are an intelligent conversational AI assistant that understands context and user intent. 
        You can help with navigation, search, information retrieval, device control, and many other tasks. 
        Always consider the conversation history and user preferences when responding.
        Be natural, helpful, and proactive in suggesting relevant actions."""
        
        enhanced_prompt = self._enhance_prompt_with_context(
            prompt=user_input,
            context=context,
            system_prompt=system_prompt
        )
        
        return await self.generate_response(
            prompt=enhanced_prompt,
            model_name=model_name,
            temperature=0.7
        )

# Global LLM manager instance
llm_manager = LLMManager()
