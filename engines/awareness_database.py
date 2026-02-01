"""
Awareness Database
- JSONL format storage
- Metadata management
- Duplicate checking
- Training data export
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import hashlib
import logging

logger = logging.getLogger(__name__)


class AwarenessDatabase:
    """Awareness Database"""

    def __init__(self, data_dir: str = "./data/awareness"):
        """
        Args:
            data_dir: Data storage directory
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Main awareness file
        self.awareness_file = self.data_dir / "awareness.jsonl"

        # Training data file
        self.training_file = self.data_dir / "training_data.jsonl"

        # Statistics file
        self.stats_file = self.data_dir / "stats.json"

        # Hash set for duplicate checking
        self._content_hashes: set[str] = set()
        self._load_hashes()

    def _load_hashes(self):
        """Load hashes from existing data"""
        if self.awareness_file.exists():
            with open(self.awareness_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        content_hash = self._compute_hash(data)
                        self._content_hashes.add(content_hash)
                    except json.JSONDecodeError:
                        continue

    def _compute_hash(self, data: dict) -> str:
        """Compute hash of data"""
        # Use description + my_response for duplicate detection
        content = f"{data.get('description', '')}{data.get('my_response', '')}"
        return hashlib.md5(content.encode()).hexdigest()

    def save_awareness(self, awareness: dict) -> bool:
        """
        Save awareness

        Args:
            awareness: Awareness data

        Returns:
            Whether save was successful (False if duplicate)
        """
        # Duplicate check
        content_hash = self._compute_hash(awareness)
        if content_hash in self._content_hashes:
            logger.info("Skipping duplicate awareness")
            return False

        # Save
        with open(self.awareness_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(awareness, ensure_ascii=False) + "\n")

        self._content_hashes.add(content_hash)
        logger.info(f"Awareness saved: {awareness.get('type', 'unknown')}")

        # Update statistics
        self._update_stats(awareness)

        return True

    def save_training_data(self, training_data: dict) -> bool:
        """
        Save training data

        Args:
            training_data: Training data (messages + metadata format)

        Returns:
            Whether save was successful
        """
        with open(self.training_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(training_data, ensure_ascii=False) + "\n")

        logger.info("Training data saved")
        return True

    def _update_stats(self, awareness: dict):
        """Update statistics"""
        stats = self.get_stats()

        # Update count
        stats["total_count"] = stats.get("total_count", 0) + 1
        stats["last_updated"] = datetime.now().isoformat()

        # Count by type
        awareness_type = awareness.get("type", "unknown")
        if "by_type" not in stats:
            stats["by_type"] = {}
        stats["by_type"][awareness_type] = stats["by_type"].get(awareness_type, 0) + 1

        # Count by category
        category = awareness.get("category", "unknown")
        if "by_category" not in stats:
            stats["by_category"] = {}
        stats["by_category"][category] = stats["by_category"].get(category, 0) + 1

        # Score distribution
        score = awareness.get("learning_potential", 3)
        if "by_score" not in stats:
            stats["by_score"] = {}
        stats["by_score"][str(score)] = stats["by_score"].get(str(score), 0) + 1

        # Save
        with open(self.stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

    def get_stats(self) -> dict:
        """Get statistics"""
        if self.stats_file.exists():
            with open(self.stats_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "total_count": 0,
            "by_type": {},
            "by_category": {},
            "by_score": {},
            "last_updated": None
        }

    def count(self) -> int:
        """Get total awareness count"""
        stats = self.get_stats()
        return stats.get("total_count", 0)

    def count_training_data(self) -> int:
        """Get training data count"""
        if not self.training_file.exists():
            return 0
        with open(self.training_file, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)

    def get_all_awareness(self, limit: int = 100) -> list[dict]:
        """Get all awareness"""
        awareness_list = []
        if not self.awareness_file.exists():
            return awareness_list

        with open(self.awareness_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    awareness_list.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # Sort by newest first
        awareness_list.sort(
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )

        return awareness_list[:limit]

    def get_by_type(self, awareness_type: str, limit: int = 50) -> list[dict]:
        """Get awareness by type"""
        all_awareness = self.get_all_awareness(limit=1000)
        filtered = [a for a in all_awareness if a.get("type") == awareness_type]
        return filtered[:limit]

    def get_by_category(self, category: str, limit: int = 50) -> list[dict]:
        """Get awareness by category"""
        all_awareness = self.get_all_awareness(limit=1000)
        filtered = [a for a in all_awareness if a.get("category") == category]
        return filtered[:limit]

    def get_high_quality(self, min_score: int = 4, limit: int = 50) -> list[dict]:
        """Get high quality awareness"""
        all_awareness = self.get_all_awareness(limit=1000)
        filtered = [a for a in all_awareness if a.get("learning_potential", 0) >= min_score]
        return filtered[:limit]

    def export_training_data(
        self,
        output_path: Optional[Path] = None,
        min_score: int = 3
    ) -> Path:
        """
        Export training data

        Args:
            output_path: Output path (None for default)
            min_score: Minimum score

        Returns:
            Exported file path
        """
        if output_path is None:
            output_path = self.data_dir / f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

        if not self.training_file.exists():
            logger.warning("Training data file does not exist")
            return output_path

        with open(self.training_file, "r", encoding="utf-8") as f_in:
            with open(output_path, "w", encoding="utf-8") as f_out:
                for line in f_in:
                    try:
                        data = json.loads(line)
                        if data.get("metadata", {}).get("score", 0) >= min_score:
                            f_out.write(line)
                    except json.JSONDecodeError:
                        continue

        logger.info(f"Training data exported: {output_path}")
        return output_path

    def is_ready_for_training(self, min_samples: int = 100) -> bool:
        """Check if ready for LoRA training"""
        return self.count_training_data() >= min_samples

    def get_training_readiness(self, min_samples: int = 100) -> dict:
        """Get training readiness status"""
        current = self.count_training_data()
        return {
            "current_samples": current,
            "required_samples": min_samples,
            "ready": current >= min_samples,
            "progress_percent": min(100, (current / min_samples) * 100)
        }
