"""
Local AI System with MCP and RAG
A comprehensive AI system combining local LLMs, MCP tools, and RAG memory
"""

__version__ = "1.0.0"
__author__ = "AI System Team"
__description__ = "Local AI System with MCP tools and RAG memory"

# Import main components
from .config import config
from .llm_manager import llm_manager
from .mcp_manager import mcp_manager
from .rag_memory import rag_memory
from .orchestrator import ai_orchestrator

__all__ = [
    "config",
    "llm_manager", 
    "mcp_manager",
    "rag_memory",
    "ai_orchestrator"
]
