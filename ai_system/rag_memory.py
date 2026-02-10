"""
RAG Memory System
Implements Retrieval-Augmented Generation for long-term memory
"""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

try:
    from .config import RAGConfig, config
except ImportError:
    from config import RAGConfig, config

logger = logging.getLogger(__name__)

class Document:
    """Represents a document in the memory system"""
    
    def __init__(self, content: str, metadata: Dict[str, Any] = None, doc_id: str = None):
        self.content = content
        self.metadata = metadata or {}
        self.doc_id = doc_id or self._generate_id()
        self.created_at = datetime.now().isoformat()
        
    def _generate_id(self) -> str:
        """Generate a unique document ID"""
        import hashlib
        import time
        content_hash = hashlib.md5(self.content.encode()).hexdigest()[:8]
        timestamp = str(int(time.time()))[-6:]
        return f"doc_{timestamp}_{content_hash}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert document to dictionary"""
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at
        }

class RAGMemorySystem:
    """RAG-based long-term memory system"""
    
    def __init__(self, rag_config: RAGConfig = None):
        self.config = rag_config or config.rag_config
        self.embedding_model = None
        self.vector_db = None
        self.metadata_db_path = Path(self.config.vector_db_path) / "metadata.db"
        self.collection_name = "memory_documents"
        
    async def initialize(self):
        """Initialize the RAG memory system"""
        logger.info("Initializing RAG Memory System...")
        
        # Create directories
        Path(self.config.vector_db_path).mkdir(parents=True, exist_ok=True)
        
        # Initialize embedding model
        await self._load_embedding_model()
        
        # Initialize vector database
        await self._initialize_vector_db()
        
        # Initialize metadata database
        await self._initialize_metadata_db()
        
        logger.info("RAG Memory System initialized successfully")
    
    async def _load_embedding_model(self):
        """Load the sentence transformer model for embeddings"""
        try:
            self.embedding_model = SentenceTransformer(self.config.embedding_model)
            logger.info(f"Loaded embedding model: {self.config.embedding_model}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    
    async def _initialize_vector_db(self):
        """Initialize ChromaDB vector database"""
        try:
            # Initialize ChromaDB client
            self.vector_db = chromadb.PersistentClient(
                path=self.config.vector_db_path,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Get or create collection
            try:
                self.collection = self.vector_db.get_collection(self.collection_name)
                logger.info(f"Found existing collection: {self.collection_name}")
            except:
                self.collection = self.vector_db.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Long-term memory documents"}
                )
                logger.info(f"Created new collection: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"Failed to initialize vector database: {e}")
            raise
    
    async def _initialize_metadata_db(self):
        """Initialize SQLite database for metadata"""
        try:
            with sqlite3.connect(self.metadata_db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS documents (
                        doc_id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        metadata TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        access_count INTEGER DEFAULT 0,
                        last_accessed TEXT
                    )
                ''')
                
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS conversations (
                        conversation_id TEXT PRIMARY KEY,
                        title TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        message_count INTEGER DEFAULT 0
                    )
                ''')
                
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS conversation_messages (
                        message_id TEXT PRIMARY KEY,
                        conversation_id TEXT,
                        role TEXT,
                        content TEXT,
                        timestamp TEXT,
                        FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
                    )
                ''')
                
                conn.commit()
                logger.info("Metadata database initialized")
                
        except Exception as e:
            logger.error(f"Failed to initialize metadata database: {e}")
            raise
    
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks for processing"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), self.config.chunk_size - self.config.chunk_overlap):
            chunk_words = words[i:i + self.config.chunk_size]
            chunk = " ".join(chunk_words)
            if chunk.strip():
                chunks.append(chunk)
                
        return chunks
    
    async def add_document(self, content: str, metadata: Dict[str, Any] = None, doc_id: str = None) -> str:
        """Add a document to the memory system"""
        try:
            document = Document(content, metadata, doc_id)
            
            # Chunk the content
            chunks = self._chunk_text(content)
            
            # Generate embeddings for chunks
            embeddings = self.embedding_model.encode(chunks)
            
            # Prepare data for vector database
            chunk_ids = [f"{document.doc_id}_chunk_{i}" for i in range(len(chunks))]
            chunk_metadata = [
                {
                    "doc_id": document.doc_id,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    **document.metadata
                }
                for i in range(len(chunks))
            ]
            
            # Add to vector database
            self.collection.add(
                ids=chunk_ids,
                documents=chunks,
                metadatas=chunk_metadata,
                embeddings=embeddings.tolist()
            )
            
            # Add to metadata database
            with sqlite3.connect(self.metadata_db_path) as conn:
                conn.execute(
                    '''INSERT OR REPLACE INTO documents 
                       (doc_id, content, metadata, created_at, updated_at, access_count, last_accessed)
                       VALUES (?, ?, ?, ?, ?, 0, ?)''',
                    (
                        document.doc_id,
                        content,
                        json.dumps(metadata or {}),
                        document.created_at,
                        document.created_at,
                        document.created_at
                    )
                )
                conn.commit()
            
            logger.info(f"Added document {document.doc_id} with {len(chunks)} chunks")
            return document.doc_id
            
        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            raise
    
    async def search_similar(self, query: str, max_results: int = None) -> List[Dict[str, Any]]:
        """Search for similar documents using vector similarity"""
        try:
            max_results = max_results or self.config.max_retrieved_docs
            
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query])
            
            # Search in vector database
            results = self.collection.query(
                query_embeddings=query_embedding.tolist(),
                n_results=max_results
            )
            
            # Process results
            similar_docs = []
            if results["documents"]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results["documents"][0],
                    results["metadatas"][0], 
                    results["distances"][0]
                )):
                    # Check similarity threshold
                    similarity = 1 - distance  # Convert distance to similarity
                    if similarity >= self.config.similarity_threshold:
                        similar_docs.append({
                            "content": doc,
                            "metadata": metadata,
                            "similarity": similarity,
                            "doc_id": metadata.get("doc_id"),
                            "chunk_index": metadata.get("chunk_index", 0)
                        })
            
            # Update access statistics
            for doc in similar_docs:
                await self._update_access_stats(doc["doc_id"])
            
            logger.info(f"Found {len(similar_docs)} similar documents for query")
            return similar_docs
            
        except Exception as e:
            logger.error(f"Failed to search similar documents: {e}")
            return []
    
    async def _update_access_stats(self, doc_id: str):
        """Update document access statistics"""
        try:
            with sqlite3.connect(self.metadata_db_path) as conn:
                conn.execute(
                    '''UPDATE documents 
                       SET access_count = access_count + 1, last_accessed = ?
                       WHERE doc_id = ?''',
                    (datetime.now().isoformat(), doc_id)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to update access stats for {doc_id}: {e}")
    
    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID"""
        try:
            with sqlite3.connect(self.metadata_db_path) as conn:
                cursor = conn.execute(
                    '''SELECT doc_id, content, metadata, created_at, updated_at, access_count, last_accessed
                       FROM documents WHERE doc_id = ?''',
                    (doc_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    return {
                        "doc_id": row[0],
                        "content": row[1],
                        "metadata": json.loads(row[2]) if row[2] else {},
                        "created_at": row[3],
                        "updated_at": row[4],
                        "access_count": row[5],
                        "last_accessed": row[6]
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
        
        return None
    
    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the memory system"""
        try:
            # Delete from vector database
            # First, find all chunk IDs for this document
            results = self.collection.get(
                where={"doc_id": doc_id}
            )
            
            if results["ids"]:
                self.collection.delete(ids=results["ids"])
            
            # Delete from metadata database
            with sqlite3.connect(self.metadata_db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM documents WHERE doc_id = ?",
                    (doc_id,)
                )
                conn.commit()
                
                deleted = cursor.rowcount > 0
                
            if deleted:
                logger.info(f"Deleted document {doc_id}")
            else:
                logger.warning(f"Document {doc_id} not found for deletion")
                
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False
    
    async def add_conversation(self, conversation_id: str, title: str = None):
        """Add a new conversation to memory"""
        try:
            with sqlite3.connect(self.metadata_db_path) as conn:
                conn.execute(
                    '''INSERT OR REPLACE INTO conversations 
                       (conversation_id, title, created_at, updated_at, message_count)
                       VALUES (?, ?, ?, ?, 0)''',
                    (
                        conversation_id,
                        title or f"Conversation {conversation_id}",
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    )
                )
                conn.commit()
            logger.info(f"Added conversation {conversation_id}")
        except Exception as e:
            logger.error(f"Failed to add conversation {conversation_id}: {e}")
    
    async def add_message_to_conversation(self, conversation_id: str, role: str, content: str, message_id: str = None):
        """Add a message to a conversation"""
        try:
            message_id = message_id or f"msg_{int(datetime.now().timestamp())}_{hash(content) % 10000}"
            
            with sqlite3.connect(self.metadata_db_path) as conn:
                # Add message
                conn.execute(
                    '''INSERT INTO conversation_messages 
                       (message_id, conversation_id, role, content, timestamp)
                       VALUES (?, ?, ?, ?, ?)''',
                    (message_id, conversation_id, role, content, datetime.now().isoformat())
                )
                
                # Update conversation stats
                conn.execute(
                    '''UPDATE conversations 
                       SET message_count = message_count + 1, updated_at = ?
                       WHERE conversation_id = ?''',
                    (datetime.now().isoformat(), conversation_id)
                )
                
                conn.commit()
            
            # Also add message content to document memory for retrieval
            await self.add_document(
                content=content,
                metadata={
                    "type": "conversation_message",
                    "conversation_id": conversation_id,
                    "role": role,
                    "message_id": message_id
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to add message to conversation {conversation_id}: {e}")
    
    async def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get conversation history"""
        try:
            with sqlite3.connect(self.metadata_db_path) as conn:
                cursor = conn.execute(
                    '''SELECT message_id, role, content, timestamp
                       FROM conversation_messages 
                       WHERE conversation_id = ?
                       ORDER BY timestamp DESC
                       LIMIT ?''',
                    (conversation_id, limit)
                )
                
                messages = []
                for row in cursor.fetchall():
                    messages.append({
                        "message_id": row[0],
                        "role": row[1],
                        "content": row[2],
                        "timestamp": row[3]
                    })
                
                return list(reversed(messages))  # Return in chronological order
                
        except Exception as e:
            logger.error(f"Failed to get conversation history for {conversation_id}: {e}")
            return []
    
    async def clear_conversation_history(self, conversation_id: str) -> bool:
        """Clear all messages from a conversation"""
        try:
            with sqlite3.connect(self.metadata_db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM conversation_messages WHERE conversation_id = ?",
                    (conversation_id,)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Cleared {deleted_count} messages from conversation {conversation_id}")
                return deleted_count > 0
                
        except Exception as e:
            logger.error(f"Failed to clear conversation history for {conversation_id}: {e}")
            return False
    
    async def cleanup_old_documents(self, days: int = None):
        """Clean up old documents based on retention policy"""
        try:
            days = days or config.memory_retention_days
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.metadata_db_path) as conn:
                # Get old document IDs
                cursor = conn.execute(
                    "SELECT doc_id FROM documents WHERE created_at < ? AND access_count = 0",
                    (cutoff_date,)
                )
                old_doc_ids = [row[0] for row in cursor.fetchall()]
                
                # Delete old documents
                for doc_id in old_doc_ids:
                    await self.delete_document(doc_id)
                
                logger.info(f"Cleaned up {len(old_doc_ids)} old documents")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old documents: {e}")
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        try:
            stats = {"vector_db": {}, "metadata_db": {}}
            
            # Vector database stats
            collection_count = self.collection.count()
            stats["vector_db"]["total_chunks"] = collection_count
            
            # Metadata database stats
            with sqlite3.connect(self.metadata_db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM documents")
                stats["metadata_db"]["total_documents"] = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM conversations")
                stats["metadata_db"]["total_conversations"] = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM conversation_messages")
                stats["metadata_db"]["total_messages"] = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT AVG(access_count) FROM documents")
                avg_access = cursor.fetchone()[0]
                stats["metadata_db"]["avg_document_access"] = round(avg_access or 0, 2)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {}

# Global RAG memory system instance
rag_memory = RAGMemorySystem()
