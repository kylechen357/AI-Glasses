"""
AI System Orchestrator
Main orchestrator that coordinates LLMs, MCP tools, and RAG memory
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import uuid

try:
    from .config import config
    from .llm_manager import llm_manager
    from .mcp_manager import mcp_manager
    from .rag_memory import rag_memory
except ImportError:
    from config import config
    from llm_manager import llm_manager
    from mcp_manager import mcp_manager
    from rag_memory import rag_memory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConversationSession:
    """Represents a conversation session with memory and context"""
    
    def __init__(self, session_id: str = None, title: str = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.title = title or f"Session {self.session_id[:8]}"
        self.created_at = datetime.now()
        self.message_history: List[Dict[str, Any]] = []
        self.context_documents: List[Dict[str, Any]] = []
        self.used_tools: List[str] = []
        
    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """Add a message to the session history"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.message_history.append(message)
        
    def get_recent_history(self, max_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent message history formatted for LLM"""
        recent = self.message_history[-max_messages:] if max_messages > 0 else self.message_history
        return [{"role": msg["role"], "content": msg["content"]} for msg in recent]

class AIOrchestrator:
    """Main AI system orchestrator"""
    
    def __init__(self):
        self.active_sessions: Dict[str, ConversationSession] = {}
        self.system_initialized = False
        
    async def initialize(self):
        """Initialize all system components"""
        if self.system_initialized:
            return
            
        logger.info("Initializing AI System...")
        
        try:
            # Initialize all components
            await llm_manager.initialize()
            await mcp_manager.initialize()
            await rag_memory.initialize()
            
            self.system_initialized = True
            logger.info("AI System initialized successfully!")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI System: {e}")
            raise
    
    async def create_session(self, title: str = None) -> str:
        """Create a new conversation session"""
        session = ConversationSession(title=title)
        self.active_sessions[session.session_id] = session
        
        # Add to memory system
        await rag_memory.add_conversation(session.session_id, session.title)
        
        logger.info(f"Created new session: {session.session_id}")
        return session.session_id
    
    async def process_query(
        self,
        query: str,
        session_id: str = None,
        model_name: str = None,
        use_tools: bool = True,
        use_memory: bool = True,
        temperature: float = None
    ) -> Dict[str, Any]:
        """Process a user query with full AI capabilities"""
        
        if not self.system_initialized:
            await self.initialize()
        
        # Get or create session
        if session_id and session_id in self.active_sessions:
            session = self.active_sessions[session_id]
        else:
            session_id = await self.create_session()
            session = self.active_sessions[session_id]
        
        # Add user message to session
        session.add_message("user", query)
        
        try:
            # Step 1: Retrieve relevant memory if enabled
            relevant_context = []
            if use_memory:
                relevant_docs = await rag_memory.search_similar(query, max_results=3)
                relevant_context = relevant_docs
                session.context_documents.extend(relevant_docs)
            
            # Step 2: Determine if tools are needed
            available_tools = []
            if use_tools:
                available_tools = await self._get_relevant_tools(query)
            
            # Step 3: Build enhanced prompt with context
            enhanced_prompt = await self._build_enhanced_prompt(
                query, 
                session, 
                relevant_context, 
                available_tools
            )
            
            # Step 4: Generate initial response
            initial_response = await llm_manager.chat_completion(
                messages=enhanced_prompt,
                model_name=model_name,
                temperature=temperature
            )
            
            # Step 5: Execute tools if mentioned in response
            tool_results = []
            if use_tools and available_tools:
                tool_results = await self._execute_mentioned_tools(initial_response, available_tools)
                session.used_tools.extend([tool["name"] for tool in tool_results])
            
            # Step 6: Generate final response with tool results
            final_response = initial_response
            if tool_results:
                final_response = await self._generate_final_response(
                    enhanced_prompt,
                    initial_response,
                    tool_results,
                    model_name,
                    temperature
                )
            
            # Step 7: Add assistant message to session and memory
            session.add_message("assistant", final_response, {
                "tools_used": [tool["name"] for tool in tool_results],
                "context_docs_count": len(relevant_context)
            })
            
            await rag_memory.add_message_to_conversation(
                session_id, "user", query
            )
            await rag_memory.add_message_to_conversation(
                session_id, "assistant", final_response
            )
            
            # Return comprehensive response
            return {
                "response": final_response,
                "session_id": session_id,
                "context_used": relevant_context,
                "tools_executed": tool_results,
                "model_used": model_name or config.default_llm,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            error_response = f"I apologize, but I encountered an error while processing your request: {e}"
            session.add_message("assistant", error_response, {"error": True})
            
            return {
                "response": error_response,
                "session_id": session_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _get_relevant_tools(self, query: str) -> List[Dict[str, Any]]:
        """Determine which tools might be relevant for the query"""
        all_tools = mcp_manager.get_available_tools()
        relevant_tools = []
        
        query_lower = query.lower()
        
        # Simple keyword-based relevance (could be enhanced with ML)
        for server_name, tools in all_tools.items():
            for tool in tools:
                tool_info = {
                    "server": server_name,
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
                
                # Check relevance based on keywords
                if any(keyword in query_lower for keyword in [
                    "file", "read", "write", "directory"
                ]) and "filesystem" in tool["name"].lower():
                    relevant_tools.append(tool_info)
                elif any(keyword in query_lower for keyword in [
                    "stock", "price", "market", "trading"
                ]) and "stock" in tool["name"].lower():
                    relevant_tools.append(tool_info)
                elif any(keyword in query_lower for keyword in [
                    "search", "find", "lookup", "web"
                ]) and "search" in tool["name"].lower():
                    relevant_tools.append(tool_info)
        
        return relevant_tools
    
    async def _build_enhanced_prompt(
        self,
        query: str,
        session: ConversationSession,
        relevant_context: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Build an enhanced prompt with context and tool information"""
        
        messages = []
        
        # System prompt
        system_prompt = f"""You are an advanced AI assistant with access to local language models, various tools via Model Context Protocol (MCP), and a long-term memory system.

Current time: {datetime.now().isoformat()}
Session ID: {session.session_id}

CAPABILITIES:
1. Access to local LLMs for reasoning and generation
2. MCP tools for various tasks (filesystem, web search, stock data, etc.)
3. RAG-based long-term memory for context retrieval
4. Conversation history and context management

MEMORY CONTEXT:
"""
        
        if relevant_context:
            system_prompt += "Relevant information from memory:\n"
            for i, doc in enumerate(relevant_context[:3], 1):
                system_prompt += f"{i}. {doc['content'][:200]}...\n"
        else:
            system_prompt += "No relevant context found in memory.\n"
        
        if available_tools:
            system_prompt += f"\nAVAILABLE TOOLS:\n"
            for tool in available_tools:
                system_prompt += f"- {tool['name']} ({tool['server']}): {tool['description']}\n"
            system_prompt += "\nYou can mention tools in your response and I will execute them for you.\n"
        
        system_prompt += """
INSTRUCTIONS:
- Provide helpful, accurate, and contextual responses
- Use memory context when relevant
- Suggest or mention tools when they would be useful
- Be conversational and maintain context across the session
- If you need to use a tool, mention it clearly in your response
"""
        
        messages.append({"role": "system", "content": system_prompt})
        
        # Add recent conversation history
        recent_history = session.get_recent_history(max_messages=6)
        messages.extend(recent_history[:-1])  # Exclude the current query
        
        # Add current query
        messages.append({"role": "user", "content": query})
        
        return messages
    
    async def _execute_mentioned_tools(
        self,
        response: str,
        available_tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Execute tools mentioned in the LLM response"""
        
        tool_results = []
        response_lower = response.lower()
        
        # Simple tool detection (could be enhanced with NLP)
        for tool in available_tools:
            tool_name = tool["name"]
            tool_server = tool["server"]
            
            if tool_name.lower() in response_lower or any(
                keyword in response_lower 
                for keyword in tool_name.lower().split("_")
            ):
                try:
                    # Extract parameters (simplified - would need more sophisticated parsing)
                    parameters = await self._extract_tool_parameters(response, tool)
                    
                    if parameters:
                        result = await mcp_manager.execute_tool(
                            tool_server, tool_name, parameters
                        )
                        tool_results.append({
                            "name": tool_name,
                            "server": tool_server,
                            "parameters": parameters,
                            "result": result
                        })
                        
                except Exception as e:
                    logger.error(f"Error executing tool {tool_name}: {e}")
                    tool_results.append({
                        "name": tool_name,
                        "server": tool_server,
                        "error": str(e)
                    })
        
        return tool_results
    
    async def _extract_tool_parameters(
        self,
        response: str,
        tool: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for tool execution from response"""
        
        # Simplified parameter extraction - in practice, this would be more sophisticated
        parameters = {}
        
        tool_name = tool["name"]
        tool_params = tool["parameters"]
        
        # Basic parameter extraction based on tool type
        if "read_file" in tool_name.lower() and "path" in tool_params:
            # Look for file paths in response
            import re
            path_matches = re.findall(r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']', response)
            if path_matches:
                parameters["path"] = path_matches[0]
        
        elif "search" in tool_name.lower() and "query" in tool_params:
            # Use parts of the original response as search query
            words = response.split()
            if len(words) > 3:
                parameters["query"] = " ".join(words[:10])  # First 10 words
        
        elif "stock" in tool_name.lower() and "symbol" in tool_params:
            # Look for stock symbols
            import re
            symbol_matches = re.findall(r'\b[A-Z]{1,5}\b', response)
            if symbol_matches:
                parameters["symbol"] = symbol_matches[0]
        
        return parameters
    
    async def _generate_final_response(
        self,
        original_prompt: List[Dict[str, str]],
        initial_response: str,
        tool_results: List[Dict[str, Any]],
        model_name: str = None,
        temperature: float = None
    ) -> str:
        """Generate final response incorporating tool results"""
        
        # Build prompt with tool results
        tool_context = "TOOL EXECUTION RESULTS:\n"
        for result in tool_results:
            if "error" in result:
                tool_context += f"- {result['name']}: Error - {result['error']}\n"
            else:
                tool_context += f"- {result['name']}: {json.dumps(result['result'], indent=2)}\n"
        
        final_prompt = original_prompt + [
            {"role": "assistant", "content": initial_response},
            {"role": "user", "content": f"{tool_context}\nPlease provide a comprehensive response incorporating these tool results."}
        ]
        
        final_response = await llm_manager.chat_completion(
            messages=final_prompt,
            model_name=model_name,
            temperature=temperature
        )
        
        return final_response
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a session"""
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        return {
            "session_id": session.session_id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "message_count": len(session.message_history),
            "tools_used": list(set(session.used_tools)),
            "context_documents": len(session.context_documents)
        }
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions"""
        sessions = []
        for session_id, session in self.active_sessions.items():
            info = await self.get_session_info(session_id)
            sessions.append(info)
        return sessions
    
    async def clear_conversation(self, session_id: str) -> bool:
        """Clear conversation history for a session"""
        try:
            # Clear from active session if it exists
            if session_id in self.active_sessions:
                session = self.active_sessions[session_id]
                session.message_history.clear()
                session.context_documents.clear()
                session.used_tools.clear()
                logger.info(f"Cleared active session data for {session_id}")
            
            # Clear from persistent memory
            cleared = await rag_memory.clear_conversation_history(session_id)
            
            if cleared:
                logger.info(f"Cleared conversation history for session {session_id}")
            
            return cleared
            
        except Exception as e:
            logger.error(f"Failed to clear conversation {session_id}: {e}")
            return False
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        if not self.system_initialized:
            return {"status": "not_initialized"}
        
        try:
            llm_models = await llm_manager.list_models()
            mcp_status = await mcp_manager.get_server_status()
            memory_stats = await rag_memory.get_memory_stats()
            
            return {
                "status": "running",
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "llm_manager": {
                        "available_models": len(llm_models),
                        "models": [model["name"] for model in llm_models if model["available"]]
                    },
                    "mcp_manager": {
                        "total_servers": len(mcp_status),
                        "running_servers": sum(1 for s in mcp_status.values() if s["running"]),
                        "total_tools": sum(s["tools_available"] for s in mcp_status.values())
                    },
                    "rag_memory": memory_stats
                },
                "active_sessions": len(self.active_sessions)
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {"status": "error", "error": str(e)}
    
    async def shutdown(self):
        """Shutdown the AI system"""
        logger.info("Shutting down AI System...")
        
        try:
            # Shutdown MCP manager with timeout
            await asyncio.wait_for(mcp_manager.shutdown(), timeout=15.0)
        except asyncio.TimeoutError:
            logger.warning("MCP shutdown timed out, forcing cleanup")
        except Exception as e:
            logger.error(f"Error during MCP shutdown: {e}")
        
        try:
            # Clear active sessions
            self.active_sessions.clear()
            self.system_initialized = False
            
            logger.info("AI System shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during final cleanup: {e}")
            logger.exception("Shutdown error details")

# Global orchestrator instance
ai_orchestrator = AIOrchestrator()
