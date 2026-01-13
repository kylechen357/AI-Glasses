"""
AI System Configuration
Manages local LLMs, MCP tools, and RAG memory
"""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class LLMConfig:
    """Configuration for local LLM models"""
    model_name: str
    model_type: str  # 'ollama', 'llamacpp', etc.
    endpoint: str = "http://localhost:11434"
    context_length: int = 4096
    temperature: float = 0.7
    max_tokens: int = 2048

@dataclass
class MCPServerConfig:
    """Configuration for MCP servers"""
    name: str
    command: str
    args: List[str]
    env: Dict[str, str] = None
    working_dir: Optional[str] = None

@dataclass
class RAGConfig:
    """Configuration for RAG system"""
    vector_db_path: str = "./data/vector_db"
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_retrieved_docs: int = 5
    similarity_threshold: float = 0.7

class SystemConfig:
    """Main system configuration"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        self.logs_dir = self.base_dir / "logs"
        
        # Ensure directories exist
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        
        # Default LLM configurations
        self.llm_configs = {
            "llama3.2": LLMConfig(
                model_name="llama3.2",
                model_type="ollama",
                context_length=8192
            ),
            "codellama": LLMConfig(
                model_name="codellama",
                model_type="ollama",
                context_length=4096,
                temperature=0.1  # Lower temperature for code
            ),
            "mistral": LLMConfig(
                model_name="mistral",
                model_type="ollama",
                context_length=4096
            )
        }
        
        # MCP server configurations
        self.mcp_configs = {
            "filesystem": MCPServerConfig(
                name="filesystem",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", str(self.base_dir)]
            ),
            "stock-checker": MCPServerConfig(
                name="stock-checker",
                command="python3",
                args=[str(self.base_dir.parent / "mcp-servers/stock-checker/stock_server.py")]
            ),
            "web-search": MCPServerConfig(
                name="web-search",
                command="node",
                args=[str(self.base_dir.parent / "mcp-servers/web-search/dist/index.js")]
            )
        }
        
        # RAG configuration
        self.rag_config = RAGConfig(
            vector_db_path=str(self.data_dir / "vector_db")
        )
        
        # System settings
        self.default_llm = "llama3.2"
        self.max_conversation_history = 50
        self.memory_retention_days = 30
        
    def get_llm_config(self, model_name: str = None) -> LLMConfig:
        """Get LLM configuration"""
        model_name = model_name or self.default_llm
        return self.llm_configs.get(model_name, self.llm_configs[self.default_llm])
    
    def get_mcp_config(self, server_name: str) -> Optional[MCPServerConfig]:
        """Get MCP server configuration"""
        return self.mcp_configs.get(server_name)
    
    def list_available_llms(self) -> List[str]:
        """List all available LLM models"""
        return list(self.llm_configs.keys())
    
    def list_available_mcp_servers(self) -> List[str]:
        """List all available MCP servers"""
        return list(self.mcp_configs.keys())

# Global configuration instance
config = SystemConfig()
