import os
import json
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


@dataclass
class MemoryItem:
    """Individual memory item with content and metadata"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: __import__('time').time())
    embedding: Optional[List[float]] = None


class VectorMemoryStore:
    """Vector-based memory store using ChromaDB for similarity search"""
    
    def __init__(self, collection_name: str = "agent_memory", persist_dir: str = "./memory_db"):
        self.collection_name = collection_name
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(exist_ok=True)
        
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(collection_name)
        except:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        
        # Initialize sentence transformer for embeddings
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
    
    def add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add content to memory store"""
        memory_id = str(uuid.uuid4())
        metadata = metadata or {}
        
        # Generate embedding
        embedding = self.encoder.encode(content).tolist()
        
        # Add to ChromaDB
        self.collection.add(
            ids=[memory_id],
            documents=[content],
            metadatas=[metadata],
            embeddings=[embedding]
        )
        
        return memory_id
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar memories"""
        # Generate query embedding
        query_embedding = self.encoder.encode(query).tolist()
        
        # Search in ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=['documents', 'metadatas', 'distances']
        )
        
        # Format results
        memories = []
        for i in range(len(results['ids'][0])):
            memories.append({
                'id': results['ids'][0][i],
                'content': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'similarity': 1 - results['distances'][0][i]  # Convert distance to similarity
            })
        
        return memories
    
    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific memory by ID"""
        try:
            result = self.collection.get(ids=[memory_id], include=['documents', 'metadatas'])
            if result['ids']:
                return {
                    'id': result['ids'][0],
                    'content': result['documents'][0],
                    'metadata': result['metadatas'][0]
                }
        except:
            pass
        return None
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID"""
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except:
            return False
    
    def clear(self):
        """Clear all memories"""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )


class EpisodicMemory:
    """Sequential memory for episodic experiences"""
    
    def __init__(self, max_episodes: int = 1000):
        self.episodes: List[Dict[str, Any]] = []
        self.max_episodes = max_episodes
    
    def add_episode(self, content: Dict[str, Any]):
        """Add an episode to memory"""
        episode = {
            'id': str(uuid.uuid4()),
            'timestamp': __import__('time').time(),
            'content': content
        }
        self.episodes.append(episode)
        
        # Keep only recent episodes
        if len(self.episodes) > self.max_episodes:
            self.episodes = self.episodes[-self.max_episodes:]
    
    def get_recent(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent episodes"""
        return self.episodes[-count:]
    
    def get_by_timeframe(self, start_time: float, end_time: float) -> List[Dict[str, Any]]:
        """Get episodes within a time frame"""
        return [ep for ep in self.episodes 
                if start_time <= ep['timestamp'] <= end_time]
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """Simple text search in episodes"""
        query_lower = query.lower()
        matches = []
        for episode in self.episodes:
            content_str = str(episode['content']).lower()
            if query_lower in content_str:
                matches.append(episode)
        return matches


class WorkingMemory:
    """Short-term working memory for current context"""
    
    def __init__(self, max_items: int = 20):
        self.items: Dict[str, Any] = {}
        self.max_items = max_items
        self.access_order: List[str] = []
    
    def set(self, key: str, value: Any):
        """Set a value in working memory"""
        if key in self.items:
            # Move to end if already exists
            self.access_order.remove(key)
        elif len(self.items) >= self.max_items:
            # Remove least recently used
            lru_key = self.access_order.pop(0)
            del self.items[lru_key]
        
        self.items[key] = value
        self.access_order.append(key)
    
    def get(self, key: str, default=None):
        """Get a value from working memory"""
        if key in self.items:
            # Update access order
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.items[key]
        return default
    
    def clear(self):
        """Clear working memory"""
        self.items.clear()
        self.access_order.clear()
    
    def keys(self) -> List[str]:
        """Get all keys"""
        return list(self.items.keys())


class IntegratedMemorySystem:
    """Integrated memory system combining different types of memory"""
    
    def __init__(self, memory_dir: str = "./agent_memory"):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(exist_ok=True)
        
        # Initialize different memory types
        self.vector_store = VectorMemoryStore(
            collection_name="semantic_memory",
            persist_dir=str(self.memory_dir / "vector")
        )
        self.episodic = EpisodicMemory()
        self.working = WorkingMemory()
        
        # Load episodic memory if exists
        self._load_episodic()
    
    def remember(self, content: str, memory_type: str = "semantic", metadata: Optional[Dict[str, Any]] = None):
        """Store content in appropriate memory"""
        metadata = metadata or {}
        metadata['type'] = memory_type
        
        if memory_type == "semantic":
            return self.vector_store.add(content, metadata)
        elif memory_type == "episodic":
            self.episodic.add_episode({'content': content, 'metadata': metadata})
            self._save_episodic()
        elif memory_type == "working":
            key = metadata.get('key', str(uuid.uuid4()))
            self.working.set(key, content)
            return key
    
    def recall(self, query: str, memory_type: str = "semantic", top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant memories"""
        if memory_type == "semantic":
            return self.vector_store.search(query, top_k)
        elif memory_type == "episodic":
            return self.episodic.search(query)
        elif memory_type == "working":
            # Return all working memory items for now
            return [{'key': k, 'content': v} for k, v in self.working.items.items()]
        return []
    
    def get_context(self, query: str, max_items: int = 10) -> Dict[str, Any]:
        """Get relevant context from all memory types"""
        context = {
            'semantic': self.vector_store.search(query, max_items // 3),
            'episodic': self.episodic.search(query)[:max_items // 3],
            'working': list(self.working.items.items())
        }
        return context
    
    def _save_episodic(self):
        """Save episodic memory to disk"""
        episodic_file = self.memory_dir / "episodic.json"
        with open(episodic_file, 'w') as f:
            json.dump(self.episodic.episodes, f, indent=2)
    
    def _load_episodic(self):
        """Load episodic memory from disk"""
        episodic_file = self.memory_dir / "episodic.json"
        if episodic_file.exists():
            try:
                with open(episodic_file, 'r') as f:
                    self.episodic.episodes = json.load(f)
            except:
                pass  # Continue with empty memory if loading fails
