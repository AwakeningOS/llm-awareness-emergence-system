"""
ChromaDB Vector Memory System
- Used alongside Memory MCP (knowledge graph)
- Strong for fuzzy search and similarity search
"""

import chromadb
from chromadb.config import Settings
from datetime import datetime
from pathlib import Path
from typing import Optional


class MemorySystem:
    """Vector-based long-term memory system"""

    def __init__(self, data_dir: str = "./data/chromadb"):
        """
        Args:
            data_dir: ChromaDB data storage directory
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.data_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="conversations",
            metadata={"description": "Vector memory for conversation history and user information"}
        )

    def save(
        self,
        content: str,
        category: str = "general",
        importance: int = 5,
        user_id: str = "default",
        metadata: Optional[dict] = None
    ) -> str:
        """
        Save memory

        Args:
            content: Content to save
            category: Category (user_info, preference, event, emotion, conversation)
            importance: Importance level (1-10)
            user_id: User ID
            metadata: Additional metadata

        Returns:
            ID of saved memory
        """
        memory_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        doc_metadata = {
            "category": category,
            "importance": importance,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
        }

        if metadata:
            doc_metadata.update(metadata)

        self.collection.add(
            ids=[memory_id],
            documents=[content],
            metadatas=[doc_metadata]
        )

        return memory_id

    def search(
        self,
        query: str,
        user_id: str = "default",
        limit: int = 5,
        category: Optional[str] = None
    ) -> list[dict]:
        """
        Search memory by similarity

        Args:
            query: Search query
            user_id: User ID
            limit: Number of results to retrieve
            category: Category to filter (None for all categories)

        Returns:
            List of search results
        """
        # Build where filter (ChromaDB requires $and for multiple conditions)
        if category:
            where_filter = {
                "$and": [
                    {"user_id": user_id},
                    {"category": category}
                ]
            }
        else:
            where_filter = {"user_id": user_id}

        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where=where_filter
        )

        memories = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                memories.append({
                    "id": results["ids"][0][i],
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None
                })

        return memories

    def get_recent(
        self,
        user_id: str = "default",
        limit: int = 10
    ) -> list[dict]:
        """
        Get recent memories

        Args:
            user_id: User ID
            limit: Number of results to retrieve

        Returns:
            List of recent memories
        """
        results = self.collection.get(
            where={"user_id": user_id},
            limit=limit
        )

        memories = []
        if results["documents"]:
            for i, doc in enumerate(results["documents"]):
                memories.append({
                    "id": results["ids"][i],
                    "content": doc,
                    "metadata": results["metadatas"][i] if results["metadatas"] else {}
                })

        # Sort by created_at (newest first)
        memories.sort(
            key=lambda x: x["metadata"].get("created_at", ""),
            reverse=True
        )

        return memories[:limit]

    def delete(self, memory_id: str) -> bool:
        """
        Delete memory

        Args:
            memory_id: ID of memory to delete

        Returns:
            Whether deletion was successful
        """
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception:
            return False

    def count(self, user_id: Optional[str] = None, category: Optional[str] = None) -> int:
        """
        Get total memory count

        Args:
            user_id: User ID (None for all)
            category: Category filter (None for all)

        Returns:
            Memory count
        """
        if user_id and category:
            results = self.collection.get(where={
                "$and": [
                    {"user_id": user_id},
                    {"category": category}
                ]
            })
            return len(results["ids"])
        elif user_id:
            results = self.collection.get(where={"user_id": user_id})
            return len(results["ids"])
        elif category:
            results = self.collection.get(where={"category": category})
            return len(results["ids"])
        return self.collection.count()

    def save_dialogue(
        self,
        user_message: str,
        assistant_message: str,
        user_id: str = "global",
        user_name: str = "unknown"
    ) -> str:
        """
        Save dialogue exchange immediately to ChromaDB

        Args:
            user_message: User's message
            assistant_message: Assistant's response
            user_id: User ID
            user_name: User's display name

        Returns:
            ID of saved dialogue
        """
        # Format dialogue as single content
        content = f"[User: {user_name}] {user_message}\n[Assistant] {assistant_message}"

        return self.save(
            content=content,
            category="dialogue",
            importance=3,  # Dialogue has medium importance
            user_id="global",  # Always global for unified memory
            metadata={
                "original_user_id": user_id,
                "user_name": user_name,
                "user_message": user_message[:500],  # Truncate for metadata
                "assistant_message": assistant_message[:500],
            }
        )

    def export_all(self, user_id: Optional[str] = None) -> dict:
        """
        Export all memories for dreaming process

        Args:
            user_id: User ID filter (None for all users - global dreaming)

        Returns:
            Structured export with statistics
        """
        from datetime import datetime

        # Get all memories
        if user_id:
            results = self.collection.get(where={"user_id": user_id})
        else:
            results = self.collection.get()

        if not results["ids"]:
            return {
                "harvested_at": datetime.now().isoformat(),
                "total_count": 0,
                "by_category": {},
                "all_memories": [],
                "time_range": None,
                "statistics": {}
            }

        # Organize by category
        by_category = {}
        all_memories = []
        timestamps = []
        importance_sum = 0

        for i, doc in enumerate(results["documents"]):
            metadata = results["metadatas"][i] if results["metadatas"] else {}
            memory_id = results["ids"][i]

            memory = {
                "id": memory_id,
                "content": doc,
                "category": metadata.get("category", "general"),
                "importance": metadata.get("importance", 5),
                "user_id": metadata.get("user_id", "unknown"),
                "created_at": metadata.get("created_at", ""),
                "metadata": metadata
            }

            all_memories.append(memory)

            # Group by category
            category = memory["category"]
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(memory)

            # Track timestamps
            if metadata.get("created_at"):
                timestamps.append(metadata["created_at"])

            importance_sum += memory["importance"]

        # Calculate statistics
        timestamps.sort()
        time_range = None
        if timestamps:
            time_range = {
                "oldest": timestamps[0],
                "newest": timestamps[-1]
            }

        category_counts = {cat: len(mems) for cat, mems in by_category.items()}

        return {
            "harvested_at": datetime.now().isoformat(),
            "total_count": len(all_memories),
            "by_category": by_category,
            "all_memories": all_memories,
            "time_range": time_range,
            "statistics": {
                "avg_importance": importance_sum / len(all_memories) if all_memories else 0,
                "category_counts": category_counts,
                "user_ids": list(set(m["user_id"] for m in all_memories))
            }
        }

    def batch_delete(self, memory_ids: list[str]) -> dict:
        """
        Delete multiple memories at once

        Args:
            memory_ids: List of memory IDs to delete

        Returns:
            Result summary
        """
        deleted = 0
        failed = []

        for memory_id in memory_ids:
            try:
                self.collection.delete(ids=[memory_id])
                deleted += 1
            except Exception as e:
                failed.append({"id": memory_id, "error": str(e)})

        return {
            "deleted_count": deleted,
            "failed_count": len(failed),
            "failed": failed
        }

    def batch_save(self, memories: list[dict]) -> dict:
        """
        Save multiple memories at once

        Args:
            memories: List of memory dicts with content, category, importance, user_id, metadata

        Returns:
            Result summary
        """
        saved = 0
        failed = []

        for mem in memories:
            try:
                self.save(
                    content=mem.get("content", ""),
                    category=mem.get("category", "general"),
                    importance=mem.get("importance", 5),
                    user_id=mem.get("user_id", "global"),
                    metadata=mem.get("metadata")
                )
                saved += 1
            except Exception as e:
                failed.append({"content": mem.get("content", "")[:50], "error": str(e)})

        return {
            "saved_count": saved,
            "failed_count": len(failed),
            "failed": failed
        }

    def get_by_ids(self, memory_ids: list[str]) -> list[dict]:
        """
        Get memories by their IDs

        Args:
            memory_ids: List of memory IDs

        Returns:
            List of memory dicts
        """
        try:
            results = self.collection.get(ids=memory_ids)

            memories = []
            if results["documents"]:
                for i, doc in enumerate(results["documents"]):
                    memories.append({
                        "id": results["ids"][i],
                        "content": doc,
                        "metadata": results["metadatas"][i] if results["metadatas"] else {}
                    })

            return memories
        except Exception:
            return []
