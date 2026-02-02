"""
Dreaming Engine V2 - Enhanced Version
- Read memories + user feedback -> Output insights -> Save to file
- Structured feedback with context for better learning
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests

logger = logging.getLogger(__name__)

# ========== Dream Prompt ==========

DREAM_PROMPT = """以下はあなたの記憶とユーザーからのフィードバックです。

{memories}

{user_feedback}

---

これらの情報群から本質的構造を抽出してください。
"""


class DreamingEngine:
    """Simple Dreaming Engine"""

    def __init__(
        self,
        memory_system,
        data_dir: Path = None,
        llm_host: str = "localhost",
        llm_port: int = 1234,
        api_token: str = ""
    ):
        self.memory = memory_system
        self.llm_host = llm_host
        self.llm_port = llm_port
        self.api_token = api_token
        self.api_url = f"http://{self.llm_host}:{self.llm_port}/api/v1/chat"

        # Data directory
        self.data_dir = data_dir or Path("./data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Insights file
        self.insights_file = self.data_dir / "insights.jsonl"

        # Archives
        self.archives_file = self.data_dir / "dream_archives.jsonl"

        # User feedback file (from personality_axis)
        self.user_feedback_file = self.data_dir / "personality_axis" / "user_feedback.jsonl"

    def check_threshold(self, threshold: int = 50) -> dict:
        """Check if memory count exceeds threshold"""
        count = self.memory.count()
        return {
            "current_count": count,
            "threshold": threshold,
            "should_dream": count > threshold,
            "excess": count - threshold if count > threshold else 0
        }

    def _get_loaded_model(self) -> str:
        """Get currently loaded model for API calls"""
        try:
            models_url = f"http://{self.llm_host}:{self.llm_port}/api/v1/models"
            headers = {"Content-Type": "application/json"}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"

            response = requests.get(models_url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                for model in data.get("models", []):
                    if model.get("loaded_instances"):
                        return model.get("key", model["loaded_instances"][0]["id"])
        except:
            pass
        # Default model for JIT
        return "qwen/qwen3-30b-a3b-2507"

    def _call_llm(self, prompt: str, temperature: float = 0.7, use_sequential_thinking: bool = True) -> str:
        """Call LM Studio MCP API with optional sequential-thinking"""
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"

            # Get model for API call
            model = self._get_loaded_model()

            # Build integrations list - use mcp.json server with mcp/ prefix
            integrations = ["mcp/sequential-thinking"] if use_sequential_thinking else []

            logger.info(f"Calling MCP API (model: {model}, integrations: {integrations}) with prompt length: {len(prompt)} chars")

            payload = {
                "model": model,
                "input": prompt,
                "integrations": integrations,
                "temperature": temperature,
                "context_length": 16000
            }

            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=300
            )

            if response.status_code == 200:
                result = response.json()

                # Parse MCP response format
                messages = []
                for item in result.get("output", []):
                    if item.get("type") == "message":
                        content = item.get("content", "")
                        if content:
                            messages.append(content)

                content = "\n".join(messages).strip()
                logger.info(f"MCP response length: {len(content)} chars")
                return content
            else:
                logger.error(f"MCP API error: {response.status_code} - {response.text[:200]}")
                return ""

        except Exception as e:
            logger.error(f"MCP API call failed: {e}")
            return ""

    def _parse_insights(self, response: str) -> list:
        """Extract insights from LLM response (simple line-by-line)"""
        insights = []

        for line in response.strip().split('\n'):
            line = line.strip()
            # Find numbered lines (1. 2. 3. etc.)
            if line and len(line) > 3:
                # Remove number
                if line[0].isdigit() and (line[1] == '.' or (line[1].isdigit() and line[2] == '.')):
                    # Remove "1. " or "10. "
                    parts = line.split('.', 1)
                    if len(parts) > 1:
                        insight = parts[1].strip()
                        if insight:
                            insights.append(insight)

        return insights

    def _load_user_feedback(self, limit: int = 20) -> list:
        """Load user feedback from file"""
        feedbacks = []
        if not self.user_feedback_file.exists():
            return feedbacks

        try:
            with open(self.user_feedback_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        feedbacks.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"Failed to load user feedback: {e}")

        # Return most recent feedbacks
        return feedbacks[-limit:]

    def _format_user_feedback(self, feedbacks: list) -> str:
        """Format user feedback for dream prompt"""
        if not feedbacks:
            return "(ユーザーフィードバックなし)"

        lines = []
        for fb in feedbacks:
            timestamp = fb.get("timestamp", "")[:16]
            user_input = fb.get("user_input", "")[:100]
            assistant_output = fb.get("assistant_output", "")[:150]
            feedback = fb.get("feedback", "")
            input_axes = fb.get("input_axes", {})
            response_axes = fb.get("response_axes", {})

            # Format axes compactly
            axes_str = ""
            if response_axes:
                axes_parts = []
                axis_names = {
                    "analysis_overview": "分析-俯瞰",
                    "individual_collective": "個-集団",
                    "empathy_responsibility": "共感-責任",
                    "cooperation_independence": "協調-自立",
                    "stability_transformation": "安定-変容",
                    "divergence_convergence": "拡散-収束"
                }
                for k, v in response_axes.items():
                    if k in axis_names:
                        sign = "+" if v > 0 else ""
                        axes_parts.append(f"{axis_names[k]}:{sign}{v}")
                axes_str = f"\n応答人格軸: {', '.join(axes_parts)}"

            entry = f"""
---
[{timestamp}]
入力: 「{user_input}...」
応答: 「{assistant_output}...」{axes_str}
**フィードバック**: {feedback}
"""
            lines.append(entry)

        return "\n".join(lines)

    def dream(self, memory_limit: int = 50) -> dict:
        """Execute dreaming mode"""
        start_time = datetime.now()
        logger.info("=== Dream V2 Enhanced Starting ===")

        # Step 1: Get memories
        export = self.memory.export_all()
        all_memories = export.get("all_memories", [])

        if not all_memories:
            logger.warning("No memories to process")
            return {"status": "skipped", "reason": "No memories"}

        # Sort by importance and select top
        sorted_memories = sorted(all_memories, key=lambda x: x.get("importance", 5), reverse=True)
        selected_memories = sorted_memories[:memory_limit]

        logger.info(f"Selected {len(selected_memories)} memories for dreaming")

        # Step 2: Convert memories to text
        memories_text = ""
        for i, mem in enumerate(selected_memories, 1):
            content = mem.get("content", "")
            category = mem.get("category", "unknown")
            memories_text += f"\n### 記憶 {i} [{category}]\n{content}\n"

        # Step 3: Load and format user feedback
        user_feedbacks = self._load_user_feedback(limit=20)
        feedback_text = self._format_user_feedback(user_feedbacks)
        logger.info(f"Loaded {len(user_feedbacks)} user feedbacks for dreaming")

        # Step 4: Have LLM generate insights
        prompt = DREAM_PROMPT.format(memories=memories_text, user_feedback=feedback_text)
        response = self._call_llm(prompt)

        if not response:
            logger.error("Empty response from LLM")
            return {"status": "failed", "reason": "LLM returned empty response"}

        # Step 5: Extract insights (or use full response if no numbered list)
        insights = self._parse_insights(response)
        if not insights:
            # Fallback: save entire response as one insight
            insights = [response.strip()]
            logger.info("No numbered insights found, saving full response")
        else:
            logger.info(f"Extracted {len(insights)} insights")

        # Step 6: Save to insights file
        timestamp = datetime.now().isoformat()
        saved_count = 0

        with open(self.insights_file, "a", encoding="utf-8") as f:
            for insight in insights:
                entry = {
                    "timestamp": timestamp,
                    "insight": insight
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                saved_count += 1

        logger.info(f"Saved {saved_count} insights to {self.insights_file}")

        # Step 7: Archive and delete processed memories
        processed_ids = [mem["id"] for mem in selected_memories]

        # Archive (append to single file)
        archive_entry = {
            "archived_at": timestamp,
            "memories_count": len(selected_memories),
            "memories": selected_memories,
            "user_feedbacks_used": len(user_feedbacks),
            "insights_generated": insights
        }
        with open(self.archives_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(archive_entry, ensure_ascii=False) + "\n")

        # Delete
        delete_result = self.memory.batch_delete(processed_ids)
        deleted_count = delete_result.get("deleted_count", 0)

        logger.info(f"Archived and deleted {deleted_count} memories")

        # Complete
        duration = (datetime.now() - start_time).total_seconds()

        result = {
            "status": "completed",
            "memories_processed": len(selected_memories),
            "user_feedbacks_used": len(user_feedbacks),
            "insights_generated": len(insights),
            "insights": insights,
            "memories_deleted": deleted_count,
            "duration_seconds": duration,
            "archive_path": str(self.archives_file)
        }

        logger.info(f"=== Dream V2 Enhanced Complete: {len(insights)} insights from {len(selected_memories)} memories + {len(user_feedbacks)} feedbacks in {duration:.1f}s ===")

        return result

    def get_all_insights(self) -> list:
        """Get all insights from storage"""
        insights = []

        if not self.insights_file.exists():
            return insights

        with open(self.insights_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        insights.append(entry)
                    except json.JSONDecodeError:
                        continue

        return insights

    def get_recent_insights(self, limit: int = 20) -> list:
        """Get recent insights"""
        all_insights = self.get_all_insights()
        return all_insights[-limit:]

    def count_insights(self) -> int:
        """Count total insights"""
        return len(self.get_all_insights())

    def get_stats(self) -> dict:
        """Get dreaming statistics"""
        insights_count = self.count_insights()
        memory_count = self.memory.count()

        # Count dream cycles from archives
        dream_cycles = 0
        total_archived = 0
        last_dream = None

        if self.archives_file.exists():
            with open(self.archives_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        dream_cycles += 1
                        total_archived += entry.get("memories_count", 0)
                        last_dream = entry.get("archived_at")
                    except:
                        pass

        return {
            "dream_cycles": dream_cycles,
            "total_archived_memories": total_archived,
            "current_memory_count": memory_count,
            "total_insights": insights_count,
            "last_dream": last_dream
        }

    def get_last_report(self) -> Optional[str]:
        """Get last dream report as formatted text"""
        if not self.archives_file.exists():
            return None

        last_entry = None
        with open(self.archives_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    last_entry = json.loads(line.strip())
                except:
                    pass

        if not last_entry:
            return None

        report = f"""# Dream Report
Date: {last_entry.get('archived_at', 'Unknown')}
Memories Processed: {last_entry.get('memories_count', 0)}

## Insights Generated
"""
        for i, insight in enumerate(last_entry.get('insights_generated', []), 1):
            report += f"{i}. {insight}\n"

        return report
